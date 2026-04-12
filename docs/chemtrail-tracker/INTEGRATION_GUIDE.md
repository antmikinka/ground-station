# Phase 1.5 SentrySearch Integration Guide

**Chemtrail Webcam Tracker**  
**Version:** 1.5.0  
**Last Updated:** 2026-04-11  
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage Examples](#usage-examples)
5. [API Reference](#api-reference)
6. [ChromaDB Query Examples](#chromadb-query-examples)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The Phase 1.5 SentrySearch integration transforms the Chemtrail Webcam Tracker from a real-time detection system into a **semantic, searchable archive** of contrail detection events. This integration enables natural language queries such as:

- *"Find all contrails from Boeing 737 over downtown"*
- *"Show me persistent contrails from last week"*
- *"Contrails captured by camera-01 yesterday"*

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Video Chunking** | Split webcam feeds into 5-30 second overlapping segments for processing |
| **Still-Frame Detection** | Skip static sky frames, reducing CPU load by 60-80% |
| **Semantic Embedding** | Generate vector embeddings using Gemini API or local Qwen3-VL models |
| **Vector Storage** | Archive detections in ChromaDB with rich metadata |
| **Natural Language Search** | Query detection archive using plain English |
| **Metadata Filtering** | Filter by flight ICAO24, camera ID, date range, detection type |
| **Flight Data Overlay** | Burn flight telemetry HUD onto detection clips |

### Architecture Summary

```
Webcam Feed → Chunker → Still-Frame Check → Preprocess → CV Detection
                                                              ↓
Flight Correlation ← Geolocalization ← Detection Event
                                              ↓
                              Embedding → ChromaDB → Search API
```

---

## Installation

### Prerequisites

- Python 3.10 or higher
- ffmpeg (system-installed or via imageio-ffmpeg)
- ChromaDB compatible system
- Gemini API key (for cloud embeddings) OR GPU for local embeddings

### Step 1: Install Dependencies

```bash
cd C:\Users\antmi\ground-station

# Install core dependencies
pip install chromadb>=0.5.0
pip install imageio-ffmpeg>=0.4.0
pip install google-genai>=0.1.0

# Optional: for geocoding in overlays
pip install geopy>=2.4.0

# Optional: for local embedding backend
pip install torch>=2.0.0
pip install transformers>=4.35.0
```

### Step 2: Verify Installation

```bash
python -c "import chromadb; print(chromadb.__version__)"
python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
python -c "from google import genai; print('Gemini SDK OK')"
```

### Step 3: Set Environment Variables

Create or update your `.env` file in the project root:

```bash
# Gemini API Configuration (required for cloud embeddings)
GEMINI_API_KEY=your-api-key-here

# Optional: ChromaDB path override
CHEMTRAIL_DB_PATH=C:/Users/antmi/ground-station/backend/.chemtrail_db
```

---

## Configuration

### ChromaDB Path Configuration

The vector store uses a default path but can be customized:

```python
from chemtrail.archive.vector_store import ChemtrailVectorStore

# Default path (C:\Users\<user>\.chemtrail\db)
store = ChemtrailVectorStore()

# Custom path
store = ChemtrailVectorStore(
    db_path="C:/Users/antmi/ground-station/backend/.chemtrail_db"
)
```

### Embedding Backend Selection

The system supports multiple embedding backends:

#### Gemini API Backend (Default)

```python
from chemtrail.archive.embedder import get_embedder

# Uses GEMINI_API_KEY from environment
embedder = get_embedder(backend="gemini")
```

**Pros:**
- Best embedding quality
- No GPU required
- Handles video natively

**Cons:**
- API costs (~$0.02 per 30s clip)
- Rate limits (60 requests/minute free tier)
- Requires internet connection

#### Local Backend (Qwen3-VL)

```python
from chemtrail.archive.embedder import get_embedder

# Local embedding with Qwen3-VL-8B
embedder = get_embedder(
    backend="local",
    model="qwen8b",
    dimensions=768
)
```

**Pros:**
- No API costs
- No rate limits
- Works offline

**Cons:**
- Requires GPU (8GB+ VRAM recommended)
- Slower than API
- Lower embedding quality

### Backend Detection

Automatically detect the backend used for existing indexes:

```python
from chemtrail.archive.vector_store import detect_backend, detect_index

# Detect backend from existing database
backend = detect_backend()  # Returns "gemini", "local", or None

# Detect backend and model
backend, model = detect_index()
# Returns: ("gemini", None) or ("local", "qwen8b")
```

---

## Usage Examples

### Processing Webcam Feeds

#### Batch Processing Video Files

```python
from chemtrail.archive.chunker import chunk_video, is_still_frame_chunk

# Chunk a video file into 30-second segments with 5-second overlap
chunks = chunk_video(
    video_path="C:/Users/antmi/webcam_footage.mp4",
    chunk_duration=30,
    overlap=5
)

print(f"Created {len(chunks)} chunks")

# Filter out still-frame chunks (static sky)
dynamic_chunks = []
for chunk in chunks:
    if not is_still_frame_chunk(chunk["chunk_path"]):
        dynamic_chunks.append(chunk)

print(f"Filtered to {len(dynamic_chunks)} dynamic chunks")
```

#### Continuous RTSP Stream Processing

```python
from chemtrail.archive.chunker import chunk_video

# Continuously chunk an RTSP stream
stream_url = "rtsp://camera.example.com/stream"

for chunk in chunk_video(
    stream_url=stream_url,
    chunk_duration=10,
    overlap=2,
    continuous_mode=True
):
    # Process each chunk as it's recorded
    print(f"New chunk: {chunk['chunk_path']}")
    # TODO: Add your detection pipeline here
```

#### Preprocessing for CV Pipeline

```python
from chemtrail.archive.chunker import preprocess_chunk

# Downscale chunk for efficient processing
preprocessed = preprocess_chunk(
    chunk_path="C:/Users/antmi/chunk_001.mp4",
    target_resolution=480,  # Height in pixels
    target_fps=5
)

print(f"Preprocessed: {preprocessed}")
```

### Searching Detections

#### Basic Semantic Search

```python
from chemtrail.archive.vector_store import ChemtrailVectorStore
from chemtrail.archive.searcher import search_detections

# Initialize vector store
store = ChemtrailVectorStore(
    db_path="C:/Users/antmi/ground-station/backend/.chemtrail_db"
)

# Natural language search
results = search_detections(
    query="contrails from Boeing 737",
    vector_store=store,
    n_results=10
)

for result in results:
    print(f"Score: {result['score']:.2f}")
    print(f"  Source: {result['source_file']}")
    print(f"  Time: {result['start_time']}s - {result['end_time']}s")
    print(f"  Callsign: {result.get('callsign', 'N/A')}")
```

#### Filtered Search with Metadata

```python
from datetime import datetime, timedelta

# Search with filters
results = search_detections(
    query="high altitude contrails",
    vector_store=store,
    n_results=20,
    icao24="4b1a02",  # Specific flight
    camera_id="cam-001",  # Specific camera
    date_from=datetime.now() - timedelta(days=7),
    date_to=datetime.now(),
    detection_type="contrail"
)
```

#### Flight-Specific Search

```python
# Search all detections for a specific flight
flight_results = store.search_by_flight(
    icao24="4b1a02",
    n_results=50
)

print(f"Found {len(flight_results)} detections for flight {icao24}")
```

#### Camera-Specific Search

```python
# Search detections from a specific camera
camera_results = store.search_by_camera(
    camera_id="cam-001",
    date_from=datetime(2026, 4, 1),
    date_to=datetime(2026, 4, 11),
    n_results=100
)
```

#### Geographic Bounding Box Search

```python
# Search within Seattle downtown area
location_results = store.search_by_location(
    lat_min=47.60,
    lat_max=47.62,
    lon_min=-122.35,
    lon_max=-122.32,
    n_results=50
)
```

### Generating Overlay Clips

#### Basic Flight Data Overlay

```python
from chemtrail.archive.telemetry_overlay import (
    apply_flight_overlay,
    get_flight_metadata,
    build_hud_overlay
)
from services.flight_service import FlightService
from datetime import datetime, timezone

# Initialize flight service
flight_service = FlightService()

# Get flight metadata for overlay
flight_meta = get_flight_metadata(
    icao24="4b1a02",
    flight_service=flight_service,
    timestamp=datetime.now(timezone.utc)
)

if flight_meta:
    # Apply HUD overlay to clip
    output_path = "C:/Users/antmi/output_with_overlay.mp4"
    result = apply_flight_overlay(
        input_path="C:/Users/antmi/detection_clip.mp4",
        output_path=output_path,
        flight_metadata=flight_meta
    )
    
    if result == output_path:
        print("Overlay applied successfully")
    else:
        print("Overlay failed, returned original clip")
```

#### Building Custom HUD Overlays

```python
from chemtrail.archive.telemetry_overlay import build_hud_overlay

# Build custom HUD metadata
hud_meta = build_hud_overlay(
    flight_data={
        "callsign": "UAL123",
        "altitude": 35000,
        "velocity": 250.5,  # m/s
        "heading": 270.0,
        "latitude": 47.6062,
        "longitude": -122.3321
    },
    camera_name="Seattle Downtown Cam",
    timestamp=datetime.now(timezone.utc),
    contrail_vector={
        "angle": 45.0,
        "length_px": 120,
        "width_px": 8,
        "persistence": 30
    }
)
```

### Complete Detection Pipeline

```python
from chemtrail.archive.detection_service import DetectionService
from chemtrail.archive.vector_store import ChemtrailVectorStore
from chemtrail.cv.contrail_detector import ContrailDetector
from services.flight_service import FlightService
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async def run_detection_pipeline():
    # Initialize components
    engine = create_async_engine("sqlite+aiosqlite:///detections.db")
    vector_store = ChemtrailVectorStore()
    flight_service = FlightService()
    contrail_detector = ContrailDetector()
    
    async with AsyncSession(engine) as session:
        # Create detection service
        detection_service = DetectionService(
            session=session,
            vector_store=vector_store,
            flight_service=flight_service,
            contrail_detector=contrail_detector
        )
        
        # Process video chunks
        chunks = chunk_video("webcam_feed.mp4", chunk_duration=30)
        
        # Camera metadata
        camera_meta = {
            "name": "Downtown Cam",
            "latitude": 47.6062,
            "longitude": -122.3321,
            "altitude": 100,
            "azimuth": 180,
            "elevation": 45,
            "fov_horizontal": 60,
            "fov_vertical": 40
        }
        
        # Run detection pipeline
        results = await detection_service.process_detection_batch(
            chunks=chunks,
            camera_id="cam-001",
            camera_metadata=camera_meta,
            skip_still_frames=True,
            apply_overlay=True
        )
        
        print(f"Processed {len(results)} detections")
```

---

## API Reference

### chunker.py

#### `chunk_video()`

Split a video into overlapping chunks.

```python
def chunk_video(
    video_path: str,
    chunk_duration: int = 30,
    overlap: int = 5,
    continuous_mode: bool = False,
    output_dir: Optional[str] = None,
) -> list[dict] | Iterator[dict]
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `video_path` | `str` | - | Path to video file or RTSP/MJPEG URL |
| `chunk_duration` | `int` | `30` | Duration of each chunk in seconds |
| `overlap` | `int` | `5` | Overlap between chunks in seconds |
| `continuous_mode` | `bool` | `False` | If True, continuously chunk stream |
| `output_dir` | `str` | `None` | Directory for chunk files |

**Returns:** List of dicts with `chunk_path`, `source_file`, `start_time`, `end_time`

**Example:**
```python
chunks = chunk_video("feed.mp4", chunk_duration=30, overlap=5)
for chunk in chunks:
    print(f"Chunk: {chunk['chunk_path']}, {chunk['start_time']}s-{chunk['end_time']}s")
```

#### `is_still_frame_chunk()`

Check if a video chunk contains mostly still frames.

```python
def is_still_frame_chunk(
    chunk_path: str,
    threshold: float = 0.98,
    verbose: bool = False,
) -> bool
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk_path` | `str` | - | Path to video chunk |
| `threshold` | `float` | `0.98` | Size ratio threshold (min/max) |
| `verbose` | `bool` | `False` | Print debug info |

**Returns:** `True` if chunk appears static

#### `preprocess_chunk()`

Downscale and reduce frame rate of a video chunk.

```python
def preprocess_chunk(
    chunk_path: str,
    target_resolution: int = 480,
    target_fps: int = 5,
) -> str
```

**Returns:** Path to preprocessed file

### vector_store.py

#### `ChemtrailVectorStore`

Persistent vector store for chemtrail detections backed by ChromaDB.

```python
class ChemtrailVectorStore:
    def __init__(
        self,
        db_path: str | Path | None = None,
        backend: str = "gemini",
        model: str | None = None
    )
```

**Methods:**

| Method | Description |
|--------|-------------|
| `add_detection(chunk_id, embedding, metadata)` | Store a detection with metadata |
| `add_detections(chunks)` | Batch-store detections |
| `search(query_embedding, n_results)` | Search by vector similarity |
| `search_by_flight(icao24, n_results)` | Search by flight ICAO24 |
| `search_by_camera(camera_id, date_from, date_to, n_results)` | Search by camera with date range |
| `search_by_location(lat_min, lat_max, lon_min, lon_max, n_results)` | Search by geographic bounds |
| `search_by_date_range(date_from, date_to, n_results)` | Search by date range |
| `is_indexed(source_file)` | Check if file is already indexed |
| `remove_file(source_file)` | Remove all chunks for a file |
| `get_stats()` | Get store statistics |

#### `add_detection()`

```python
def add_detection(
    self,
    chunk_id: str,
    embedding: list[float],
    metadata: dict,
) -> None
```

**Required metadata keys:**
- `source_file`, `start_time`, `end_time`
- `camera_id`, `confidence`

**Optional metadata keys:**
- `camera_name`, `camera_lat`, `camera_lon`, `camera_alt`
- `detection_type`, `pixel_x`, `pixel_y`, `azimuth`, `elevation`
- `contrail_vector`, `icao24`, `callsign`, `aircraft_type`
- `estimated_lat`, `estimated_lon`, `estimated_alt`
- `correlation_score`, `position_method`
- `overlay_applied`, `clip_path`

### embedder.py

#### `get_embedder()`

Factory function to get the active embedder.

```python
def get_embedder(backend: str = "gemini", **kwargs) -> BaseEmbedder
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `backend` | `str` | `"gemini"` or `"local"` |
| `model` | `str` | For local: `"qwen8b"`, `"qwen2b"` |
| `dimensions` | `int` | Output embedding dimensions |

#### `embed_video_chunk()`

Embed a video chunk.

```python
def embed_video_chunk(
    chunk_path: str,
    verbose: bool = False
) -> list[float]
```

#### `embed_query()`

Embed a text query.

```python
def embed_query(
    query_text: str,
    verbose: bool = False
) -> list[float]
```

### searcher.py

#### `search_detections()`

Search detection archive with natural language and metadata filters.

```python
def search_detections(
    query: str,
    vector_store: ChemtrailVectorStore,
    n_results: int = 10,
    icao24: str | None = None,
    camera_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    detection_type: str | None = None,
    verbose: bool = False,
) -> list[dict]
```

**Returns:** List of result dicts with:
- `chunk_id`, `source_file`, `start_time`, `end_time`
- `score`, `camera_id`, `camera_name`
- `icao24`, `callsign`, `detection_type`
- `confidence`, `estimated_lat`, `estimated_lon`

### telemetry_overlay.py

#### `apply_flight_overlay()`

Burn flight data HUD onto detection clip.

```python
def apply_flight_overlay(
    input_path: str,
    output_path: str,
    flight_metadata: dict,
) -> str
```

**Returns:** `output_path` on success, `input_path` on failure

#### `get_flight_metadata()`

Get flight metadata for overlay from OpenSky cache.

```python
def get_flight_metadata(
    icao24: str,
    flight_service,
    timestamp: datetime,
) -> dict | None
```

#### `build_hud_overlay()`

Build a complete HUD metadata dict for overlay.

```python
def build_hud_overlay(
    flight_data: dict,
    camera_name: str,
    timestamp: datetime,
    contrail_vector: dict | None = None,
) -> dict
```

### detection_service.py

#### `DetectionService`

Orchestrates detection processing and archival.

```python
class DetectionService:
    def __init__(
        self,
        session: AsyncSession,
        vector_store: ChemtrailVectorStore,
        flight_service: FlightService,
        contrail_detector: ContrailDetector,
        embedder: Optional[BaseEmbedder] = None,
    )
    
    async def process_detection_batch(
        self,
        chunks: List[Dict],
        camera_id: str,
        camera_metadata: Dict,
        skip_still_frames: bool = True,
        apply_overlay: bool = False,
    ) -> List[Dict]
```

---

## ChromaDB Query Examples

### Direct ChromaDB Access

```python
import chromadb
from chemtrail.archive.vector_store import ChemtrailVectorStore

store = ChemtrailVectorStore()
collection = store.collection
```

### Query by Embedding

```python
from chemtrail.archive.embedder import embed_query

# Embed query
query_embedding = embed_query("contrails from passenger jets")

# Query collection
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    include=["metadatas", "distances"]
)

for i, meta in enumerate(results["metadatas"][0]):
    print(f"Result {i+1}:")
    print(f"  Distance: {results['distances'][0][i]:.4f}")
    print(f"  Source: {meta['source_file']}")
    print(f"  Confidence: {meta['confidence']:.2f}")
```

### Query with Metadata Filter (Where Clause)

```python
# Filter by ICAO24
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    where={"icao24": "4b1a02"},
    include=["metadatas", "distances"]
)

# Filter by detection type
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    where={"detection_type": "contrail"},
    include=["metadatas", "distances"]
)

# Filter with AND condition
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    where={
        "$and": [
            {"icao24": "4b1a02"},
            {"detection_type": "contrail"}
        ]
    },
    include=["metadatas", "distances"]
)
```

### Get Metadata Only (No Embedding Query)

```python
# Get all detections for a camera
results = collection.get(
    where={"camera_id": "cam-001"},
    limit=100,
    include=["metadatas"]
)

# Get specific fields
for meta in results["metadatas"]:
    print(f"{meta['callsign']} at {meta['start_time']}s")
```

### Delete Detections

```python
# Remove by chunk ID
collection.delete(ids=["chunk_id_1", "chunk_id_2"])

# Remove by metadata filter (two-step)
results = collection.get(where={"camera_id": "cam-001"})
collection.delete(ids=results["ids"])
```

### Collection Statistics

```python
# Get collection count
count = collection.count()

# Get all metadata
all_meta = collection.get(include=["metadatas"])
print(f"Total detections: {len(all_meta['ids'])}")

# Count by detection type
contrail_count = sum(1 for m in all_meta["metadatas"] if m["detection_type"] == "contrail")
aircraft_count = sum(1 for m in all_meta["metadatas"] if m["detection_type"] == "aircraft")
```

---

## Troubleshooting

### Common Issues

#### 1. "ffmpeg not found" Error

**Symptom:**
```
RuntimeError: ffmpeg not found on PATH and imageio-ffmpeg is not available
```

**Solution:**
```bash
# Option 1: Install imageio-ffmpeg
pip install imageio-ffmpeg

# Option 2: Install system ffmpeg
# Windows
choco install ffmpeg

# macOS
brew install ffmpeg

# Linux
apt install ffmpeg
```

#### 2. "GEMINI_API_KEY is not set" Error

**Symptom:**
```
GeminiAPIKeyError: GEMINI_API_KEY is not set
```

**Solution:**
```bash
# Set environment variable
export GEMINI_API_KEY=your-api-key

# Or add to .env file
echo "GEMINI_API_KEY=your-api-key" >> .env

# Or use local backend
embedder = get_embedder(backend="local")
```

#### 3. ChromaDB Backend Mismatch

**Symptom:**
```
BackendMismatchError: This index was built with the gemini backend
```

**Solution:**
```python
# Detect existing backend
from chemtrail.archive.vector_store import detect_backend

backend = detect_backend()  # Returns "gemini" or "local"

# Use matching backend
store = ChemtrailVectorStore(backend=backend)
```

#### 4. Gemini API Rate Limit Exceeded

**Symptom:**
```
GeminiQuotaError: Gemini API rate limit exceeded
```

**Solution:**
```python
# Reduce request rate
# Option 1: Use larger chunk duration
chunks = chunk_video("video.mp4", chunk_duration=60)  # Fewer chunks

# Option 2: Use local backend
embedder = get_embedder(backend="local")

# Option 3: Implement retry with backoff
from chemtrail.archive.gemini_embedder import _retry

def embed_with_retry(chunk_path):
    return _retry(lambda: embedder.embed_video_chunk(chunk_path))
```

#### 5. Still-Frame Detection Failing

**Symptom:** All chunks processed even for static cameras

**Solution:**
```python
# Adjust threshold (default: 0.98)
is_still = is_still_frame_chunk(
    chunk_path="chunk.mp4",
    threshold=0.95  # Lower = more sensitive
)

# Or use verbose mode for debugging
is_still = is_still_frame_chunk(
    chunk_path="chunk.mp4",
    verbose=True  # Prints frame sizes
)
```

#### 6. Overlay Not Applied to Clip

**Symptom:** Output clip has no HUD overlay

**Solution:**
```python
# Check ffmpeg supports ASS filter
from chemtrail.archive.telemetry_overlay import _get_ass_ffmpeg

ffmpeg_exe = _get_ass_ffmpeg()
print(f"Using ffmpeg: {ffmpeg_exe}")

# Verify flight metadata is valid
flight_meta = get_flight_metadata(icao24, flight_service, timestamp)
if not flight_meta:
    print("Flight metadata not found")

# Check output path is writable
result = apply_flight_overlay(input_path, output_path, flight_meta)
if result == input_path:
    print("Overlay failed - check ffmpeg logs")
```

### Performance Issues

#### Slow Embedding

**Symptoms:** Embedding takes >10 seconds per chunk

**Solutions:**
1. Use local backend with smaller model:
```python
embedder = get_embedder(backend="local", model="qwen2b")
```

2. Preprocess chunks to smaller size:
```python
preprocessed = preprocess_chunk(
    chunk_path,
    target_resolution=240,  # Lower resolution
    target_fps=3  # Lower fps
)
```

#### High Memory Usage

**Symptoms:** OOM errors during processing

**Solutions:**
1. Process chunks sequentially, not in batches
2. Clean up temporary files:
```python
import shutil
import tempfile

# After processing
shutil.rmtree(temp_dir, ignore_errors=True)
```

### Debug Mode

Enable verbose logging for debugging:

```python
from chemtrail.archive.embedder import embed_video_chunk
from chemtrail.archive.chunker import is_still_frame_chunk

# Verbose embedding
embedding = embed_video_chunk("chunk.mp4", verbose=True)

# Verbose still-frame detection
is_still = is_still_frame_chunk("chunk.mp4", verbose=True)
```

### Support

For additional help:
- Check the [ARCHITECTURE.md](./ARCHITECTURE.md) for system overview
- Review the [API_REFERENCE.md](./API_REFERENCE.md) for detailed API docs
- File issues on the project repository
