# Chemtrail Webcam Tracker - Pipeline Quickstart Guide
**Version:** 2.0.0
**Last Updated:** 2026-04-11

---

## Complete End-to-End Flow in 5 Minutes

This quickstart guide walks you through the complete Phase 2 pipeline:

1. Add a webcam source
2. Start live detection pipeline
3. Search detections
4. View overlay clips
5. Run historical batch analysis

**Prerequisites:**
- Python 3.10+
- ffmpeg installed
- Database configured

---

## Step 1: Add a Webcam Source (1 minute)

### Quick Setup

```python
import asyncio
from datetime import datetime, timezone
from chemtrail.sources import WebcamManager, StreamType

async def add_webcam():
    # Initialize webcam manager
    manager = WebcamManager()
    await manager.initialize()

    # Add a sky-facing webcam
    source = manager.add_manual_source(
        name="Seattle Downtown Sky Cam",
        url="rtsp://192.168.1.100:554/stream",  # Replace with your stream URL
        stream_type=StreamType.RTSP,
        latitude=47.6062,
        longitude=-122.3321,
        altitude=100,
        azimuth=180,       # Facing south
        elevation=45,      # Pointed up at 45 degrees
        is_sky_facing=True,
        tags=["seattle", "downtown"],
    )

    print(f"Added webcam: {source.name}")
    print(f"Source ID: {source.id}")
    print(f"Location: ({source.latitude}, {source.longitude})")

    return manager, source

# Run it
# manager, source = asyncio.run(add_webcam())
```

### Using a Test Video Instead

If you don't have a live stream, use a test video file:

```python
# Verify you have a test video
from chemtrail.sources import HistoricalIngestor

ingestor = HistoricalIngestor()

# Scan for test videos
result = ingestor.scan_directory("C:/Videos/Test", recursive=False)
print(f"Found {result.count} test videos")
for path in result.found:
    print(f"  - {path}")
```

---

## Step 2: Start Live Detection Pipeline (2 minutes)

### Initialize All Services

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from chemtrail.sources import (
    WebcamManager, StreamType,
    HistoricalIngestor,
    VideoCatalog,
    WeatherService,
    PipelineOrchestrator,
    PipelineConfig,
)
from chemtrail.archive.vector_store import ChemtrailVectorStore
from chemtrail.archive.detection_service import DetectionService

# Create database session
engine = create_async_engine("sqlite+aiosqlite:///backend/detections.db")
session = AsyncSession(bind=engine)

# Initialize vector store
vector_store = ChemtrailVectorStore()

# Initialize all services
webcam_manager = WebcamManager()
await webcam_manager.initialize()

historical_ingestor = HistoricalIngestor(db_session=session, vector_store=vector_store)
video_catalog = VideoCatalog(session=session, vector_store=vector_store)
await video_catalog.initialize()

weather_service = WeatherService()
detection_service = DetectionService()

# Configure pipeline
config = PipelineConfig(
    max_concurrent_jobs=2,
    enable_weather_enrichment=True,
    enable_quality_scoring=True,
    skip_still_frames=True,
    apply_overlay=True,        # Burn flight telemetry on clips
    chunk_duration_seconds=30,
    chunk_overlap_seconds=5,
)

# Create and start orchestrator
orchestrator = PipelineOrchestrator(
    session=session,
    webcam_manager=webcam_manager,
    historical_ingestor=historical_ingestor,
    video_catalog=video_catalog,
    detection_service=detection_service,
    weather_service=weather_service,
    config=config,
)

await orchestrator.start()
print("Pipeline started!")
```

### Capture and Process a Segment

```python
# Capture a 30-second segment
segment = await webcam_manager.capture_segment(
    source=source,
    duration=30,
    output_dir="C:/temp/chemtrail_segments",
)

if segment:
    print(f"Captured segment: {segment['segment_path']}")

    # Submit for processing
    job_id = await orchestrator.submit_job(
        source_path=segment["segment_path"],
        source_type="webcam",
        priority=0,
        metadata={
            "camera_id": source.id,
            "camera_name": source.name,
            "latitude": source.latitude,
            "longitude": source.longitude,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(f"Submitted job: {job_id}")
```

### Wait for Processing

```python
# Wait for job completion (with 5-minute timeout)
try:
    status = await orchestrator.wait_for_job(job_id, timeout_seconds=300)

    print(f"\nJob Status: {status['status']}")
    print(f"Current Stage: {status['current_stage']}")

    if status['status'] == 'completed':
        detections = status.get('stage_results', {}).get('detections', [])
        print(f"Detections found: {len(detections)}")

        for det in detections[:5]:
            print(f"  - {det.get('flight_icao', 'Unknown')}: {det.get('confidence', 0):.2f}")

except TimeoutError:
    print("Job still processing...")
```

---

## Step 3: Search Detections (1 minute)

### Search by Natural Language

```python
from chemtrail.archive.searcher import search_detections

# Semantic search
results = search_detections(
    query="contrails over Seattle",
    vector_store=vector_store,
    n_results=10,
)

print(f"Found {len(results)} matching detections:")
for r in results:
    print(f"  Score: {r['score']:.2f}")
    print(f"    Flight: {r.get('callsign', 'N/A')}")
    print(f"    Time: {r.get('timestamp', 'N/A')}")
    print(f"    Camera: {r.get('camera_name', 'N/A')}")
```

### Filter by Flight

```python
# Search by specific flight ICAO code
flight_results = vector_store._collection.get(
    where={
        "flight_icao": {"$eq": "4b1a02"}
    },
    limit=20,
)

print(f"Detections for flight 4b1a02: {len(flight_results['ids'])}")
```

### Filter by Date Range

```python
from datetime import datetime, timedelta

# Get detections from last 24 hours
results = search_detections(
    query="contrail",
    vector_store=vector_store,
    n_results=50,
)

# Filter by timestamp in Python
one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
recent = [
    r for r in results
    if r.get('timestamp') and
    datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) > one_day_ago
]

print(f"Recent detections (last 24h): {len(recent)}")
```

### Search Video Catalog

```python
# Search catalog by quality
high_quality = video_catalog.search(
    min_quality=70,
    limit=20,
)

print(f"High-quality videos: {len(high_quality)}")
for v in high_quality[:5]:
    print(f"  {v['camera_name']}: {v['resolution']} (score: {v['quality_score']})")
```

---

## Step 4: View Overlay Clips (1 minute)

### Access Detection Clips with Flight Overlay

```python
from pathlib import Path

# Get output directory for overlay clips
overlay_dir = Path("C:/temp/chemtrail_overlays")
overlay_dir.mkdir(parents=True, exist_ok=True)

# Find overlay clips
overlay_clips = list(overlay_dir.glob("*.mp4"))

print(f"Available overlay clips: {len(overlay_clips)}")
for clip in overlay_clips[:5]:
    print(f"  - {clip.name}")
    print(f"    Size: {clip.stat().st_size / 1_000_000:.1f} MB")
```

### Playback Overlay Clip

```python
# Use ffplay to preview
import subprocess

if overlay_clips:
    clip_path = overlay_clips[0]
    print(f"Playing: {clip_path.name}")

    # Launch ffplay (press 'q' to quit)
    subprocess.run(["ffplay", str(clip_path)])
```

### Generate Overlay for Specific Detection

```python
from chemtrail.archive.telemetry_overlay import TelemetryOverlay

# Create overlay for a detection
overlay = TelemetryOverlay()

# Assuming you have detection data
detection_data = {
    "flight_icao": "4b1a02",
    "flight_callsign": "SWA1234",
    "altitude_ft": 35000,
    "ground_speed_kts": 450,
    "vertical_rate_fpm": 0,
    "heading": 270,
    "latitude": 47.6062,
    "longitude": -122.3321,
}

# Generate overlay
output_path = await overlay.create_overlay(
    video_path=str(overlay_clips[0]) if overlay_clips else "path/to/video.mp4",
    detection=detection_data,
    output_path=str(overlay_dir / "overlay_output.mp4"),
)

print(f"Overlay created: {output_path}")
```

### Overlay HUD Elements

The flight telemetry overlay includes:

```
┌─────────────────────────────────────────────────┐
│ SWA1234 (4b1a02)                 ALT: 35,000 ft │
│ Boeing 737-800                   SPD: 450 kts   │
│ Heading: 270 deg                 V/S: 0 fpm     │
│ Pos: 47.6062, -122.3321                         │
└─────────────────────────────────────────────────┘
```

---

## Step 5: Run Historical Batch Analysis (1 minute)

### Batch Process Video Archive

```python
# Run pipeline on historical videos
archive_dirs = [
    "C:/Videos/Chemtrail_Archive/April_2026",
]

results = await orchestrator.run_historical_pipeline(
    directories=archive_dirs,
    recursive=True,
)

print(f"\n=== Batch Analysis Results ===")
print(f"Total videos found: {results['stats']['total_videos']}")
print(f"Jobs submitted: {results['stats']['submitted_jobs']}")
print(f"Errors: {len(results['errors'])}")

if results['errors']:
    print("\nErrors encountered:")
    for err in results['errors'][:5]:
        print(f"  - {err}")
```

### Monitor Batch Progress

```python
# Check status of all batch jobs
all_jobs = orchestrator.get_all_jobs_status()

completed = sum(1 for j in all_jobs if j['status'] == 'completed')
running = sum(1 for j in all_jobs if j['status'] == 'running')
pending = sum(1 for j in all_jobs if j['status'] == 'pending')
failed = sum(1 for j in all_jobs if j['status'] == 'failed')

print(f"\n=== Batch Progress ===")
print(f"Completed: {completed}")
print(f"Running: {running}")
print(f"Pending: {pending}")
print(f"Failed: {failed}")
```

### Wait for All Jobs

```python
import asyncio

# Wait for all jobs to complete
async def wait_for_all_jobs(orchestrator, timeout_per_job=600):
    pending_jobs = [
        j for j in orchestrator._jobs.values()
        if j.status not in ('completed', 'failed', 'cancelled')
    ]

    print(f"Waiting for {len(pending_jobs)} jobs...")

    for job in pending_jobs:
        try:
            status = await orchestrator.wait_for_job(
                job.job_id,
                timeout_seconds=timeout_per_job,
            )
            print(f"  {job.job_id[:8]}... : {status['status']}")
        except TimeoutError:
            print(f"  {job.job_id[:8]}... : timeout")

# Usage
# await wait_for_all_jobs(orchestrator)
```

### Generate Summary Report

```python
# After all jobs complete, generate summary
def generate_summary(orchestrator):
    all_jobs = list(orchestrator._jobs.values())

    completed_jobs = [j for j in all_jobs if j.status.value == 'completed']
    total_detections = sum(
        len(j.stage_results.get('detections', []))
        for j in completed_jobs
    )

    return {
        'total_jobs': len(all_jobs),
        'completed': len(completed_jobs),
        'failed': len([j for j in all_jobs if j.status.value == 'failed']),
        'total_detections': total_detections,
        'detections_per_job': total_detections / len(completed_jobs) if completed_jobs else 0,
    }

summary = generate_summary(orchestrator)

print(f"\n=== Analysis Summary ===")
print(f"Total jobs: {summary['total_jobs']}")
print(f"Completed: {summary['completed']}")
print(f"Failed: {summary['failed']}")
print(f"Total detections: {summary['total_detections']}")
print(f"Average per job: {summary['detections_per_job']:.1f}")
```

---

## Complete Script: 5-Minute Pipeline

Here's the complete end-to-end script:

```python
"""
Chemtrail Phase 2 - Complete 5-Minute Pipeline

This script demonstrates the full Phase 2 workflow:
1. Add webcam source
2. Start detection pipeline
3. Search detections
4. View overlay clips
5. Run batch analysis
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from chemtrail.sources import (
    WebcamManager, StreamType,
    HistoricalIngestor,
    VideoCatalog,
    WeatherService,
    PipelineOrchestrator,
    PipelineConfig,
)
from chemtrail.archive.vector_store import ChemtrailVectorStore
from chemtrail.archive.detection_service import DetectionService
from chemtrail.archive.searcher import search_detections


async def main():
    print("=" * 60)
    print("CHEMTRAIL PHASE 2 - COMPLETE PIPELINE DEMO")
    print("=" * 60)

    # ========== SETUP ==========
    print("\n[SETUP] Initializing services...")

    # Database
    engine = create_async_engine("sqlite+aiosqlite:///backend/detections.db")
    session = AsyncSession(bind=engine)

    # Services
    vector_store = ChemtrailVectorStore()
    webcam_manager = WebcamManager()
    await webcam_manager.initialize()
    historical_ingestor = HistoricalIngestor(db_session=session, vector_store=vector_store)
    video_catalog = VideoCatalog(session=session, vector_store=vector_store)
    await video_catalog.initialize()
    weather_service = WeatherService()
    detection_service = DetectionService()

    # Pipeline config
    config = PipelineConfig(
        max_concurrent_jobs=2,
        enable_weather_enrichment=True,
        enable_quality_scoring=True,
        skip_still_frames=True,
        apply_overlay=True,
    )

    orchestrator = PipelineOrchestrator(
        session=session,
        webcam_manager=webcam_manager,
        historical_ingestor=historical_ingestor,
        video_catalog=video_catalog,
        detection_service=detection_service,
        weather_service=weather_service,
        config=config,
    )

    await orchestrator.start()
    print("[SETUP] Complete!")

    # ========== STEP 1: ADD WEBCAM ==========
    print("\n[STEP 1] Adding webcam source...")

    source = webcam_manager.add_manual_source(
        name="Demo Sky Cam",
        url="rtsp://192.168.1.100:554/stream",
        stream_type=StreamType.RTSP,
        latitude=47.6062,
        longitude=-122.3321,
        altitude=100,
        azimuth=180,
        elevation=45,
        is_sky_facing=True,
    )

    print(f"[STEP 1] Added: {source.name} (ID: {source.id})")

    # ========== STEP 2: START PIPELINE ==========
    print("\n[STEP 2] Starting live detection pipeline...")

    # Capture segment (or use existing video)
    test_video = "C:/Videos/test_sky.mp4"  # Replace with actual path

    if Path(test_video).exists():
        job_id = await orchestrator.submit_job(
            source_path=test_video,
            source_type="local",
            metadata={
                "camera_id": source.id,
                "latitude": source.latitude,
                "longitude": source.longitude,
            },
        )

        print(f"[STEP 2] Submitted job: {job_id}")

        # Wait for completion
        print("[STEP 2] Processing...")
        status = await orchestrator.wait_for_job(job_id, timeout_seconds=300)
        print(f"[STEP 2] Status: {status['status']}")

        if status['status'] == 'completed':
            detections = status['stage_results'].get('detections', [])
            print(f"[STEP 2] Found {len(detections)} detections")
    else:
        print(f"[STEP 2] Test video not found: {test_video}")
        print("           Create a test video or use a live stream")

    # ========== STEP 3: SEARCH DETECTIONS ==========
    print("\n[STEP 3] Searching detections...")

    results = search_detections(
        query="contrail",
        vector_store=vector_store,
        n_results=10,
    )

    print(f"[STEP 3] Found {len(results)} matching detections")
    for r in results[:3]:
        print(f"         Score: {r['score']:.2f} - {r.get('callsign', 'N/A')}")

    # ========== STEP 4: VIEW OVERLAY CLIPS ==========
    print("\n[STEP 4] Checking overlay clips...")

    overlay_dir = Path("C:/temp/chemtrail_overlays")
    if overlay_dir.exists():
        clips = list(overlay_dir.glob("*.mp4"))
        print(f"[STEP 4] Found {len(clips)} overlay clips")
        for clip in clips[:3]:
            print(f"         - {clip.name} ({clip.stat().st_size / 1_000_000:.1f} MB)")
    else:
        print("[STEP 4] No overlay clips yet")

    # ========== STEP 5: BATCH ANALYSIS ==========
    print("\n[STEP 5] Running historical batch analysis...")

    archive_dir = "C:/Videos/Chemtrail_Archive"
    if Path(archive_dir).exists():
        batch_results = await orchestrator.run_historical_pipeline(
            directories=[archive_dir],
            recursive=False,
        )

        print(f"[STEP 5] Videos found: {batch_results['stats']['total_videos']}")
        print(f"[STEP 5] Jobs submitted: {batch_results['stats']['submitted_jobs']}")
    else:
        print(f"[STEP 5] Archive directory not found: {archive_dir}")

    # ========== CLEANUP ==========
    print("\n[CLEANUP] Shutting down...")
    await orchestrator.stop()
    await webcam_manager.close()

    print("\n" + "=" * 60)
    print("PIPELINE DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Next Steps

After completing this quickstart:

1. **Add more cameras** - Register additional sky-facing webcams
2. **Configure schedules** - Set up automated capture intervals
3. **Fine-tune detection** - Adjust sensitivity thresholds
4. **Export results** - Generate reports and export detection data
5. **Integrate with UI** - Connect to the frontend detection browser

---

## Troubleshooting Quickstart

| Issue | Solution |
|-------|----------|
| ffmpeg not found | `choco install ffmpeg` or download from ffmpeg.org |
| Database errors | Check `.env` has correct `DATABASE_URL` |
| RTSP connection fails | Verify stream URL and network connectivity |
| No detections found | Check video has visible contrails; adjust detection thresholds |
| Job timeout | Increase `stage_timeout_seconds` in config |

For detailed troubleshooting, see `PHASE2_USER_GUIDE.md#troubleshooting`.

---

*Document Version: 2.0.0 | Last Updated: 2026-04-11*
