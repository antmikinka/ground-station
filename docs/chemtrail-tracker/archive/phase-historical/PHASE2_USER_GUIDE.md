# Chemtrail Webcam Tracker - Phase 2 User Guide
**Version:** 2.0.0
**Last Updated:** 2026-04-11

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Webcam Source Discovery and Configuration](#webcam-source-discovery-and-configuration)
4. [Historical Video Archive Import](#historical-video-archive-import)
5. [Live Detection Pipeline](#live-detection-pipeline)
6. [Batch Historical Analysis](#batch-historical-analysis)
7. [Searching and Browsing Results](#searching-and-browsing-results)
8. [Configuration Examples](#configuration-examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Phase 2 transforms the Chemtrail Webcam Tracker into a complete end-to-end footage management system. This guide covers:

- **Live webcam feed acquisition** from RTSP/MJPEG/HLS streams
- **Historical video ingestion** from local archives and YouTube
- **Intelligent video cataloging** with quality scoring and weather enrichment
- **Pipeline orchestration** for automated processing workflows
- **Search and browse** capabilities for detection results

### Phase 2 Capabilities

| Feature | Description |
|---------|-------------|
| **Webcam Management** | Discover, register, and manage live sky-facing webcam streams |
| **Historical Ingestor** | Scan and import video archives with metadata extraction |
| **Video Catalog** | Sort and filter videos by location, weather, quality, and date |
| **Weather Enrichment** | Auto-tag videos with historical weather data from Open-Meteo |
| **Pipeline Orchestrator** | End-to-end workflow from acquisition to archival |
| **Quality Scoring** | Automated video quality assessment for prioritization |

---

## Quick Start

### Prerequisites

Ensure you have the following installed:

```bash
# Python 3.10+
python --version

# ffmpeg (required for video processing)
ffmpeg -version

# Install Python dependencies
cd C:\Users\antmi\ground-station
pip install -r backend/requirements.txt
```

### Environment Configuration

Create or update your `.env` file:

```bash
# .env
DATABASE_URL=sqlite+aiosqlite:///backend/detections.db
CHEMTRAIL_DB_PATH=C:/Users/antmi/ground-station/backend/.chemtrail_db
GEMINI_API_KEY=your-gemini-api-key  # Optional, for semantic embeddings
```

### Basic Pipeline Setup

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from chemtrail.sources import (
    WebcamManager,
    HistoricalIngestor,
    VideoCatalog,
    WeatherService,
    PipelineOrchestrator,
    PipelineConfig,
)
from chemtrail.archive.vector_store import ChemtrailVectorStore
from chemtrail.archive.detection_service import DetectionService

# Initialize database session
engine = create_async_engine("sqlite+aiosqlite:///backend/detections.db")
session = AsyncSession(bind=engine)

# Initialize vector store
vector_store = ChemtrailVectorStore()

# Initialize services
webcam_manager = WebcamManager()
historical_ingestor = HistoricalIngestor(db_session=session, vector_store=vector_store)
video_catalog = VideoCatalog(session=session, vector_store=vector_store)
weather_service = WeatherService()
detection_service = DetectionService()

# Configure and start pipeline
config = PipelineConfig(
    max_concurrent_jobs=3,
    enable_weather_enrichment=True,
    enable_quality_scoring=True,
    skip_still_frames=True,
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
```

---

## Webcam Source Discovery and Configuration

### Adding Manual Webcam Sources

Register a webcam source with known stream URL:

```python
from chemtrail.sources import WebcamManager, StreamType

manager = WebcamManager()
await manager.initialize()

# Add a sky-facing webcam manually
source = manager.add_manual_source(
    name="Seattle Downtown Sky Cam",
    url="rtsp://camera.example.com:554/stream1",
    stream_type=StreamType.RTSP,
    latitude=47.6062,
    longitude=-122.3321,
    altitude=100,
    azimuth=180,        # Facing south
    elevation=45,       # Pointed 45 degrees up
    fov_horizontal=60,  # 60 degree horizontal FOV
    fov_vertical=40,    # 40 degree vertical FOV
    is_sky_facing=True, # Confirm sky-facing
    tags=["seattle", "downtown", "sky"],
)

print(f"Added source with ID: {source.id}")
```

### Supported Stream Types

| Type | Protocol | Example URL |
|------|----------|-------------|
| `StreamType.RTSP` | RTSP | `rtsp://user:pass@192.168.1.100:554/stream` |
| `StreamType.MJPEG` | MJPEG | `http://camera.example.com:8080/video.mjpeg` |
| `StreamType.HLS` | HLS (HTTP Live Streaming) | `http://camera.example.com/stream/playlist.m3u8` |
| `StreamType.YOUTUBE` | YouTube Live | `https://www.youtube.com/watch?v=VIDEO_ID` |

### Discovering Webcams from Windy.com API

Automatically discover public webcams in a geographic area:

```python
from chemtrail.sources import WebcamManager

manager = WebcamManager()
await manager.initialize(windy_api_key="YOUR_WINDY_API_KEY")

# Discover webcams near Seattle within 50km radius
sources = await manager.discover_windy_camels(
    api_key="YOUR_WINDY_API_KEY",
    lat=47.6062,
    lon=-122.3321,
    radius_km=50,
)

# Add discovered sources to manager
for source in sources:
    await manager.add_source(source)
    print(f"Discovered: {source.name} at ({source.latitude}, {source.longitude})")
```

### Discovering Webcams by Bounding Box

```python
# Discover webcams in a bounding box (Pacific Northwest)
sources = await manager.discover_windy_camels(
    api_key="YOUR_WINDY_API_KEY",
    bbox={
        "north": 49.0,
        "south": 45.0,
        "east": -120.0,
        "west": -125.0,
    },
)
```

### Listing and Filtering Sources

```python
# Get all registered sources
all_sources = manager.get_all_sources()
print(f"Total sources: {len(all_sources)}")

# Get sources near a location
nearby = manager.get_sources_near(
    lat=47.6062,
    lon=-122.3321,
    radius_km=25,
)
print(f"Sources within 25km: {len(nearby)}")

# Remove a source
manager.remove_source(source_id)
```

### Capturing Live Segments

```python
# Capture a 10-second segment from a webcam
segment = await manager.capture_segment(
    source=source,
    duration=10,          # Capture duration in seconds
    output_dir="/tmp/chemtrail_segments",
)

if segment:
    print(f"Captured: {segment['segment_path']}")
    print(f"Duration: {segment['duration']}s")
    print(f"Timestamp: {segment['timestamp']}")
```

### Running Continuous Capture

```python
# Run continuous capture with health monitoring
async with WebcamManager() as manager:
    await manager.add_source(source)
    await manager.run_forever(capture_interval=30)  # Capture every 30 seconds
```

### Example: Complete Webcam Setup

```python
import asyncio
from chemtrail.sources import WebcamManager, StreamType

async def setup_webcam_pipeline():
    manager = WebcamManager()
    await manager.initialize(windy_api_key="YOUR_API_KEY")

    # Add multiple cameras
    cameras = [
        {
            "name": "SEA Airport Runway Cam",
            "url": "rtsp://192.168.1.100:554/runway1",
            "lat": 47.4502,
            "lon": -122.3088,
            "altitude": 130,
            "azimuth": 160,
            "elevation": 30,
        },
        {
            "name": "Downtown Seattle Sky View",
            "url": "http://seattle-cam.example.com/video.mjpeg",
            "lat": 47.6062,
            "lon": -122.3321,
            "altitude": 100,
            "azimuth": 180,
            "elevation": 45,
        },
    ]

    for cam in cameras:
        source = manager.add_manual_source(
            name=cam["name"],
            url=cam["url"],
            stream_type=StreamType.RTSP if "rtsp" in cam["url"] else StreamType.MJPEG,
            latitude=cam["lat"],
            longitude=cam["lon"],
            altitude=cam["altitude"],
            azimuth=cam["azimuth"],
            elevation=cam["elevation"],
            is_sky_facing=True,
            tags=["airport", "seattle"] if "SEA" in cam["name"] else ["downtown"],
        )
        print(f"Registered: {source.name} (ID: {source.id})")

    # Discover additional public webcams
    public_cams = await manager.discover_windy_camels(
        api_key="YOUR_WINDY_API_KEY",
        lat=47.6062,
        lon=-122.3321,
        radius_km=50,
    )
    print(f"Discovered {len(public_cams)} additional public webcams")

    return manager

# Usage
# manager = asyncio.run(setup_webcam_pipeline())
```

---

## Historical Video Archive Import

### Scanning Video Directories

```python
from chemtrail.sources import HistoricalIngestor

# Initialize ingestor
ingestor = HistoricalIngestor(db_session=session, vector_store=vector_store)

# Scan a single directory (non-recursive)
result = ingestor.scan_directory(
    directory="C:/Videos/Chemtrail_Archive/April_2026",
    recursive=False,
)

print(f"Found {result.count} video files in {result.directory}")
for path in result.found[:5]:  # Show first 5
    print(f"  - {path}")
```

### Recursive Directory Scanning

```python
# Scan entire archive recursively
result = ingestor.scan_directory(
    directory="C:/Videos/Chemtrail_Archive",
    recursive=True,
)

print(f"Total videos found: {result.count}")
```

### Supported Video Formats

The Historical Ingestor supports these video formats:

| Extension | Format | Notes |
|-----------|--------|-------|
| `.mp4` | MPEG-4 Part 14 | Most common, recommended |
| `.mov` | QuickTime | Apple format |
| `.avi` | AVI | Legacy Windows format |
| `.mkv` | Matroska | Container format |
| `.webm` | WebM | Web-optimized |
| `.m4v` | iTunes Video | Apple variant |

### Ingesting Individual Videos

```python
# Ingest a single video file
result = ingestor.ingest_video(
    video_path="C:/Videos/chemtrail_20260411_120000.mp4",
    source_type="local",      # or "youtube", "webcam"
    camera_id="cam-001",      # Optional: link to registered camera
    metadata_override={
        "latitude": 47.6062,
        "longitude": -122.3321,
        "altitude": 100,
        "tags": ["seattle", "downtown", "clear_sky"],
    },
)

if result["success"]:
    print(f"Ingested successfully: {result['data']['id']}")
    print(f"Resolution: {result['data']['resolution']}")
    print(f"Duration: {result['data']['duration_seconds']}s")
else:
    print(f"Ingest failed: {result['error']}")
```

### Batch Ingest from Multiple Directories

```python
# Ingest all videos from multiple directories
directories = [
    "C:/Videos/Archives/April_2026",
    "C:/Videos/Archives/March_2026",
    "C:/Videos/Archives/February_2026",
]

results = ingestor.ingest_batch(
    directory_paths=directories,
    recursive=True,
    source_type="local",
)

# Summarize results
successful = sum(1 for r in results if r["success"])
failed = len(results) - successful
print(f"Ingest complete: {successful} successful, {failed} failed")
```

### Checking for Duplicates

```python
# The ingestor automatically tracks processed files by SHA256 hash
# To manually check:

file_hash = ingestor.metadata_extractor.compute_file_hash(
    "C:/Videos/chemtrail_20260411_120000.mp4"
)

if ingestor.is_duplicate(file_hash):
    print("This video has already been processed")
else:
    print("New video - safe to ingest")
```

### Extracting Video Metadata

```python
from chemtrail.sources import MetadataExtractor

extractor = MetadataExtractor()

metadata = extractor.extract_metadata(
    "C:/Videos/chemtrail_20260411_120000.mp4"
)

print(f"File: {metadata.file_path}")
print(f"Size: {metadata.file_size_bytes / 1_000_000:.1f} MB")
print(f"Duration: {metadata.duration_seconds:.1f}s")
print(f"Resolution: {metadata.width}x{metadata.height}")
print(f"FPS: {metadata.fps}")
print(f"Codec: {metadata.codec}")
print(f"Bitrate: {metadata.bitrate_kbps} kbps")
print(f"SHA256: {metadata.checksum_sha256[:16]}...")
```

### Example: Complete Archive Import Workflow

```python
import asyncio
from chemtrail.sources import HistoricalIngestor, VideoCatalog

async def import_archive():
    # Initialize
    ingestor = HistoricalIngestor(db_session=session, vector_store=vector_store)
    catalog = VideoCatalog(session=session, vector_store=vector_store)
    await catalog.initialize()

    # Scan archive directories
    archive_dirs = [
        "C:/Videos/Chemtrail_Archive/2026/Q1",
        "C:/Videos/Chemtrail_Archive/2026/Q2",
    ]

    all_videos = []
    for directory in archive_dirs:
        result = ingestor.scan_directory(directory, recursive=True)
        all_videos.extend(result.found)
        print(f"Scanned {directory}: {result.count} videos")

    # Ingest and catalog
    ingested_count = 0
    for video_path in all_videos:
        ingest_result = ingestor.ingest_video(video_path)

        if ingest_result["success"]:
            # Add to catalog
            catalog_result = catalog.add_entry(ingest_result["data"])

            if catalog_result["success"]:
                ingested_count += 1
                print(f"Ingested: {video_path}")
            else:
                print(f"Catalog error: {catalog_result['error']}")
        else:
            print(f"Ingest error: {ingest_result['error']}")

    print(f"\nImport complete: {ingested_count}/{len(all_videos)} videos")

# Usage
# asyncio.run(import_archive())
```

---

## Live Detection Pipeline

### Starting the Live Pipeline

```python
from chemtrail.sources import PipelineOrchestrator, PipelineConfig

# Configure pipeline
config = PipelineConfig(
    max_concurrent_jobs=3,
    enable_weather_enrichment=True,
    enable_quality_scoring=True,
    skip_still_frames=True,
    apply_overlay=True,           # Burn flight telemetry on clips
    chunk_duration_seconds=30,    # Process 30-second chunks
    chunk_overlap_seconds=5,      # 5-second overlap between chunks
)

# Initialize orchestrator
orchestrator = PipelineOrchestrator(
    session=session,
    webcam_manager=webcam_manager,
    historical_ingestor=historical_ingestor,
    video_catalog=video_catalog,
    detection_service=detection_service,
    weather_service=weather_service,
    config=config,
)

# Start pipeline workers
await orchestrator.start()
print(f"Pipeline started with {config.max_concurrent_jobs} workers")
```

### Running Continuous Live Detection

```python
# Run live detection pipeline continuously for 1 hour
results = await orchestrator.run_live_pipeline(
    camera_id="cam-seattle-001",  # Registered camera ID
    duration_hours=1,              # Run for 1 hour
    chunk_interval=30,             # Capture every 30 seconds
    skip_still=True,               # Skip static frames
    apply_overlay=True,            # Apply flight overlay
)

print(f"Pipeline complete:")
print(f"  Jobs submitted: {len(results['jobs'])}")
print(f"  Errors: {len(results['errors'])}")
```

### Submitting Individual Jobs

```python
# Submit a webcam segment for processing
job_id = await orchestrator.submit_job(
    source_path="/tmp/chemtrail_segments/cam-001_1234567890.mp4",
    source_type="webcam",
    priority=0,  # Lower = higher priority
    metadata={
        "camera_id": "cam-seattle-001",
        "latitude": 47.6062,
        "longitude": -122.3321,
        "recorded_at": "2026-04-11T12:00:00Z",
    },
)

print(f"Submitted job: {job_id}")
```

### Monitoring Job Progress

```python
# Check job status
status = await orchestrator.get_pipeline_status(job_id)

if status:
    print(f"Job: {status['job_id']}")
    print(f"Status: {status['status']}")
    print(f"Current Stage: {status['current_stage']}")
    print(f"Created: {status['created_at']}")

    if status['started_at']:
        print(f"Started: {status['started_at']}")
    if status['completed_at']:
        print(f"Completed: {status['completed_at']}")
    if status['error_message']:
        print(f"Error: {status['error_message']}")
```

### Waiting for Job Completion

```python
import asyncio

try:
    # Wait for job with 30-minute timeout
    final_status = await orchestrator.wait_for_job(
        job_id,
        timeout_seconds=1800,  # 30 minutes
    )

    print(f"Job completed with status: {final_status['status']}")

    if final_status['status'] == 'completed':
        detections = final_status.get('stage_results', {}).get('detections', [])
        print(f"Total detections: {len(detections)}")

except TimeoutError:
    print("Job timed out - still processing")
except ValueError as e:
    print(f"Job error: {e}")
```

### Cancelling Jobs

```python
# Cancel a pending or running job
cancelled = await orchestrator.cancel_pipeline(job_id)

if cancelled:
    print(f"Job {job_id} cancelled successfully")
else:
    print(f"Could not cancel job (may be already completed)")
```

### Getting All Job Statuses

```python
# Get status summary for all jobs
all_jobs = orchestrator.get_all_jobs_status()

for job in all_jobs:
    print(f"Job {job['job_id'][:8]}... : {job['status']} ({job['current_stage']})")
```

---

## Batch Historical Analysis

### Processing Video Archives

```python
# Run pipeline on entire video archive
directories = [
    "C:/Videos/Chemtrail_Archive/2026/Q1",
    "C:/Videos/Chemtrail_Archive/2026/Q2",
]

results = await orchestrator.run_historical_pipeline(
    directories=directories,
    recursive=True,
)

print(f"Batch Analysis Results:")
print(f"  Total videos found: {results['stats']['total_videos']}")
print(f"  Jobs submitted: {results['stats']['submitted_jobs']}")
print(f"  Errors: {len(results['errors'])}")
```

### Processing YouTube Videos

```python
# Process a YouTube airport live stream
youtube_url = "https://www.youtube.com/watch?v=airport_live_stream"

results = await orchestrator.run_youtube_pipeline(
    youtube_url=youtube_url,
)

if results["jobs"]:
    job_id = results["jobs"][0]
    print(f"YouTube video submitted for processing: {job_id}")

if results["errors"]:
    print(f"Errors: {results['errors']}")
```

### Prioritizing Batch Jobs

```python
# Submit multiple videos with different priorities
high_priority_videos = [
    "C:/Videos/high_quality_1.mp4",
    "C:/Videos/high_quality_2.mp4",
]

normal_priority_videos = [
    "C:/Videos/standard_1.mp4",
    "C:/Videos/standard_2.mp4",
]

# High priority jobs (processed first)
for path in high_priority_videos:
    await orchestrator.submit_job(
        source_path=path,
        source_type="local",
        priority=0,  # Highest priority
    )

# Normal priority jobs
for path in normal_priority_videos:
    await orchestrator.submit_job(
        source_path=path,
        source_type="local",
        priority=10,  # Normal priority
    )
```

### Weather Enrichment Configuration

```python
# Disable weather enrichment for faster processing
config = PipelineConfig(
    enable_weather_enrichment=False,  # Skip weather API calls
    enable_quality_scoring=True,
)

# Or enable with custom cache TTL
weather_service = WeatherService(cache_ttl_hours=48)  # Cache for 2 days
```

### Quality Scoring Details

The quality scoring algorithm evaluates:

| Metric | Weight | Description |
|--------|--------|-------------|
| Resolution | 40 pts | 4K=40, 1080p=35, 720p=25, 480p=15 |
| Duration | 20 pts | Optimal: 30s-10min |
| Bitrate | 20 pts | Based on file size / duration |
| Stability | 20 pts | Camera shake detection |

```python
# Calculate quality score manually
score = video_catalog.calculate_quality_score(
    resolution="1080p",
    duration=120,        # 2 minutes
    file_size=50_000_000,  # 50 MB
    metrics={
        "stability_score": 0.85,
        "lighting_score": 0.75,
    },
)

print(f"Quality score: {score}/100")
```

---

## Searching and Browsing Results

### Video Catalog Search

```python
from datetime import datetime, timedelta

# Search by date range
videos = video_catalog.search(
    date_from=datetime.now() - timedelta(days=7),
    date_to=datetime.now(),
    min_quality=70,
    limit=50,
)

print(f"Found {len(videos)} high-quality videos from last week")
for v in videos[:5]:
    print(f"  - {v['camera_name']}: {v['resolution']} (quality: {v['quality_score']})")
```

### Search by Camera

```python
# Filter by specific camera
camera_videos = video_catalog.search(
    camera_id="cam-seattle-001",
    limit=20,
)
```

### Search by Location

```python
# Find videos near a location
nearby_videos = video_catalog.search_by_location(
    lat=47.6062,
    lon=-122.3321,
    radius_km=25,
    limit=50,
)

print(f"Videos within 25km of Seattle: {len(nearby_videos)}")
```

### Quality Distribution

```python
# Get quality distribution across catalog
distribution = video_catalog.get_quality_distribution()

print("Quality Distribution:")
for tier, count in distribution.items():
    print(f"  {tier}: {count} videos")
```

### Catalog Statistics

```python
# Get overall catalog statistics
stats = video_catalog.get_stats()

print(f"Catalog Statistics:")
print(f"  Total videos: {stats['total_videos']}")
print(f"  Total duration: {stats['total_duration_hours']} hours")
print(f"  Sources breakdown:")
for source, count in stats['sources_breakdown'].items():
    print(f"    {source}: {count}")
```

### Searching Detections (Semantic Search)

```python
from chemtrail.archive.searcher import search_detections

# Natural language search
results = search_detections(
    query="contrails from Boeing 737 over Seattle",
    vector_store=vector_store,
    n_results=10,
)

for r in results:
    print(f"Score: {r['score']:.2f}")
    print(f"  Callsign: {r.get('callsign', 'N/A')}")
    print(f"  Camera: {r.get('camera_name', 'N/A')}")
    print(f"  Time: {r.get('timestamp', 'N/A')}")
```

### Filtering Detections

```python
# Search with metadata filters
from chemtrail.archive.vector_store import ChemtrailVectorStore

store = ChemtrailVectorStore()

# By flight ICAO code
flight_results = store.search_by_flight(
    icao24="4b1a02",
    n_results=50,
)

# By camera with date range
camera_results = store.search_by_camera(
    camera_id="cam-001",
    date_from=datetime(2026, 4, 1),
    n_results=100,
)

# By geographic area
location_results = store.search_by_location(
    lat_min=47.60,
    lat_max=47.62,
    lon_min=-122.35,
    lon_max=-122.32,
    n_results=50,
)
```

---

## Configuration Examples

### Example 1: Single Camera Setup

```python
"""Minimal setup for a single RTSP camera."""

from chemtrail.sources import (
    WebcamManager, StreamType,
    HistoricalIngestor, VideoCatalog, WeatherService,
    PipelineOrchestrator, PipelineConfig,
)

async def setup_single_camera():
    # Initialize manager
    manager = WebcamManager(max_concurrent=1)
    await manager.initialize()

    # Add camera
    source = manager.add_manual_source(
        name="Backyard Sky Cam",
        url="rtsp://192.168.1.50:554/stream",
        stream_type=StreamType.RTSP,
        latitude=47.6062,
        longitude=-122.3321,
        altitude=50,
        azimuth=180,
        elevation=45,
        is_sky_facing=True,
    )

    # Configure lightweight pipeline
    config = PipelineConfig(
        max_concurrent_jobs=1,
        enable_weather_enrichment=True,
        enable_quality_scoring=False,  # Skip for speed
        skip_still_frames=True,
        chunk_duration_seconds=30,
    )

    orchestrator = PipelineOrchestrator(
        session=session,
        webcam_manager=manager,
        video_catalog=catalog,
        weather_service=WeatherService(),
        detection_service=detection_service,
        config=config,
    )

    await orchestrator.start()

    # Run for 24 hours
    results = await orchestrator.run_live_pipeline(
        camera_id=source.id,
        duration_hours=24,
        chunk_interval=60,
    )

    return results
```

### Example 2: Multi-Camera Airport Monitoring

```python
"""Setup for monitoring multiple airport webcams."""

async def setup_airport_monitoring():
    manager = WebcamManager(max_concurrent=5)
    await manager.initialize(windy_api_key="YOUR_API_KEY")

    # Register airport cameras
    airports = [
        {
            "name": "SEA Runway 16L",
            "url": "rtsp://sea-cam.example.com/runway16l",
            "lat": 47.4502,
            "lon": -122.3088,
            "alt": 130,
            "azimuth": 160,
        },
        {
            "name": "SEA Runway 34R",
            "url": "rtsp://sea-cam.example.com/runway34r",
            "lat": 47.4480,
            "lon": -122.3120,
            "alt": 130,
            "azimuth": 340,
        },
        {
            "name": "BFI General Aviation",
            "url": "http://boeing-field.example.com/ga_cam.mjpeg",
            "lat": 47.5300,
            "lon": -122.3020,
            "alt": 20,
            "azimuth": 90,
        },
    ]

    for airport in airports:
        manager.add_manual_source(
            name=airport["name"],
            url=airport["url"],
            stream_type=StreamType.RTSP if "rtsp" in airport["url"] else StreamType.MJPEG,
            latitude=airport["lat"],
            longitude=airport["lon"],
            altitude=airport["alt"],
            azimuth=airport["azimuth"],
            elevation=30,
            is_sky_facing=True,
            tags=["airport", "seattle"],
        )

    # High-throughput pipeline configuration
    config = PipelineConfig(
        max_concurrent_jobs=5,
        enable_weather_enrichment=True,
        enable_quality_scoring=True,
        skip_still_frames=True,
        apply_overlay=True,
        chunk_duration_seconds=30,
    )

    orchestrator = PipelineOrchestrator(
        session=session,
        webcam_manager=manager,
        video_catalog=catalog,
        weather_service=WeatherService(),
        detection_service=detection_service,
        config=config,
    )

    await orchestrator.start()

    # Run parallel pipelines for all cameras
    all_results = []
    for source in manager.get_all_sources():
        results = await orchestrator.run_live_pipeline(
            camera_id=source.id,
            duration_hours=8,
            chunk_interval=30,
        )
        all_results.append(results)

    return all_results
```

### Example 3: Archive Digitization Project

```python
"""Batch process legacy video archives."""

async def digitize_archive():
    ingestor = HistoricalIngestor(db_session=session, vector_store=vector_store)
    catalog = VideoCatalog(session=session, vector_store=vector_store)
    await catalog.initialize()

    # Archive directories organized by date
    archive_base = "C:/Videos/Legacy_Archive"
    year_dirs = [
        f"{archive_base}/2024",
        f"{archive_base}/2025",
        f"{archive_base}/2026",
    ]

    # Scan all directories
    all_videos = []
    for year_dir in year_dirs:
        result = ingestor.scan_directory(year_dir, recursive=True)
        print(f"{year_dir}: {result.count} videos")
        all_videos.extend(result.found)

    print(f"Total videos to process: {len(all_videos)}")

    # Configure batch pipeline
    config = PipelineConfig(
        max_concurrent_jobs=3,  # Limit to avoid overwhelming system
        enable_weather_enrichment=True,
        enable_quality_scoring=True,
        skip_still_frames=True,
    )

    orchestrator = PipelineOrchestrator(
        session=session,
        historical_ingestor=ingestor,
        video_catalog=catalog,
        weather_service=WeatherService(),
        detection_service=detection_service,
        config=config,
    )

    await orchestrator.start()

    # Submit all videos with priority based on quality
    for video_path in all_videos:
        # Extract metadata first
        metadata = ingestor.metadata_extractor.extract_metadata(video_path)

        # Higher priority for better quality
        if metadata.height >= 1080:
            priority = 0  # High priority
        elif metadata.height >= 720:
            priority = 5  # Medium priority
        else:
            priority = 10  # Low priority

        await orchestrator.submit_job(
            source_path=video_path,
            source_type="local",
            priority=priority,
            metadata={
                "resolution": f"{metadata.height}p",
                "duration_seconds": metadata.duration_seconds,
            },
        )

    print(f"Submitted {len(all_videos)} jobs for processing")

    return orchestrator
```

### Example 4: Weather-Based Filtering

```python
"""Filter videos by weather conditions for optimal contrail visibility."""

from chemtrail.sources.weather_service import WEATHER_CODE_DESCRIPTION

async def find_clear_sky_videos():
    # Search catalog
    all_videos = video_catalog.search(
        date_from=datetime(2026, 4, 1),
        date_to=datetime(2026, 4, 11),
        limit=500,
    )

    # Filter by weather condition
    clear_sky_videos = [
        v for v in all_videos
        if v.get('weather_data', {}).get('condition') in ['clear', 'mainly_clear']
        and v.get('weather_data', {}).get('cloud_cover_pct', 100) < 30
    ]

    print(f"Found {len(clear_sky_videos)} videos with clear sky conditions")

    # Sort by quality
    clear_sky_videos.sort(
        key=lambda v: v.get('quality_score', 0),
        reverse=True,
    )

    # Top 10 for contrail detection
    top_videos = clear_sky_videos[:10]
    for v in top_videos:
        print(f"  {v['camera_name']}: quality={v['quality_score']}, "
              f"weather={v['weather_data'].get('condition')}")

    return top_videos
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. ffmpeg Not Found

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

**Solution:**
```bash
# Install ffmpeg via package manager
# Windows (Chocolatey)
choco install ffmpeg

# Windows (Manual)
# Download from https://ffmpeg.org/download.html
# Add to PATH

# Verify installation
ffmpeg -version
```

#### 2. RTSP Stream Connection Failures

**Error:**
```
Failed to capture segment: Connection refused
```

**Solutions:**

1. **Check network connectivity:**
   ```bash
   ping camera-ip-address
   telnet camera-ip-address 554
   ```

2. **Verify stream URL:**
   ```python
   # Test stream with VLC or ffplay
   ffplay "rtsp://camera-ip:554/stream" -rtsp_transport tcp
   ```

3. **Try different RTSP transport:**
   ```python
   # The WebcamManager automatically uses TCP transport for RTSP
   # If issues persist, check camera firewall settings
   ```

4. **Check camera credentials:**
   ```python
   # Ensure URL includes credentials if required
   url = "rtsp://username:password@camera-ip:554/stream"
   ```

#### 3. Open-Meteo API Rate Limiting

**Error:**
```
HTTPError: 429 Too Many Requests
```

**Solution:**
```python
# Increase cache TTL to reduce API calls
weather_service = WeatherService(cache_ttl_hours=48)

# Or use cached data only
# (Implement local caching layer)
```

#### 4. Duplicate Video Ingestion

**Error:**
```
Ingest failed: Duplicate file
```

**Solution:**
```python
# This is expected behavior - the file hash already exists
# To force re-ingestion, clear the processed hashes:

ingestor._processed_hashes.clear()

# Or check if you want to skip duplicates
if not ingestor.is_duplicate(file_hash):
    result = ingestor.ingest_video(video_path)
```

#### 5. Pipeline Job Timeout

**Error:**
```
TimeoutError: Job xxx timed out after 1800s
```

**Solutions:**

1. **Increase timeout for large videos:**
   ```python
   config = PipelineConfig(
       stage_timeout_seconds={
           PipelineStage.DETECTION: 3600,  # 1 hour for detection
           PipelineStage.CHUNKING: 1200,   # 20 min for chunking
       },
   )
   ```

2. **Check system resources:**
   ```bash
   # Monitor CPU and memory usage
   # High load may cause processing delays
   ```

3. **Reduce concurrent jobs:**
   ```python
   config = PipelineConfig(max_concurrent_jobs=2)
   ```

#### 6. ChromaDB Collection Errors

**Error:**
```
ChromaDB not initialized
```

**Solution:**
```python
# Ensure vector_store is properly initialized
vector_store = ChemtrailVectorStore()

# Initialize catalog with vector store
catalog = VideoCatalog(session=session, vector_store=vector_store)
await catalog.initialize()
```

#### 7. Memory Issues with Large Videos

**Symptoms:**
- System becomes unresponsive during processing
- Out of memory errors

**Solutions:**

1. **Reduce concurrent jobs:**
   ```python
   config = PipelineConfig(max_concurrent_jobs=1)
   ```

2. **Process videos in batches:**
   ```python
   batch_size = 10
   for i in range(0, len(videos), batch_size):
       batch = videos[i:i+batch_size]
       # Process batch
       await asyncio.sleep(60)  # Cool-down between batches
   ```

3. **Reduce chunk duration:**
   ```python
   config = PipelineConfig(
       chunk_duration_seconds=15,  # Smaller chunks
       chunk_overlap_seconds=2,
   )
   ```

### Debug Logging

Enable detailed logging for troubleshooting:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chemtrail_phase2.log'),
        logging.StreamHandler(),
    ]
)
```

### Health Check Script

```python
async def health_check():
    """Run system health checks."""
    from chemtrail.sources import WebcamManager, HistoricalIngestor

    print("=== Chemtrail Phase 2 Health Check ===\n")

    # Check ffmpeg
    import subprocess
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        print(f"ffmpeg: OK ({result.stdout.decode().split()[2]})")
    except FileNotFoundError:
        print("ffmpeg: NOT FOUND - Install required")

    # Check database connection
    try:
        await session.execute("SELECT 1")
        print("Database: OK")
    except Exception as e:
        print(f"Database: ERROR - {e}")

    # Check webcam manager
    try:
        manager = WebcamManager()
        await manager.initialize()
        print("WebcamManager: OK")
        await manager.close()
    except Exception as e:
        print(f"WebcamManager: ERROR - {e}")

    # Check weather service
    try:
        weather = WeatherService()
        test_weather = weather.get_historical_weather(
            lat=47.6062,
            lon=-122.3321,
            timestamp=datetime.now(),
        )
        print(f"WeatherService: OK (API accessible)")
        weather.close()
    except Exception as e:
        print(f"WeatherService: ERROR - {e}")

    print("\n=== Health Check Complete ===")

# Run: asyncio.run(health_check())
```

### Support Resources

- **Architecture Documentation:** `PHASE2_ARCHITECTURE.md`
- **Implementation Brief:** `IMPLEMENTATION_BRIEF_PHASE2.md`
- **API Reference:** `API_REFERENCE.md`
- **Integration Guide:** `INTEGRATION_GUIDE.md`

---

*Document Version: 2.0.0 | Last Updated: 2026-04-11*
