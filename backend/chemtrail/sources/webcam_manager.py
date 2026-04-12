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

"""Live Webcam Feed Acquisition Manager.

Responsibilities:
1. Manage connections to RTSP/MJPEG/HLS streams
2. Monitor stream health and auto-reconnect
3. Capture continuous segments for processing
4. Handle multiple concurrent streams
5. Integrate with public webcam APIs (Windy.com, etc.)
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio
import subprocess
import hashlib

import httpx

from common.common import logger


class StreamType(Enum):
    """Supported stream protocol types."""
    RTSP = "rtsp"
    MJPEG = "mjpeg"
    HLS = "hls"
    YOUTUBE = "youtube"


@dataclass
class WebcamSource:
    """Configuration for a webcam source.

    Attributes:
        name: Human-readable camera name
        url: Stream URL (RTSP, MJPEG, HLS, or YouTube)
        stream_type: Protocol type
        latitude: Camera latitude (WGS84 decimal degrees)
        longitude: Camera longitude (WGS84 decimal degrees)
        altitude: Camera altitude in meters AMSL
        azimuth: Camera heading (0-360, N=0, E=90)
        elevation: Camera tilt (-90 to 90, 0=horizon)
        fov_horizontal: Horizontal field of view in degrees
        fov_vertical: Vertical field of view in degrees
        is_sky_facing: Whether camera is pointed at sky
        tags: Custom tags for organization
    """
    name: str
    url: str
    stream_type: StreamType
    latitude: float
    longitude: float
    altitude: float
    azimuth: float = 0.0
    elevation: float = 0.0
    fov_horizontal: Optional[float] = None
    fov_vertical: Optional[float] = None
    is_sky_facing: bool = True
    tags: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Generate unique ID from URL."""
        return hashlib.sha256(self.url.encode()).hexdigest()[:16]


@dataclass
class StreamHealth:
    """Current health metrics for a stream."""
    status: str  # live, error, offline
    uptime_seconds: float
    segment_count: int
    last_segment_time: datetime
    error_message: Optional[str] = None
    reconnect_count: int = 0


class WebcamManager:
    """
    Manages multiple live webcam streams.

    Usage:
        manager = WebcamManager()
        await manager.add_source(source)
        await manager.capture_segment(source, duration=10, output_dir="/tmp")

        # Or run continuously
        async with WebcamManager() as manager:
            await manager.run_forever()
    """

    STALE_THRESHOLD_SECONDS = 120  # 2 minutes without segment = stale

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._sources: Dict[str, WebcamSource] = {}
        self._health: Dict[str, StreamHealth] = {}
        self._running = False
        self._windy_api_key: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def initialize(self, windy_api_key: Optional[str] = None) -> None:
        """Initialize manager with optional API clients."""
        self._windy_api_key = windy_api_key
        self._http_client = httpx.AsyncClient(timeout=10.0)
        logger.info("WebcamManager initialized")

    async def close(self) -> None:
        """Close HTTP clients."""
        if self._http_client:
            await self._http_client.aclose()
        logger.info("WebcamManager closed")

    # ==================== Source Management ====================

    def add_manual_source(
        self,
        name: str,
        url: str,
        stream_type: StreamType,
        latitude: float,
        longitude: float,
        altitude: float,
        azimuth: float = 0.0,
        elevation: float = 0.0,
        fov_horizontal: Optional[float] = None,
        fov_vertical: Optional[float] = None,
        is_sky_facing: bool = True,
        tags: Optional[List[str]] = None,
    ) -> WebcamSource:
        """Manually add a webcam source."""
        source = WebcamSource(
            name=name,
            url=url,
            stream_type=stream_type,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            azimuth=azimuth,
            elevation=elevation,
            fov_horizontal=fov_horizontal,
            fov_vertical=fov_vertical,
            is_sky_facing=is_sky_facing,
            tags=tags or [],
        )
        self._sources[source.id] = source
        self._health[source.id] = StreamHealth(
            status="offline",
            uptime_seconds=0,
            segment_count=0,
            last_segment_time=datetime.now(timezone.utc),
        )
        logger.info(f"Added manual source: {name} ({source.id})")
        return source

    def get_all_sources(self) -> List[WebcamSource]:
        """Get all registered sources."""
        return list(self._sources.values())

    def get_sources_near(
        self,
        lat: float,
        lon: float,
        radius_km: float,
    ) -> List[WebcamSource]:
        """Get sources within radius of location."""
        from math import radians, cos, sin, asin, sqrt

        def haversine(lat1, lon1, lat2, lon2):
            r = 6371  # Earth radius in km
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            return 2 * asin(sqrt(a)) * r

        return [
            source for source in self._sources.values()
            if haversine(lat, lon, source.latitude, source.longitude) <= radius_km
        ]

    def remove_source(self, source_id: str) -> bool:
        """Remove a source."""
        if source_id in self._sources:
            del self._sources[source_id]
            if source_id in self._health:
                del self._health[source_id]
            logger.info(f"Removed source: {source_id}")
            return True
        return False

    # ==================== Public API Discovery ====================

    async def discover_windy_camels(
        self,
        api_key: str,
        bbox: Optional[Dict[str, float]] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: float = 50,
    ) -> List[WebcamSource]:
        """Discover webcams from Windy.com API.

        Args:
            api_key: Windy.com API key
            bbox: Bounding box {north, south, east, west}
            lat, lon: Center point for radius search
            radius_km: Search radius in km

        Returns:
            List of WebcamSource objects
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=10.0)

        base_url = "https://api.windy.com/api/webcams"
        params = {"apikey": api_key, "lang": "en", "fields": "location,player"}

        # Build URL based on search type
        if lat is not None and lon is not None:
            url = f"{base_url}/nearby/{lat},{lon},{radius_km}"
        elif bbox:
            url = f"{base_url}/bbox/{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"
        else:
            raise ValueError("Either lat/lon/radius or bbox must be provided")

        try:
            response = await self._http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            sources = []
            for item in data.get("result", {}).get("webcams", []):
                if item.get("status") != "active":
                    continue

                location = item.get("location", {})
                player = item.get("player", {})

                # Try to get stream URL
                stream_url = player.get("live", {}).get("embed", "")

                if not stream_url:
                    continue

                source = WebcamSource(
                    name=location.get("city", "Unknown"),
                    url=stream_url,
                    stream_type=StreamType.HLS,
                    latitude=location.get("latitude", 0),
                    longitude=location.get("longitude", 0),
                    altitude=0,
                    is_sky_facing=True,
                    tags=["windy", "public"],
                )
                sources.append(source)

            logger.info(f"Discovered {len(sources)} webcams from Windy.com")
            return sources

        except httpx.HTTPError as e:
            logger.error(f"Windy.com API error: {e}")
            return []

    async def discover_opensky_webcams(self) -> List[WebcamSource]:
        """Discover webcams from OpenSky network.

        Note: OpenSky doesn't have a dedicated webcam API,
        this is a placeholder for future integration.
        """
        logger.warning("OpenSky webcam discovery not yet implemented")
        return []

    # ==================== Stream Capture ====================

    def get_stream_url(self, source: WebcamSource) -> str:
        """Get current stream URL for a source."""
        return source.url

    async def capture_segment(
        self,
        source: WebcamSource,
        duration: int = 10,
        output_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Capture a segment from a webcam stream.

        Args:
            source: Webcam source to capture
            duration: Duration in seconds
            output_dir: Output directory (temp dir if None)

        Returns:
            Dict with segment_path, source_id, duration, timestamp
            or None on failure
        """
        import tempfile
        import time

        output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="chemtrail_webcam_"))
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build output path
        timestamp = int(time.time())
        segment_path = output_dir / f"{source.id}_{timestamp}.mp4"

        # Build ffmpeg command
        cmd = self._build_ffmpeg_command(source, duration, str(segment_path))

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=duration + 30,  # Allow extra time for startup
            )

            if result.returncode == 0 and segment_path.exists():
                # Update health
                if source.id in self._health:
                    health = self._health[source.id]
                    health.segment_count += 1
                    health.last_segment_time = datetime.now(timezone.utc)
                    health.status = "live"

                logger.info(f"Captured segment: {segment_path}")
                return {
                    "segment_path": str(segment_path),
                    "source_id": source.id,
                    "source_name": source.name,
                    "duration": duration,
                    "timestamp": timestamp,
                }
            else:
                logger.error(f"Failed to capture segment: {stderr.decode()}")
                return None

        except asyncio.TimeoutError:
            logger.error(f"Capture timeout for {source.name}")
            return None
        except Exception as e:
            logger.error(f"Capture error for {source.name}: {e}")
            return None

    def _build_ffmpeg_command(
        self,
        source: WebcamSource,
        duration: int,
        output_path: str,
    ) -> List[str]:
        """Build ffmpeg command for stream type."""
        cmd = [
            "ffmpeg",
            "-y",
            "-re",  # Read at native frame rate
        ]

        # Stream-specific options
        if source.stream_type == StreamType.RTSP:
            cmd.extend(["-rtsp_transport", "tcp"])
        elif source.stream_type == StreamType.YOUTUBE:
            cmd.extend(["-user_agent", "Mozilla/5.0"])
        elif source.stream_type == StreamType.HLS:
            cmd.extend(["-strict", "experimental"])

        # Input and output
        cmd.extend([
            "-i", source.url,
            "-t", str(duration),
            "-c", "copy",
            output_path,
        ])

        return cmd

    # ==================== Health Monitoring ====================

    def check_source_health(self, source: WebcamSource) -> StreamHealth:
        """Check current health of a stream."""
        if source.id not in self._health:
            return StreamHealth(
                status="offline",
                uptime_seconds=0,
                segment_count=0,
                last_segment_time=datetime.now(timezone.utc),
            )

        health = self._health[source.id]

        # Check if stream is stale
        time_since_segment = (
            datetime.now(timezone.utc) - health.last_segment_time
        ).total_seconds()

        if time_since_segment > self.STALE_THRESHOLD_SECONDS:
            if health.status == "live":
                health.status = "error"
                health.error_message = f"No segments for {time_since_segment:.0f}s"

        return health

    async def run_forever(self, capture_interval: int = 30) -> None:
        """Run stream manager continuously.

        Args:
            capture_interval: Seconds between captures
        """
        self._running = True
        logger.info(f"Starting continuous capture with {len(self._sources)} sources")

        while self._running:
            for source in self._sources.values():
                if not self._running:
                    break

                health = self.check_source_health(source)
                if health.status == "error":
                    logger.warning(f"Source {source.name} has health issues: {health.error_message}")

            await asyncio.sleep(capture_interval)

    async def stop(self) -> None:
        """Stop continuous capture."""
        self._running = False
        logger.info("Stopping WebcamManager")

    async def __aenter__(self) -> "WebcamManager":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._running = False
        await self.close()
