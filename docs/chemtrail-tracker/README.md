# Chemtrail Webcam Tracker

**Phase 2 - Footage Acquisition & Pipeline Orchestration**  
**Version:** 2.0.0  
**Last Updated:** 2026-04-11

A complete end-to-end footage management system that correlates public webcam sky imagery with flight tracking data to detect and log aircraft contrails. The system leverages computer vision for automated detection, multiple API integrations for data correlation, geolocalization mathematics for position triangulation, and comprehensive pipeline orchestration for automated processing workflows.

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Automated Contrail Detection** | Hough transform-based detection of contrails in sky imagery |
| **Flight Correlation** | Match detected contrails with actual flight data from OpenSky Network |
| **Geolocalization** | Calculate aircraft positions using camera metadata and detection angles |
| **Semantic Search Archive** | Natural language search over detection history using vector embeddings |
| **Flight Data Overlay** | Burn flight telemetry HUD onto detection clips |
| **Still-Frame Skipping** | Skip static sky frames to reduce CPU load by 60-80% |

### Phase 2 Additions (NEW)

| Feature | Description |
|---------|-------------|
| **Live Webcam Acquisition** | Continuous RTSP/MJPEG/HLS stream capture with health monitoring |
| **Historical Video Ingestion** | Scan and import local video archives with metadata extraction |
| **Video Catalog & Sorting** | Intelligent organization by camera, date, weather, and quality |
| **Weather Enrichment** | Auto-tagging with historical weather data from Open-Meteo API |
| **Pipeline Orchestration** | End-to-end workflow automation from acquisition to archival |
| **Quality Scoring** | Automated video quality assessment for prioritization |
| **YouTube Integration** | Download and process YouTube live streams via yt-dlp |

### Phase 1.5 Additions

- **ChromaDB Vector Store** - Archive detections with semantic embeddings
- **Natural Language Search** - Query with plain English ("contrails from Boeing 737")
- **Video Chunking Pipeline** - Process RTSP/MJPEG feeds into segments
- **Flight Telemetry Overlay** - ASS subtitle-based HUD rendering
- **Multi-Backend Embedding** - Gemini API or local Qwen3-VL models

---

## Quick Start

### Installation

```bash
cd C:\Users\antmi\ground-station

# Install dependencies
pip install -r backend/requirements.txt

# Install Phase 1.5 dependencies
pip install chromadb>=0.5.0
pip install imageio-ffmpeg>=0.4.0
pip install google-genai>=0.1.0

# Install Phase 2 dependencies
pip install yt-dlp>=2024.1.0
pip install httpx>=0.28.0
```

### Configuration

1. Set environment variables in `.env`:
```bash
GEMINI_API_KEY=your-api-key-here
DATABASE_URL=sqlite+aiosqlite:///backend/detections.db
CHEMTRAIL_DB_PATH=C:/Users/antmi/ground-station/backend/.chemtrail_db
WINDY_API_KEY=your-windy-api-key  # Optional, for webcam discovery
```

2. Configure cameras in the system (requires metadata):
```python
camera_metadata = {
    "name": "Seattle Downtown Cam",
    "latitude": 47.6062,
    "longitude": -122.3321,
    "altitude": 100,
    "azimuth": 180,
    "elevation": 45,
    "fov_horizontal": 60,
    "fov_vertical": 40
}
```

3. **Lemonade Server FLM** (Optional - for local NPU embedding):

   a. Install Lemonade Server from https://github.com/FastFlowLM/FastFlowLM/releases
   
   b. Start Lemonade Server (GUI app or `lemonade-server.exe`)
   
   c. Verify the server is running at `http://localhost:8000`:
   ```bash
   curl http://localhost:8000/v1/models
   ```
   
   d. Set environment variables:
   ```bash
   FLM_BASE_URL=http://localhost:8000
   FLM_EMBEDDING_MODEL=nomic-embed-text-v2-moe-GGUF
   FLM_VISION_MODEL=qwen3vl-it-4b-FLM
   FLM_DIMENSIONS=768
   EMBEDDER_BACKEND=flm
   ```

   Lemonade Server routes inference to FLM on the AMD Ryzen AI NPU backend,
   providing an OpenAI-compatible API for vision-language and embedding tasks.

4. **FR24 Integration Setup** (Optional - for enhanced flight data):

   a. Obtain an FR24 API token from https://www.flightradar24.com/developers/api
   
   b. Set the environment variable:
   ```bash
   FR24_API_TOKEN=your-fr24-api-token-here
   ```
   
   c. (Optional) Add to `.env`:
   ```bash
   FR24_API_TOKEN=your-fr24-api-token-here
   FR24_RATE_LIMIT=60                      # Requests per minute (default: 60)
   FR24_ENRICHMENT_LIMIT=50                # Max flights to enrich per batch
   FR24_CACHE_TTL=300                      # Cache TTL in seconds (default: 300)
   ```
   
   d. Verify FR24 enrichment is working:
   ```python
   from chemtrail.services import FR24FlightService
   
   service = FR24FlightService()
   health = service.health_check()
   print(f"FR24 Status: {health['status']}")
   
   # Test enrichment
   result = service.enrich_flight_cache_entry("4b1a02")
   print(result)  # Should contain fr24_id, painted_as, etc.
   ```

5. **Phase 2**: Register webcam sources programmatically:
```python
from chemtrail.sources import WebcamManager, StreamType

manager = WebcamManager()
await manager.initialize()

source = manager.add_manual_source(
    name="SEA Airport Cam",
    url="rtsp://camera.example.com:554/stream",
    stream_type=StreamType.RTSP,
    latitude=47.4502,
    longitude=-122.3088,
    altitude=130,
    azimuth=160,
    elevation=30,
    is_sky_facing=True,
)
```

6. **Phase 2**: Import historical video archives:
```python
from chemtrail.sources import HistoricalIngestor

ingestor = HistoricalIngestor(db_session=session, vector_store=vector_store)
result = ingestor.scan_directory("C:/Videos/Chemtrail_Archive", recursive=True)
print(f"Found {result.count} videos")
```

### Basic Usage

#### Phase 1.5: Process and Search Detections

```python
from chemtrail.archive.chunker import chunk_video
from chemtrail.archive.vector_store import ChemtrailVectorStore
from chemtrail.archive.searcher import search_detections

# Process webcam feed
chunks = chunk_video("webcam_feed.mp4", chunk_duration=30, overlap=5)

# Initialize vector store
store = ChemtrailVectorStore()

# Search archived detections
results = search_detections(
    query="contrails from Boeing 737",
    vector_store=store,
    n_results=10
)
```

#### Phase 2: Full Pipeline Orchestration

```python
from chemtrail.sources import (
    WebcamManager, HistoricalIngestor, VideoCatalog,
    WeatherService, PipelineOrchestrator, PipelineConfig
)

# Initialize pipeline
config = PipelineConfig(
    max_concurrent_jobs=3,
    enable_weather_enrichment=True,
    enable_quality_scoring=True,
    skip_still_frames=True,
    apply_overlay=True,
)

orchestrator = PipelineOrchestrator(
    session=session,
    webcam_manager=webcam_manager,
    historical_ingestor=ingestor,
    video_catalog=catalog,
    detection_service=detection_service,
    weather_service=weather_service,
    config=config,
)

# Start pipeline
await orchestrator.start()

# Run live detection pipeline
results = await orchestrator.run_live_pipeline(
    camera_id="cam-seattle-001",
    duration_hours=1,
    chunk_interval=30,
)

# Run batch historical analysis
batch_results = await orchestrator.run_historical_pipeline(
    directories=["C:/Videos/Archive"],
    recursive=True,
)
```

---

## Phase 2 Documentation

| Document | Description |
|----------|-------------|
| [PHASE2_USER_GUIDE.md](./PHASE2_USER_GUIDE.md) | Complete user guide for Phase 2 features |
| [PIPELINE_QUICKSTART.md](./PIPELINE_QUICKSTART.md) | 5-minute end-to-end pipeline walkthrough |
| [PHASE2_ARCHITECTURE.md](./PHASE2_ARCHITECTURE.md) | Technical architecture and module specifications |
| [IMPLEMENTATION_BRIEF_PHASE2.md](./IMPLEMENTATION_BRIEF_PHASE2.md) | Implementation details and test strategy |

---

## Architecture

### Phase 2 System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: FOOTAGE ACQUISITION & ORCHESTRATION                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  EXTERNAL SOURCES                                                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│  │  LIVE WEBCAMS   │  │  HISTORICAL     │  │  EXTERNAL       │                 │
│  │                 │  │  VIDEO FILES    │  │  DATA APIs      │                 │
│  │  • RTSP Streams │  │                 │  │                 │                 │
│  │  • MJPEG Feeds  │  │  • Local Files  │  │  • Open-Meteo   │                 │
│  │  • YouTube Live │  │  • Network      │  │  • Windy.com    │                 │
│  │  • Airport Cams │  │  • Archives     │  │  • Webcam APIs  │                 │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                 │
│           │                     │                     │                          │
│           └─────────────────────┴─────────────────────┘                          │
│                                   │                                              │
│  ┌────────────────────────────────▼─────────────────────────────────────────┐   │
│  │                    SOURCES LAYER (Phase 2 NEW)                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Webcam     │  │ Historical  │  │   Video     │  │   Weather   │     │   │
│  │  │  Manager    │  │ Ingestor    │  │  Catalog    │  │  Enrichment │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                              │
│                                   ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    PIPELINE ORCHESTRATOR (Phase 2 NEW)                   │    │
│  │  Workflow Engine: Acquisition → Sorting → Detection → Archive           │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                                   │                                              │
│                                   ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    EXISTING DETECTION PIPELINE (Phase 1.5)               │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │    │
│  │  │   Chunker   │  │  CV Detect  │  │   Flight    │  │   Archive   │    │    │
│  │  │             │  │             │  │  Correlate  │  │  (ChromaDB) │    │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  DATA LAYER                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  PostgreSQL │  │   Redis     │  │  ChromaDB   │  │   File      │            │
│  │  (Catalog)  │  │   (Queue)   │  │  (Archive)  │  │  Storage    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1.5 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHEMTRAIL TRACKER - PHASE 1.5                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  EXTERNAL SOURCES                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  RTSP/MJPEG │  │  OpenSky    │  │  Webcam     │             │
│  │  Webcams    │  │  Network    │  │  APIs       │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                 │                │                     │
│         └─────────────────┴────────────────┘                     │
│                           │                                       │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │                    INGESTION LAYER                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │
│  │  │   chunker   │  │  still-frame│  │  preprocess │       │   │
│  │  │   (RTSP→    │  │   (skip     │  │  (480p @    │       │   │
│  │  │   segments) │  │   static)   │  │   5fps)     │       │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │   │
│  └───────────────────────────────────────────────────────────┘   │
│                           │                                       │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    CV PIPELINE                           │   │
│  │  ┌─────────────┐  ┌─────────────┐                       │   │
│  │  │  Contrail   │  │  Aircraft   │                       │   │
│  │  │  (Hough)    │  │  (YOLOv8)   │                       │   │
│  │  └─────────────┘  └─────────────┘                       │   │
│  └───────────────────────────────────────────────────────────┘   │
│                           │                                       │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    SERVICES                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │   Flight    │  │    Geo      │  │  Detection  │      │   │
│  │  │  Correlation│  │  Calculator │  │  Service    │      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │   │
│  └───────────────────────────────────────────────────────────┘   │
│                           │                                       │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    ARCHIVE LAYER                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │   Embedder  │  │  ChromaDB   │  │   Overlay   │      │   │
│  │  │  (Gemini/   │  │  (vectors   │  │  (HUD burn) │      │   │
│  │  │   Qwen3-VL) │  │   + meta)   │  │             │      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │   │
│  └───────────────────────────────────────────────────────────┘   │
│                           │                                       │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    SEARCH API                            │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  GET /api/detections/search?q="contrails..."    │    │   │
│  │  │  GET /api/detections/search?icao24=...&date=... │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  DATA LAYER                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  PostgreSQL │  │   Redis     │  │   ChromaDB  │             │
│  │  (Primary)  │  │   (Cache)   │  │  (Archive)  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Webcam Feed → Chunker → Still-Frame Check → Preprocess → CV Detection
                                                              ↓
Flight Correlation ← Geolocalization ← Detection Event
                                              ↓
                              Embedding → ChromaDB → Search API
```

---

## Directory Structure

```
C:\Users\antmi\ground-station\
├── backend/
│   ├── chemtrail/
│   │   ├── __init__.py
│   │   ├── api/                    # API clients
│   │   │   ├── opensky_client.py   # OpenSky Network API
│   │   │   └── webcam_client.py    # Webcam ingestion
│   │   ├── services/               # Business logic
│   │   │   ├── camera_service.py   # Camera management
│   │   │   ├── flight_service.py   # Flight data cache
│   │   │   ├── geocalc_service.py  # Geolocalization
│   │   │   └── detection_service.py# Detection orchestration
│   │   ├── cv/                     # Computer vision
│   │   │   ├── contrail_detector.py# Hough-based detection
│   │   │   └── cv_utils.py         # CV helpers
│   │   ├── archive/                # Phase 1.5 SentrySearch
│   │   │   ├── __init__.py
│   │   │   ├── chunker.py          # Video chunking
│   │   │   ├── vector_store.py     # ChromaDB wrapper
│   │   │   ├── searcher.py         # Semantic search
│   │   │   ├── embedder.py         # Embedding factory
│   │   │   ├── base_embedder.py    # Abstract base class
│   │   │   ├── gemini_embedder.py  # Gemini API backend
│   │   │   ├── flm_embedder.py     # Lemonade Server FLM NPU embedder
│   │   │   ├── telemetry_overlay.py# Flight HUD overlay
│   │   │   └── detection_service.py# Pipeline orchestrator
│   │   ├── sources/                # Phase 2 Footage Acquisition (NEW)
│   │   │   ├── __init__.py
│   │   │   ├── webcam_manager.py   # Live stream management
│   │   │   ├── historical_ingestor.py  # Video archive import
│   │   │   ├── video_catalog.py    # Video metadata & sorting
│   │   │   ├── weather_service.py  # Open-Meteo integration
│   │   │   └── pipeline_orchestrator.py  # End-to-end workflow
│   │   └── storage/                # Storage backends
│   │       ├── image_storage.py    # File storage
│   │       └── vector_store.py     # Vector store (legacy)
│   ├── db/
│   │   └── models.py               # SQLAlchemy models
│   ├── common/
│   │   └── common.py               # Shared utilities
│   └── requirements.txt            # Python dependencies
├── docs/
│   └── chemtrail-tracker/
│       ├── README.md               # This file
│       ├── ARCHITECTURE.md         # Technical architecture
│       ├── INTEGRATION_GUIDE.md    # User integration guide
│       ├── INTEGRATION_ARCHITECTURE.md  # Phase 1.5 architecture
│       ├── API_REFERENCE.md        # Developer API docs
│       ├── PIPELINE_QUICKSTART.md  # 5-minute quickstart
│       ├── FUTURE-WHERE-TO-RESUME-LEFT-OFF.md  # Living progress doc
│       └── archive/                # Historical/phase-completed docs
└── frontend/
    └── src/
        └── features/
            └── chemtrail/          # React frontend
```

---

## Documentation Index

| Document | Description | Audience |
|----------|-------------|----------|
| [README.md](./README.md) | Project overview and quick start | All users |
| [PHASE2_USER_GUIDE.md](./PHASE2_USER_GUIDE.md) | Phase 2 user guide with configuration examples | End users, operators |
| [PIPELINE_QUICKSTART.md](./PIPELINE_QUICKSTART.md) | 5-minute end-to-end pipeline walkthrough | New users |
| [PHASE2_ARCHITECTURE.md](./PHASE2_ARCHITECTURE.md) | Phase 2 technical architecture and specifications | Architects, developers |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Complete technical architecture, API comparisons, CV approaches | System architects, developers |
| [INTEGRATION_ARCHITECTURE.md](./INTEGRATION_ARCHITECTURE.md) | Phase 1.5 SentrySearch integration design, module mapping | Integration developers |
| [IMPLEMENTATION_BRIEF_PHASE2.md](./IMPLEMENTATION_BRIEF_PHASE2.md) | Phase 2 implementation details and test strategy | Development team |
| [IMPLEMENTATION_BRIEF.md](./IMPLEMENTATION_BRIEF.md) | Phase 1 implementation instructions | Implementation team |
| [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) | Setup, configuration, usage examples, troubleshooting | End users, integrators |
| [API_REFERENCE.md](./API_REFERENCE.md) | Complete API documentation with signatures and examples | API developers |

---

## Project Status

### Phase Completion

| Phase | Status | Description | Tests |
|-------|--------|-------------|-------|
| **Phase 1** | ✅ Complete | Foundation: OpenSky API, camera management, CV detection, flight correlation | 73 passing |
| **Phase 1.5** | ✅ Complete | SentrySearch integration: chunking, embedding, vector store, search, overlay | New tests added |
| **Phase 2** | ✅ Complete | Footage acquisition: webcam manager, historical ingestor, video catalog, weather enrichment, pipeline orchestrator | New tests added |
| **Phase 3** | ⏳ Planned | Scale: motion tracking, deep learning, batch processing, analytics | - |
| **Phase 4** | ⏳ Planned | Production: multi-camera, Docker, documentation, deployment | - |

### Phase 2 Module Status

| Module | File | Status | Description |
|--------|------|--------|-------------|
| `webcam_manager.py` | `chemtrail/sources/webcam_manager.py` | ✅ Production | RTSP/MJPEG/HLS stream management with health monitoring |
| `historical_ingestor.py` | `chemtrail/sources/historical_ingestor.py` | ✅ Production | Video archive scanning and metadata extraction |
| `video_catalog.py` | `chemtrail/sources/video_catalog.py` | ✅ Production | Video metadata storage and search with ChromaDB |
| `weather_service.py` | `chemtrail/sources/weather_service.py` | ✅ Production | Open-Meteo API integration for weather enrichment |
| `pipeline_orchestrator.py` | `chemtrail/sources/pipeline_orchestrator.py` | ✅ Production | End-to-end workflow coordination |

### Phase 1.5 Module Status

| Module | Status | Backend | Description |
|--------|--------|---------|-------------|
| `chunker.py` | ✅ Production | ffmpeg | Video/RTSP chunking with still-frame detection |
| `vector_store.py` | ✅ Production | ChromaDB | Persistent vector store with metadata filtering |
| `embedder.py` | ✅ Production | Gemini/Local | Multi-backend embedding factory |
| `searcher.py` | ✅ Production | ChromaDB | Natural language search with filters |
| `telemetry_overlay.py` | ✅ Production | ffmpeg/libass | Flight data HUD rendering |
| `detection_service.py` | ✅ Production | Full pipeline | Detection orchestration |

---

## Getting Started Guide

### 1. Prerequisites

- Python 3.10+
- ffmpeg (system or via imageio-ffmpeg)
- Gemini API key (for cloud embeddings)
- PostgreSQL (for primary data)
- ChromaDB (for vector archive)

### 2. Installation

```bash
# Clone repository
cd C:\Users\antmi\ground-station

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Install Phase 1.5 dependencies
pip install chromadb imageio-ffmpeg google-genai
```

### 3. Configuration

```bash
# Create .env file
cat > .env << EOF
GEMINI_API_KEY=your-api-key-here
DATABASE_URL=sqlite+aiosqlite:///backend/detections.db
CHEMTRAIL_DB_PATH=C:/Users/antmi/ground-station/backend/.chemtrail_db
EOF
```

### 4. Initialize Database

```python
from db.models import Base
from sqlalchemy import create_engine

engine = create_engine("sqlite:///backend/detections.db")
Base.metadata.create_all(engine)
```

### 5. Register a Camera

```python
from chemtrail.services.camera_service import CameraService

service = CameraService()

camera = await service.create_camera(
    name="Seattle Downtown Cam",
    url="rtsp://camera.example.com/stream",
    camera_type="rtsp",
    latitude=47.6062,
    longitude=-122.3321,
    altitude=100,
    azimuth=180,
    elevation=45,
    fov_horizontal=60,
    fov_vertical=40
)
```

### 6. Process a Detection

```python
from chemtrail.archive.chunker import chunk_video
from chemtrail.archive.detection_service import DetectionService

# Chunk video
chunks = chunk_video("webcam_feed.mp4", chunk_duration=30)

# Process through detection pipeline
results = await detection_service.process_detection_batch(
    chunks=chunks,
    camera_id=camera.id,
    camera_metadata={...}
)
```

### 7. Search Detections

```python
from chemtrail.archive.vector_store import ChemtrailVectorStore
from chemtrail.archive.searcher import search_detections

store = ChemtrailVectorStore()

results = search_detections(
    query="contrails from Boeing 737",
    vector_store=store,
    n_results=10
)

for r in results:
    print(f"Score: {r['score']:.2f}, Callsign: {r.get('callsign', 'N/A')}")
```

---

## API Endpoints

### Detection Search

```
GET /api/detections/search?q=natural_language_query
GET /api/detections/search?icao24=ABC123&camera_id=cam-001&date_from=2026-04-01
POST /api/detections/{id}/overlay
GET /api/archive/stats
```

### Camera Management

```
GET  /api/cameras
POST /api/cameras
GET  /api/cameras/{id}
PUT  /api/cameras/{id}
DELETE /api/cameras/{id}
```

### Flight Data

```
GET  /api/flights
GET  /api/flights/{icao24}
GET  /api/flights/near?lat=47.6062&lon=-122.3321&radius=10
```

---

## Query Examples

### Natural Language Queries

```python
# Basic search
search_detections("contrails over downtown", store)

# With filters
search_detections(
    "high altitude contrails",
    store,
    icao24="4b1a02",
    date_from=datetime.now() - timedelta(days=7)
)

# Camera-specific
search_detections(
    "persistent contrails",
    store,
    camera_id="cam-001"
)
```

### ChromaDB Direct Queries

```python
# By flight
results = store.search_by_flight(icao24="4b1a02", n_results=50)

# By camera with date range
results = store.search_by_camera(
    camera_id="cam-001",
    date_from=datetime(2026, 4, 1),
    n_results=100
)

# By location
results = store.search_by_location(
    lat_min=47.60, lat_max=47.62,
    lon_min=-122.35, lon_max=-122.32,
    n_results=50
)
```

---

## Contributing

### Development Setup

```bash
# Install dev dependencies
pip install pytest pytest-cov pytest-asyncio
pip install black isort flake8 mypy

# Run tests
pytest backend/tests/chemtrail/ -v

# Run with coverage
pytest backend/tests/chemtrail/ --cov=chemtrail/archive --cov-report=html
```

### Code Style

- Use type hints for all function signatures
- Follow PEP 8 style guidelines
- Include docstrings for all public functions
- Write tests for new functionality

---

## Troubleshooting

See the [PHASE2_USER_GUIDE.md](./PHASE2_USER_GUIDE.md#troubleshooting) for detailed Phase 2 troubleshooting steps.

### Quick Fixes

| Issue | Solution |
|-------|----------|
| `ffmpeg not found` | `pip install imageio-ffmpeg` or install from ffmpeg.org |
| `GEMINI_API_KEY not set` | Set env var or use `backend="local"` |
| `BackendMismatchError` | Use `detect_backend()` to find correct backend |
| `API rate limit` | Use larger `chunk_duration` or local backend |
| `RTSP connection failed` | Check network connectivity and stream URL credentials |
| `Open-Meteo API error` | WeatherService has 24h cache; reduce API calls |
| `Duplicate video ingest` | Checksum-based deduplication is working as designed |

### Phase 2 Troubleshooting

```python
# Run health check
from chemtrail.sources import WebcamManager, HistoricalIngestor, WeatherService

async def health_check():
    # Check ffmpeg
    import subprocess
    subprocess.run(["ffmpeg", "-version"])

    # Check webcam manager
    manager = WebcamManager()
    await manager.initialize()
    print("WebcamManager: OK")

    # Check weather service
    weather = WeatherService()
    result = weather.get_historical_weather(
        lat=47.6062, lon=-122.3321,
        timestamp=datetime.now(),
    )
    print(f"WeatherService: OK (condition: {result['weather_description']})")

# asyncio.run(health_check())
```

---

## License

GNU General Public License v3.0 or later.

---

## Authors

- Dr. Sarah Kim, Technical Product Strategist & Engineering Lead
- Efstratios Goudelis, Backend Developer (Phase 1.5 implementation)

---

## References

- [OpenSky Network API](https://opensky-network.org/apidoc/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Gemini Embedding API](https://ai.google.dev/docs/embeddings)
- [OpenCV Documentation](https://docs.opencv.org/)
- [Open-Meteo API](https://open-meteo.com/en/docs/archive-api)
- [Windy.com Webcams API](https://api.windy.com/api/webcams)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg Documentation](https://ffmpeg.org/documentation.html)
