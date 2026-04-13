#!/usr/bin/env python
"""Import pipeline detections from JSON into the ChemtrailDetections database table.

Creates a virtual 'YouTube Archive' camera as the source for all imported detections.
"""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import asyncio
from sqlalchemy import select
from db import AsyncSessionLocal, engine
from db.models import ChemtrailCameras, ChemtrailDetections, CameraType, DetectionType
from db.models import AwareDateTime


async def import_detections():
    """Import all pipeline detections into the database."""
    async with AsyncSessionLocal() as session:
        # Check if YouTube Archive camera exists
        result = await session.execute(
            select(ChemtrailCameras).where(ChemtrailCameras.name == "YouTube Archive")
        )
        camera = result.scalar_one_or_none()

        if not camera:
            camera = ChemtrailCameras(
                id=uuid.uuid4(),
                name="YouTube Archive",
                url="",
                type=CameraType.MJPEG,
                latitude=39.7392,  # Default: Denver area
                longitude=-104.9903,
                altitude=1609,
                azimuth=0.0,
                elevation=45.0,
                fov_horizontal=90.0,
                fov_vertical=60.0,
                image_width=1920,
                image_height=1080,
                status="active",
                extra_data={"source": "youtube_pipeline", "note": "Virtual camera for imported detections"},
            )
            session.add(camera)
            await session.commit()
            print(f"Created virtual camera: YouTube Archive (id={camera.id})")

        # Load detections
        det_file = Path(__file__).parent.parent / "data" / "chemtrail_samples" / "detections" / "all_detections_embedded.json"
        with open(det_file) as f:
            detections = json.load(f)

        imported = 0
        for det in detections:
            video_name = det["source_video"]
            chunk_index = det["chunk_index"]

            # Check if already imported
            existing = await session.execute(
                select(ChemtrailDetections).where(
                    ChemtrailDetections.camera_id == camera.id,
                    ChemtrailDetections.image_path == f"{video_name}/chunk_{chunk_index:03d}_detected.jpg",
                )
            )
            if existing.scalar_one_or_none():
                print(f"  SKIP: {video_name} chunk {chunk_index} (already imported)")
                continue

            # Parse timestamp from video name if possible, otherwise use now
            try:
                # Try to extract date from video name
                timestamp = datetime.now()
            except Exception:
                timestamp = datetime.now()

            record = ChemtrailDetections(
                id=uuid.uuid4(),
                camera_id=camera.id,
                icao24=None,
                detection_type=DetectionType.CONTRAIL,
                timestamp=timestamp,
                processing_latency_ms=0,
                image_path=f"{video_name}/chunk_{chunk_index:03d}_detected.jpg",
                image_hash=None,
                pixel_x=det.get("start_pos", [0, 0])[0] if isinstance(det.get("start_pos"), list) else 0,
                pixel_y=det.get("start_pos", [0, 0])[1] if isinstance(det.get("start_pos"), list) else 0,
                bounding_box=None,
                azimuth=0.0,
                elevation=0.0,
                estimated_latitude=None,
                estimated_longitude=None,
                estimated_altitude=None,
                position_method="pipeline",
                confidence=det["confidence"],
                correlation_score=None,
                contrail_vector=None,
                processing_metadata={
                    "video_name": video_name,
                    "chunk_index": chunk_index,
                    "start_time": det.get("start_time", 0),
                    "end_time": det.get("end_time", 0),
                    "angle_deg": det["angle_deg"],
                    "length_px": det["length_px"],
                    "num_lines": det["num_lines"],
                    "source": "youtube_pipeline",
                },
            )
            session.add(record)
            imported += 1

        await session.commit()
        print(f"\nImported {imported} new detections (total in file: {len(detections)})")
        print(f"Camera: {camera.name} (id={camera.id})")


if __name__ == "__main__":
    asyncio.run(import_detections())
    print("Done!")
