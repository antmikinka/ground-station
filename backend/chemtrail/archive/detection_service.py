# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Detection service - orchestrates CV detection to archive pipeline."""

import asyncio
from typing import List, Optional, Dict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import subprocess
import tempfile
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger
from ..cv.contrail_detector import ContrailDetection, ContrailDetector
from .chunker import (
    chunk_video,
    is_still_frame_chunk,
    preprocess_chunk,
    _get_ffmpeg_executable,
)
from .embedder import get_embedder, BaseEmbedder
from .vector_store import ChemtrailVectorStore
from .telemetry_overlay import apply_flight_overlay, build_hud_overlay
from ..services.flight_service import FlightService
from ..services.fr24_flight_service import FR24FlightService
from ..services.geocalc_service import pixel_to_az_el, estimate_position_single


class DetectionService:
    """Orchestrates detection processing and archival.

    Pipeline:
    1. Receive video chunk from chunker
    2. Skip if still-frame (static sky)
    3. Preprocess (downscale, reduce fps)
    4. Run CV detection (contrails, aircraft)
    5. Correlate with flight data
    6. Calculate geolocation
    7. Embed and archive in ChromaDB
    """

    def __init__(
        self,
        session: AsyncSession,
        vector_store: ChemtrailVectorStore,
        flight_service: FlightService,
        contrail_detector: ContrailDetector,
        embedder: Optional[BaseEmbedder] = None,
        fr24_service: Optional[FR24FlightService] = None,
    ):
        self.session = session
        self.vector_store = vector_store
        self.flight_service = flight_service
        self.fr24_service = fr24_service
        self.contrail_detector = contrail_detector
        self.embedder = embedder or get_embedder()

    async def process_detection_batch(
        self,
        chunks: List[Dict],
        camera_id: str,
        camera_metadata: Dict,
        skip_still_frames: bool = True,
        apply_overlay: bool = False,
    ) -> List[Dict]:
        """Process a batch of video chunks through the detection pipeline.

        Args:
            chunks: List from chunker with keys:
                   chunk_path, source_file, start_time, end_time
            camera_id: Camera UUID
            camera_metadata: Camera geolocation data with keys:
                          name, latitude, longitude, altitude,
                          azimuth, elevation, fov_horizontal, fov_vertical
            skip_still_frames: Skip static sky chunks
            apply_overlay: Burn flight data HUD on clips

        Returns:
            List of processed detection records
        """
        processed = []

        for chunk in chunks:
            try:
                # Step 1: Still-frame check
                if skip_still_frames and is_still_frame_chunk(chunk["chunk_path"]):
                    logger.debug(f"Skipping still-frame chunk: {chunk['chunk_path']}")
                    continue

                # Step 2: Preprocess chunk
                preprocessed_path = preprocess_chunk(
                    chunk["chunk_path"],
                    target_resolution=480,
                    target_fps=5,
                )

                # Step 3: Extract representative frame for CV
                frame = self._extract_key_frame(preprocessed_path)

                # Step 4: Run CV detection
                detections = self.contrail_detector.detect(frame)

                if not detections:
                    logger.debug(f"No detections in chunk: {chunk['chunk_path']}")
                    continue

                # Step 5: Process each detection
                for detection in detections:
                    detection_record = await self._process_single_detection(
                        detection=detection,
                        chunk=chunk,
                        camera_id=camera_id,
                        camera_metadata=camera_metadata,
                        apply_overlay=apply_overlay,
                    )
                    processed.append(detection_record)

            except Exception as e:
                logger.error(f"Error processing chunk {chunk['chunk_path']}: {e}")
                continue

        return processed

    async def _process_single_detection(
        self,
        detection: ContrailDetection,
        chunk: Dict,
        camera_id: str,
        camera_metadata: Dict,
        apply_overlay: bool,
    ) -> Dict:
        """Process a single detection through the full pipeline."""

        # Calculate azimuth/elevation from pixel coordinates
        az, el = pixel_to_az_el(
            x=detection.start_x,
            y=detection.start_y,
            width=1920,
            height=1080,
            cam_azimuth=camera_metadata.get("azimuth", 0),
            cam_elevation=camera_metadata.get("elevation", 0),
            fov_h=camera_metadata.get("fov_horizontal", 60),
            fov_v=camera_metadata.get("fov_vertical", 40),
        )

        # Estimate position
        est_lat, est_lon = estimate_position_single(
            cam_lat=camera_metadata["latitude"],
            cam_lon=camera_metadata["longitude"],
            cam_alt=camera_metadata["altitude"],
            az_obj=az,
            el_obj=el,
            assumed_alt=10000,
        )

        # Correlate with flights
        timestamp = datetime.fromtimestamp(
            chunk.get("start_time", 0),
            tz=timezone.utc
        )
        flight_match = await self.flight_service.get_flights_near_position(
            lat=est_lat,
            lon=est_lon,
            radius_km=10,
            limit=5,
        )

        icao24 = flight_match[0]["icao24"] if flight_match else None
        callsign = flight_match[0].get("callsign") if flight_match else None

        # Enhance with FR24 data if available and flight matched
        fr24_metadata = {}
        if icao24 and self.fr24_service:
            try:
                fr24_enrichment = await asyncio.to_thread(
                    self.fr24_service.enrich_flight_cache_entry,
                    icao24,
                )

                if fr24_enrichment:
                    fr24_metadata = {
                        "fr24_id": fr24_enrichment.get("fr24_id"),
                        "painted_as": fr24_enrichment.get("painted_as"),
                        "operating_as": fr24_enrichment.get("operating_as"),
                        "origin_icao": fr24_enrichment.get("origin_icao"),
                        "origin_iata": fr24_enrichment.get("origin_iata"),
                        "destination_icao": fr24_enrichment.get("destination_icao"),
                        "destination_iata": fr24_enrichment.get("destination_iata"),
                        "flight_track": fr24_enrichment.get("flight_track"),
                        "data_sources": fr24_enrichment.get("data_sources", ["fr24"]),
                    }

                    if fr24_enrichment.get("callsign") and not callsign:
                        callsign = fr24_enrichment.get("callsign")

            except Exception as e:
                logger.warning(f"FR24 enrichment failed for {icao24}: {e}")

        # Build enhanced metadata for archive
        archive_metadata = {
            "source_file": chunk["source_file"],
            "start_time": chunk["start_time"],
            "end_time": chunk["end_time"],
            "camera_id": camera_id,
            "camera_name": camera_metadata.get("name", "unknown"),
            "camera_lat": camera_metadata["latitude"],
            "camera_lon": camera_metadata["longitude"],
            "camera_alt": camera_metadata["altitude"],
            "detection_type": "contrail",
            "pixel_x": detection.start_x,
            "pixel_y": detection.start_y,
            "azimuth": az,
            "elevation": el,
            "estimated_lat": est_lat,
            "estimated_lon": est_lon,
            "estimated_alt": 10000,
            "confidence": detection.confidence,
            "contrail_vector": detection.to_dict(),
            "icao24": icao24,
            "callsign": callsign,
            "correlation_score": self._calculate_correlation_score(
                flight_match, fr24_metadata, est_lat, est_lon
            ),
            "position_method": "single_camera",
            "overlay_applied": False,
            # FR24-specific metadata
            "fr24_id": fr24_metadata.get("fr24_id"),
            "painted_as": fr24_metadata.get("painted_as"),
            "operating_as": fr24_metadata.get("operating_as"),
            "flight_origin": fr24_metadata.get("origin_iata") or fr24_metadata.get("origin_icao"),
            "flight_destination": fr24_metadata.get("destination_iata") or fr24_metadata.get("destination_icao"),
            "flight_track_points": len(fr24_metadata.get("flight_track", [])),
            "data_sources": fr24_metadata.get("data_sources", ["opensky"] if flight_match else []),
        }

        # Generate chunk ID (needed for overlay and archival)
        chunk_id = self._generate_chunk_id(chunk["source_file"], chunk["start_time"])

        # Apply overlay if requested and flight matched
        if apply_overlay and icao24:
            overlay_dir = tempfile.mkdtemp(prefix="chemtrail_overlay_")
            overlay_path = Path(overlay_dir) / f"{chunk_id}_overlay.mp4"
            flight_meta = {
                "icao24": icao24,
                "callsign": callsign,
                "timestamp": timestamp,
                "latitude": est_lat,
                "longitude": est_lon,
                "altitude": flight_match[0]["position"].get("alt") if flight_match else None,
                "velocity": flight_match[0]["position"].get("velocity") if flight_match else None,
                "heading": flight_match[0]["position"].get("heading") if flight_match else None,
            }
            result_path = apply_flight_overlay(
                input_path=chunk["chunk_path"],
                output_path=overlay_path,
                flight_metadata=flight_meta,
            )
            archive_metadata["overlay_applied"] = True
            archive_metadata["clip_path"] = result_path

        # Embed and archive
        embedding = self._embed_chunk(chunk["chunk_path"])

        self.vector_store.add_detection(
            chunk_id=chunk_id,
            embedding=embedding,
            metadata=archive_metadata,
        )

        logger.info(
            f"Archived detection: {detection.detection_type} "
            f"(confidence: {detection.confidence:.2f})"
        )

        return {
            "chunk_id": chunk_id,
            "detection": detection,
            "metadata": archive_metadata,
        }

    def _embed_chunk(self, chunk_path: str) -> List[float]:
        """Embed a video chunk (synchronous - delegates to embedder)."""
        return self.embedder.embed_video_chunk(chunk_path, verbose=False)

    def _calculate_correlation_score(
        self,
        flight_match: List[Dict],
        fr24_metadata: Dict,
        est_lat: float,
        est_lon: float,
    ) -> float:
        """
        Calculate correlation score based on flight match quality.

        Args:
            flight_match: List of matched flights from OpenSky
            fr24_metadata: Enrichment data from FR24
            est_lat: Estimated latitude of detection
            est_lon: Estimated longitude of detection

        Returns:
            Correlation score 0.0-1.0
        """
        if not flight_match:
            return 0.0

        base_score = 0.7

        if fr24_metadata.get("fr24_id"):
            base_score += 0.15

        if fr24_metadata.get("flight_track"):
            track = fr24_metadata["flight_track"]
            for point in track[:10]:
                track_lat = point.get("lat", 0)
                track_lon = point.get("lon", 0)
                distance = ((est_lat - track_lat) ** 2 + (est_lon - track_lon) ** 2) ** 0.5
                if distance < 0.1:
                    base_score += 0.15
                    break

        return min(base_score, 1.0)

    def _extract_key_frame(self, video_path: str) -> np.ndarray:
        """Extract middle frame from video chunk for CV processing."""
        import cv2

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames == 0:
            cap.release()
            raise ValueError(f"No frames found in {video_path}")

        # Go to middle frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise ValueError(f"Could not extract frame from {video_path}")

        return frame

    def _generate_chunk_id(self, source_file: str, start_time: float) -> str:
        """Generate deterministic chunk ID."""
        raw = f"{source_file}:{start_time}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def rtsp_to_segment(
    stream_url: str,
    duration_seconds: int = 10,
    output_dir: Optional[str] = None,
) -> Optional[Dict]:
    """Capture RTSP stream for N seconds then return segment info.

    Helper function for continuous stream ingestion.

    Args:
        stream_url: RTSP or MJPEG stream URL
        duration_seconds: Duration to capture in seconds
        output_dir: Directory for segment file (temp dir if None)

    Returns:
        Dict with chunk_path, source_file, start_time, end_time
        or None on failure
    """
    import time

    output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="chemtrail_"))
    output_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_exe = _get_ffmpeg_executable()
    chunk_path = output_dir / f"segment_{int(time.time())}.mp4"

    result = subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-rtsp_transport", "tcp",
            "-i", stream_url,
            "-t", str(duration_seconds),
            "-c", "copy",
            str(chunk_path),
        ],
        capture_output=True,
        check=False,
    )

    if result.returncode == 0 and chunk_path.exists():
        return {
            "chunk_path": str(chunk_path),
            "source_file": stream_url,
            "start_time": 0.0,
            "end_time": duration_seconds,
        }

    logger.error(f"Failed to capture RTSP segment: {result.stderr}")
    return None
