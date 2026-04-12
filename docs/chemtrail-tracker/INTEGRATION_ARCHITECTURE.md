# Chemtrail Webcam Tracker - SentrySearch Integration Architecture

**Version:** 1.5.0 (Phase 1.5 Integration)  
**Author:** Dr. Sarah Kim, Technical Product Strategist & Engineering Lead  
**Date:** 2026-04-11  
**Status:** Draft - For Review

---

## Executive Summary

This document describes the integration of SentrySearch capabilities into the Chemtrail Webcam Tracker system. The integration transforms the tracker from a real-time detection system into a **semantic, searchable archive** of contrail detection events, enabling queries like *"find all contrails from Boeing 737 over downtown"*.

### Integration Goals

1. **Process webcam feeds efficiently** - Use SentrySearch's chunker for RTSP/MJPEG segmentation
2. **Skip static frames** - Leverage still-frame detection to avoid processing unchanged sky images
3. **Archive detections semantically** - Store detection clips in ChromaDB with embeddings
4. **Enable natural language search** - Query detection history with natural language
5. **Rich metadata overlay** - Burn flight data onto detection clips using overlay.py
6. **Reduce CPU load** - Preprocess frames before CV pipeline runs

---

## 1. SentrySearch Module Mapping

### 1.1 Module Reuse Assessment

| SentrySearch Module | Chemtrail Use Case | Reuse Strategy | Adaptation Required |
|---------------------|-------------------|----------------|---------------------|
| **chunker.py** | RTSP/MJPEG feed segmentation → CV pipeline input | **Adapt** | Add RTSP stream support, continuous mode, configurable chunk duration (5-30s) |
| **chunker.py::is_still_frame_chunk()** | Skip unchanged sky frames | **Reuse** | Direct reuse - works for sky imagery |
| **chunker.py::preprocess_chunk()** | Downscale frames before CV processing | **Adapt** | Modify to output individual frames, not video chunks |
| **store.py** | ChromaDB vector store for detection archival | **Adapt** | Extend metadata schema for flight data, contrail vectors, camera info, FR24 enrichment |
| **embedder.py** | Embed detection clips for semantic search | **Reuse** | Use Gemini or local Qwen3-VL for clip embeddings |
| **search.py** | Natural language search over archived detections | **Adapt** | Add filtering by metadata (flight ICAO24, camera, date range, FR24 data) |
| **overlay.py** | Burn flight data onto detection clips | **Adapt** | Replace Tesla-specific fields with flight data (callsign, altitude, aircraft type, FR24 branding) |
| **metadata.py** | SEI extraction (Tesla-specific) | **Replace** | Not applicable - create flight metadata injector instead |

### 1.2 FR24 Integration Summary

The system includes dual-source flight data integration combining OpenSky (primary) with Flightradar24 (enrichment):

| Component | File | Purpose |
|-----------|------|---------|
| **FR24Client** | `chemtrail/api/fr24_client.py` | Sync wrapper around fr24sdk (~360 LOC) |
| **FR24FlightService** | `chemtrail/services/fr24_flight_service.py` | Service with config, health checks, enrichment (~345 LOC) |
| **Dual-Source FlightService** | `chemtrail/services/flight_service.py` | Merges OpenSky + FR24 data |
| **DetectionService** | `chemtrail/archive/detection_service.py` | FR24 enrichment in detection pipeline |
| **FlightCache Model** | `db/models.py` | +13 FR24 fields (fr24_id, painted_as, flight_track, etc.) |
| **Database Migration** | `alembic/versions/fr24_001_*.py` | Alembic migration for FR24 fields |
| **Tests** | `tests/chemtrail/test_fr24_integration.py` | 32 FR24-specific tests (all passing) |

**Key Benefits:**
- Dual-source redundancy (OpenSky primary, FR24 enrichment)
- Rich metadata: airline branding (`painted_as`, `operating_as`), airport codes (ICAO/IATA)
- Historical data access (since 2016-05-11)
- Flight track correlation for verified path matching
- Graceful degradation when FR24 unavailable

**Configuration:**
```bash
# Required for FR24 enrichment
FR24_API_TOKEN=your-fr24-api-token-here

# Optional
FR24_RATE_LIMIT=60           # Requests per minute
FR24_ENRICHMENT_LIMIT=50     # Max flights to enrich per batch
FR24_CACHE_TTL=300           # Cache TTL in seconds
```

### 1.3 Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SENTRYSEARCH MODULES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐               │
│   │  chunker.py  │────▶│  embedder.py │────▶│   store.py   │               │
│   │  (adapted)   │     │   (reuse)    │     │  (adapted)   │               │
│   └──────┬───────┘     └──────────────┘     └──────┬───────┘               │
│          │                                          │                       │
│          ▼                                          ▼                       │
│   ┌──────────────┐                           ┌──────────────┐              │
│   │ still-frame  │                           │  search.py   │              │
│   │   detection  │                           │  (adapted)   │              │
│   │  (reuse)     │                           └──────┬───────┘              │
│   └──────────────┘                                  │                       │
│                                                     ▼                       │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐              │
│   │  overlay.py  │◀────│   Detection  │◀────│   ChromaDB   │              │
│   │  (adapted)   │     │    Clip      │     │   Results    │              │
│   └──────────────┘     └──────────────┘     └──────────────┘              │
│                                                                             │
│   FR24 INTEGRATION (Parallel):                                              │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐              │
│   │  fr24sdk     │────▶│  FR24Client  │────▶│  FR24Flight  │              │
│   │  (external)  │     │  (sync wrap) │     │  Service     │              │
│   │              │     │              │     │              │              │
│   │              │     │  • get_live  │     │  • enrich    │              │
│   │              │     │  • get_hist  │     │  • health    │              │
│   │              │     │  • tracks    │     │  • validate  │              │
│   └──────────────┘     └──────────────┘     └──────┬───────┘              │
│                                                    │                       │
│                                                    ▼                       │
│                                          ┌──────────────────┐              │
│                                          │  FlightCache     │              │
│                                          │  +13 FR24 fields │              │
│                                          │  • fr24_id       │              │
│                                          │  • painted_as    │              │
│                                          │  • flight_track  │              │
│                                          │  • data_sources  │              │
│                                          └──────────────────┘              │
│                                                                             │
│   IMPORT CHAIN (No Circular Dependencies):                                  │
│   fr24sdk (external)                                                        │
│       ↑                                                                     │
│   chemtrail/api/fr24_client.py (no internal deps)                           │
│       ↑                                                                     │
│   chemtrail/services/fr24_flight_service.py                                 │
│       ↑                                                                     │
│   chemtrail/services/flight_service.py                                      │
│       ↑                                                                     │
│   chemtrail/archive/detection_service.py                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. New Module Structure

### 2.1 Integration Layer Architecture

```
backend/
├── chemtrail/
│   ├── __init__.py
│   ├── api/
│   │   ├── opensky_client.py         # Existing - OpenSky API
│   │   ├── fr24_client.py            # NEW - FR24 SDK wrapper (~360 LOC)
│   │   └── webcam_client.py          # Existing - RTSP/MJPEG ingestion
│   ├── services/
│   │   ├── camera_service.py         # Existing - Camera management
│   │   ├── flight_service.py         # Existing - Dual-source (OpenSky + FR24)
│   │   ├── fr24_flight_service.py    # NEW - FR24 service (~345 LOC)
│   │   ├── geocalc_service.py        # Existing - Geolocalization
│   │   └── detection_service.py      # NEW - Detection orchestration
│   ├── cv/
│   │   ├── contrail_detector.py      # Existing - Hough-based detection
│   │   ├── cv_utils.py               # Existing - CV helpers
│   │   └── frame_preprocessor.py     # NEW - SentrySearch preprocess integration
│   ├── storage/
│   │   ├── image_storage.py          # Existing - File storage
│   │   └── vector_store.py           # NEW - ChromaDB wrapper (SentrySearch store.py adapted)
│   ├── archive/
│   │   ├── __init__.py
│   │   ├── chunker.py                # COPIED from SentrySearch (adapted)
│   │   ├── embedder.py               # COPIED from SentrySearch (reuse)
│   │   ├── search.py                 # COPIED from SentrySearch (adapted)
│   │   └── overlay.py                # COPIED from SentrySearch (adapted for flight data)
│   └── handlers/
│       └── detection_handler.py      # Existing - Detection processing
├── db/
│   └── models.py                     # Extended with +13 FR24 fields
├── alembic/versions/
│   └── fr24_001_add_fr24_fields_to_flight_cache.py  # NEW - FR24 migration
└── tests/chemtrail/
    └── test_fr24_integration.py      # NEW - 32 FR24 tests
```
```

### 2.2 New Bridge Modules

| Module | Purpose | SentrySearch Source |
|--------|---------|---------------------|
| `chemtrail/archive/chunker.py` | Webcam feed segmentation | `sentrysearch/chunker.py` |
| `chemtrail/archive/embedder.py` | Detection clip embeddings | `sentrysearch/embedder.py` |
| `chemtrail/archive/vector_store.py` | ChromaDB detection archive | `sentrysearch/store.py` |
| `chemtrail/archive/search.py` | Semantic search over detections | `sentrysearch/search.py` |
| `chemtrail/archive/overlay.py` | Flight data HUD overlay | `sentrysearch/overlay.py` |
| `chemtrail/services/detection_service.py` | Orchestrate detection→archive pipeline | NEW |
| `chemtrail/cv/frame_preprocessor.py` | Frame preprocessing for CV | `sentrysearch/chunker.py::preprocess_chunk()` |

---

## 3. Data Flow Architecture

### 3.1 Complete Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 1.5 DATA FLOW                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │   WEBCAM    │     │   CHUNKER   │     │  STILL-FRAME│     │  PREPROCESS │   │
│  │   RTSP/     │────▶│   (5-30s    │────▶│   CHECK     │────▶│   (downscale│   │
│  │   MJPEG     │     │   segments) │     │  (skip if   │     │    + fps)   │   │
│  │             │     │             │     │   static)   │     │             │   │
│  └─────────────┘     └─────────────┘     └──────┬──────┘     └──────┬──────┘   │
│                                                  │                   │         │
│                                                  │ SKIP              │ PROCESS │
│                                                  ▼                   ▼         │
│                                            (next chunk)    ┌─────────────┐     │
│                                                            │     CV      │     │
│                                                            │  DETECTION  │     │
│                                                            │ (Hough/YOLO)│     │
│                                                            └──────┬──────┘     │
│                                                                   │             │
│                    ┌──────────────────────────────────────────────┤             │
│                    │                                              │             │
│                    ▼                                              ▼             │
│          ┌─────────────┐                                ┌─────────────┐         │
│          │   FLIGHT    │                                │  GEOLOCAL-  │         │
│          │  CORRELATION│                                │   ALIZATION │         │
│          │  (ICAO24    │                                │  (az/el/    │         │
│          │   lookup)   │                                │   position) │         │
│          └──────┬──────┘                                └──────┬──────┘         │
│                 │                                              │                 │
│                 └──────────────────┬───────────────────────────┘                 │
│                                    │                                             │
│                                    ▼                                             │
│                          ┌─────────────────┐                                     │
│                          │  DETECTION EVENT│                                     │
│                          │  + CLIP (5-30s) │                                     │
│                          └────────┬────────┘                                     │
│                                   │                                               │
│                                   ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐        │
│  │                      ARCHIVE LAYER                                    │        │
│  │  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐             │        │
│  │  │   EMBEDDER  │────▶│  ChromaDB   │◀────│  METADATA   │             │        │
│  │  │  (Gemini/   │     │  (vectors)  │     │  (flight +  │             │        │
│  │  │   Qwen3-VL) │     │             │     │   camera)   │             │        │
│  │  └─────────────┘     └──────┬──────┘     └─────────────┘             │        │
│  │                             │                                         │        │
│  │                             ▼                                         │        │
│  │                    ┌─────────────────┐                                │        │
│  │                    │  OVERLAY (HUD)  │                                │        │
│  │                    │  Burn flight    │                                │        │
│  │                    │  data onto clip │                                │        │
│  │                    └─────────────────┘                                │        │
│  └───────────────────────────────────────────────────────────────────────┘        │
│                                   │                                               │
│                                   ▼                                               │
│                          ┌─────────────────┐                                      │
│                          │  SEMANTIC SEARCH│                                      │
│                          │  "contrails     │                                      │
│                          │   over downtown"│                                      │
│                          └─────────────────┘                                      │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Pipeline Stages Detail

#### Stage 1: Ingestion (chunker.py)
- **Input**: RTSP/MJPEG stream URL
- **Output**: 5-30 second video chunks (temporary files)
- **Configurable**: chunk_duration, overlap, target_resolution
- **Adaptation**: Add continuous stream mode vs file-based batch

#### Stage 2: Still-Frame Detection (is_still_frame_chunk)
- **Input**: Video chunk
- **Output**: Boolean (skip or process)
- **Threshold**: JPEG size ratio >= 0.98 = static scene
- **Benefit**: 60-80% CPU savings for stationary cameras

#### Stage 3: Preprocessing (preprocess_chunk)
- **Input**: Video chunk
- **Output**: Downscaled 480p @ 5fps chunk
- **Benefit**: 95% pixel reduction → faster CV processing

#### Stage 4: CV Detection (contrail_detector.py)
- **Input**: Preprocessed frames
- **Output**: List[ContrailDetection] with vectors
- **Algorithms**: Hough transform, YOLOv8 (optional)

#### Stage 5: Flight Correlation (flight_service.py)
- **Input**: Detection timestamp + geolocation
- **Output**: Matched ICAO24 + flight metadata
- **Method**: Spatiotemporal proximity matching

#### Stage 6: Geolocalization (geocalc_service.py)
- **Input**: Camera metadata + pixel coordinates
- **Output**: WGS84 lat/lon/alt estimate
- **Methods**: Single-camera (assumed altitude) or triangulation

#### Stage 7: Archive (vector_store.py + embedder.py)
- **Input**: Detection clip + metadata
- **Output**: ChromaDB entry with embedding
- **Metadata**: Full detection event + flight data

#### Stage 8: Overlay (overlay.py adapted)
- **Input**: Detection clip + flight metadata
- **Output**: Clip with burned-in HUD
- **Display**: Callsign, altitude, speed, timestamp, location

---

## 4. ChromaDB Schema

### 4.1 Collection Structure

```python
# Collection name: "chemtrail_detections"
# Embedding space: Gemini Video or Qwen3-VL (per-backend isolation)

collection_metadata = {
    "hnsw:space": "cosine",
    "embedding_backend": "gemini",  # or "local"
    "embedding_model": "gemini-video",  # or "qwen8b", "qwen2b"
}
```

### 4.2 Metadata Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `chunk_id` | str | SHA256 hash of (source_file, start_time) | Yes |
| `source_file` | str | Path to original video chunk | Yes |
| `start_time` | float | Start time in chunk (seconds) | Yes |
| `end_time` | float | End time in chunk (seconds) | Yes |
| `camera_id` | UUID | Camera that captured detection | Yes |
| `camera_name` | str | Human-readable camera name | Yes |
| `camera_lat` | float | Camera latitude (WGS84) | Yes |
| `camera_lon` | float | Camera longitude (WGS84) | Yes |
| `camera_alt` | float | Camera altitude (meters AMSL) | Yes |
| `detection_type` | str | "contrail" or "aircraft" | Yes |
| `pixel_x` | float | Detection X (image space) | Yes |
| `pixel_y` | float | Detection Y (image space) | Yes |
| `azimuth` | float | Object azimuth (degrees) | Yes |
| `elevation` | float | Object elevation (degrees) | Yes |
| `estimated_lat` | float | Estimated object latitude | No |
| `estimated_lon` | float | Estimated object longitude | No |
| `estimated_alt` | float | Estimated object altitude | No |
| `confidence` | float | Detection confidence (0-1) | Yes |
| `contrail_vector` | JSON | {angle, length_px, width_px, persistence} | No |
| `icao24` | str | Matched flight ICAO24 hex | No |
| `callsign` | str | Matched flight callsign | No |
| `aircraft_type` | str | Matched flight aircraft type | No |
| `flight_altitude` | float | Flight barometric altitude | No |
| `flight_velocity` | float | Flight ground speed | No |
| `flight_heading` | float | Flight true track | No |
| `correlation_score` | float | Flight match confidence (0-1) | No |
| `position_method` | str | "single_camera", "triangulation", "flight_correlation" | No |
| `indexed_at` | ISO8601 | Archive timestamp | Yes |
| `overlay_applied` | bool | HUD overlay burned | Yes |
| `clip_path` | str | Path to overlaid clip (if rendered) | No |

### 4.3 ChromaDB Operations

```python
# Add detection to archive
def add_detection(
    chunk_id: str,
    embedding: list[float],
    metadata: DetectionMetadata  # dict with all fields above
) -> None:
    collection.upsert(
        ids=[chunk_id],
        embeddings=[embedding],
        metadatas=[metadata]
    )

# Search with metadata filters
def search(
    query_embedding: list[float],
    n_results: int = 10,
    where: dict = None,  # e.g., {"icao24": "4b1a02"}
    where_document: dict = None,  # e.g., {"$contains": "Boeing"}
) -> list[dict]:
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["metadatas", "distances"]
    )

# Remove detections by camera
def remove_camera_detections(camera_id: str) -> int:
    results = collection.get(where={"camera_id": camera_id})
    collection.delete(ids=results["ids"])
    return len(results["ids"])
```

---

## 5. Embedding Strategy

### 5.1 What Gets Embedded

| Content Type | Embedding Target | Rationale |
|--------------|------------------|-----------|
| **Detection clips (5-30s)** | Full video chunk | Primary semantic content - captures contrail appearance, motion, context |
| **Contrail crop images** | Still frame embedding | Optional - extract contrail region for focused similarity |
| **Full sky frames** | Still frame embedding | Optional - context for scene similarity (day/night, weather) |

### 5.2 Recommended Approach

**Primary**: Embed detection clips as video using Gemini Embedding API or Qwen3-VL.

**Rationale**:
- Video embeddings capture temporal dynamics (contrail formation, persistence, dissipation)
- Single embedding per detection event (simpler than frame-by-frame)
- Gemini Video natively handles 30s chunks at 1fps sampling

**Embedding Configuration**:
```python
# Gemini backend (default)
chunk_duration = 30  # seconds
target_fps = 1  # Gemini processes 1fps natively
target_resolution = 480  # reduces upload size, doesn't change billing

# Local backend (Qwen3-VL)
chunk_duration = 30  # seconds
target_fps = 5  # Local preprocessing
target_resolution = 480
max_frames = 32  # Qwen3-VL context limit
```

### 5.3 Embedding Flow

```
Detection Event (5-30s clip)
           │
           ▼
┌─────────────────────┐
│   preprocess_chunk  │  Downscale to 480p @ 5fps
│   (ffmpeg)          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   embed_video_chunk │  Gemini API or Qwen3-VL
│   (video embedder)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   ChromaDB.upsert   │  Store embedding + metadata
│   (vector + meta)   │
└─────────────────────┘
```

### 5.4 Embedding Backends Comparison

| Backend | Model | Cost | Speed | Quality | Use Case |
|---------|-------|------|-------|---------|----------|
| **Gemini API** | Gemini Video | ~$2.84/hr footage | Fast (~2-5s/chunk) | Best | Production, research |
| **Local (Qwen3-VL-8B)** | qwen8b | Free (GPU power) | Medium (~5-10s/chunk) | Good | Offline, privacy |
| **Local (Qwen3-VL-2B)** | qwen2b | Free (GPU power) | Fast (~3-6s/chunk) | Fair | Low-end hardware |

---

## 6. Module Reuse Strategy

### 6.1 Direct Reuse (No Modification)

```
sentrysearch/
├── embedder.py          → chemtrail/archive/embedder.py
└── base_embedder.py     → chemtrail/archive/base_embedder.py
```

**Rationale**: Embedder interface is backend-agnostic - works as-is.

### 6.2 Copy + Adapt (Minor Changes)

| Source File | Target File | Changes Required |
|-------------|-------------|------------------|
| `chunker.py` | `chemtrail/archive/chunker.py` | Add RTSP stream input, continuous mode, remove tempfile cleanup (streaming) |
| `store.py` | `chemtrail/storage/vector_store.py` | Extend metadata schema, add flight-specific query helpers |
| `search.py` | `chemtrail/archive/search.py` | Add metadata filtering (icao24, camera_id, date range) |
| `overlay.py` | `chemtrail/archive/overlay.py` | Replace Tesla SEI fields with OpenSky flight data, simplify HUD layout |

### 6.3 Replace (Not Applicable)

| SentrySearch Module | Chemtrail Replacement | Rationale |
|---------------------|----------------------|-----------|
| `metadata.py` (Tesla SEI) | N/A - use flight_service.py | Tesla-specific protobuf not applicable |
| `trimmer.py` | Use existing image_storage.py | Chemtrail already has clip storage |
| `dashcam_pb2.py` | N/A | Tesla-specific protobuf definitions |

### 6.4 New Modules Required

| Module | Purpose | Dependencies |
|--------|---------|--------------|
| `detection_service.py` | Orchestrate detection→archive pipeline | chunker, contrail_detector, flight_service, vector_store |
| `frame_preprocessor.py` | CV-friendly frame preprocessing | chunker.py::preprocess_chunk() |
| `flight_overlay.py` | Generate HUD from flight data | overlay.py adapted, flight_service |

---

## 7. Dependencies

### 7.1 New Python Packages

```python
# ChromaDB vector store
chromadb>=0.5.0

# Video processing (from SentrySearch)
imageio-ffmpeg>=0.4.0  # Bundled ffmpeg
geopy>=2.4.0           # Reverse geocoding (optional, for overlay)

# Embedding backends
google-genai>=0.1.0    # Gemini API (default)
# OR for local backend:
# torch>=2.0.0
# transformers>=4.35.0
# torchvision>=0.15.0
```

### 7.2 System Dependencies

```bash
# ffmpeg required (system or bundled via imageio-ffmpeg)
# Windows: bundled with imageio-ffmpeg
# macOS: brew install ffmpeg
# Linux: apt install ffmpeg
```

### 7.3 Optional Dependencies

```python
# Tesla-style overlay (adapted for flight data)
geopy>=2.4.0           # Reverse geocoding for location labels
```

---

## 8. Updated Implementation Phases

### 8.1 Phase 1 (Complete - Baseline)

**Status**: 73 tests passing

- OpenSky API integration
- Camera management
- Contrail detection (Hough)
- Flight correlation
- Geolocalization
- Basic detection logging

### 8.2 Phase 1.5: SentrySearch Integration (NEW)

**Priority**: HIGH  
**Timeline**: 2-3 weeks  
**Dependencies**: Phase 1 complete

| ID | Task | Priority | Est. Hours | SentrySearch Source |
|----|------|----------|------------|---------------------|
| 1.5.1 | Copy and adapt chunker.py | P0 | 8 | sentrysearch/chunker.py |
| 1.5.2 | Copy embedder.py (direct reuse) | P0 | 2 | sentrysearch/embedder.py |
| 1.5.3 | Copy and adapt store.py → vector_store.py | P0 | 10 | sentrysearch/store.py |
| 1.5.4 | Copy and adapt search.py | P0 | 6 | sentrysearch/search.py |
| 1.5.5 | Copy and adapt overlay.py for flight data | P1 | 12 | sentrysearch/overlay.py |
| 1.5.6 | Create detection_service.py (orchestrator) | P0 | 16 | NEW |
| 1.5.7 | Create frame_preprocessor.py | P1 | 6 | sentrysearch/chunker.py::preprocess_chunk() |
| 1.5.8 | Extend DB models for archive metadata | P0 | 4 | NEW schema |
| 1.5.9 | Integration tests (chunker + CV + archive) | P0 | 12 | NEW |
| 1.5.10 | API endpoints for semantic search | P1 | 8 | NEW |

**Deliverables**:
- Detection clips archived in ChromaDB
- Semantic search API endpoint
- Flight data overlay on clips
- Still-frame skipping (CPU savings)
- Preprocessed frames for CV pipeline

**New API Endpoints**:
```
GET /api/detections/search?q=natural_language_query
GET /api/detections/search/advanced?icao24=...&camera_id=...&date_from=...
POST /api/detections/{id}/overlay  # Generate HUD overlay
GET /api/archive/stats  # ChromaDB statistics
```

### 8.3 Phase 2: Enhancement (Unchanged)

**Priority**: HIGH  
**Timeline**: Weeks 4-6

- Automated flight correlation (improved algorithm)
- Multi-camera triangulation
- Aircraft detection (YOLOv8)
- Detection browser UI
- Map visualization

### 8.4 Phase 3: Scale (Unchanged)

**Priority**: MEDIUM  
**Timeline**: Weeks 7-9

- Motion tracking (optical flow)
- Deep learning contrail segmentation
- Batch processing pipeline
- Analytics dashboard

### 8.5 Phase 4: Production (Unchanged)

**Priority**: LOW  
**Timeline**: Weeks 10-12

- Multi-camera network
- External API expansion
- Docker containerization
- Documentation

---

## 9. Updated System Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CHEMTRAIL TRACKER - PHASE 1.5                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  EXTERNAL SOURCES                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │
│  │  RTSP/MJPEG │  │  OpenSky    │  │  Webcam     │                      │
│  │  Webcams    │  │  Network    │  │  APIs       │                      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                      │
│         │                 │                │                              │
│         └─────────────────┴────────────────┘                              │
│                           │                                               │
│  ┌────────────────────────▼─────────────────────────────────────────┐    │
│  │                    INGESTION LAYER                                │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │    │
│  │  │   chunker   │  │  still-frame│  │  preprocess │               │    │
│  │  │   (RTSP→    │  │   (skip     │  │  (480p @    │               │    │
│  │  │   segments) │  │   static)   │  │   5fps)     │               │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                           │                                               │
│                           ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    CV PIPELINE                                   │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │  Contrail   │  │  Aircraft   │  │   Motion    │              │    │
│  │  │  (Hough)    │  │  (YOLOv8)   │  │   Tracking  │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                           │                                               │
│                           ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    SERVICES                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │   Flight    │  │    Geo      │  │  Detection  │              │    │
│  │  │  Correlation│  │  Calculator │  │  Service    │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                           │                                               │
│                           ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    ARCHIVE LAYER (NEW)                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │   Embedder  │  │  ChromaDB   │  │   Overlay   │              │    │
│  │  │  (Gemini/   │  │  (vectors   │  │  (HUD burn) │              │    │
│  │  │   Qwen3-VL) │  │   + meta)   │  │             │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                           │                                               │
│                           ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    SEARCH API (NEW)                              │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │  GET /api/detections/search?q="contrails over downtown" │    │    │
│  │  │  GET /api/detections/search?icao24=4b1a02&date_from=... │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  DATA LAYER                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  PostgreSQL │  │   Redis     │  │   Local     │  │  ChromaDB   │    │
│  │  (Primary)  │  │   (Cache)   │  │   Storage   │  │  (Archive)  │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Risk Assessment

### 10.1 Integration Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ChromaDB schema mismatch | Low | Medium | Version pin chromadb, test migration path |
| Embedding API cost overrun | Medium | Low | Set Gemini spending limits, use local fallback |
| RTSP stream compatibility | Medium | Medium | Test with major webcam providers, add fallback |
| Still-frame false negatives | Low | Low | Tunable threshold, disable flag |
| Overlay rendering performance | Medium | Low | Async processing, cache rendered clips |

### 10.2 Technical Debt Considerations

1. **Code duplication**: Copying SentrySearch modules creates maintenance burden
   - **Mitigation**: Document source, consider extracting shared library
   
2. **Dependency coupling**: Tied to SentrySearch module structure
   - **Mitigation**: Wrap in adapter interfaces, isolate imports

3. **ChromaDB vendor lock-in**: Vector store format is proprietary
   - **Mitigation**: Abstract behind vector_store.py interface

---

## 11. Success Metrics

### 11.1 Technical KPIs (Phase 1.5)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Detection archive rate | >95% | Detections stored / detections generated |
| Semantic search latency | <500ms | P95 query response time |
| Still-frame skip rate | 60-80% | Skipped chunks / total chunks (stationary cams) |
| CPU reduction | 40-60% | Preprocessing vs raw frame CV load |
| Embedding cost | <$5/day | Gemini API daily spend (10 cameras) |

### 11.2 Functional Validation

**Query Examples** (post-Phase 1.5):
- "Find contrails from Boeing 737"
- "Show detections over downtown Seattle"
- "Contrails from flights departing JFK yesterday"
- "High altitude contrails (above 30000ft)"
- "Persistent contrails lasting over 60 seconds"

---

## 12. Appendix: File Inventory

### 12.1 Files to Copy from SentrySearch

```
sentrysearch/sentrysearch/
├── chunker.py           → chemtrail/archive/chunker.py
├── embedder.py          → chemtrail/archive/embedder.py
├── base_embedder.py     → chemtrail/archive/base_embedder.py
├── store.py             → chemtrail/storage/vector_store.py
├── search.py            → chemtrail/archive/search.py
├── overlay.py           → chemtrail/archive/overlay.py
└── gemini_embedder.py   → chemtrail/archive/gemini_embedder.py
```

### 12.2 Files to Create (New)

```
backend/chemtrail/
├── services/detection_service.py
├── cv/frame_preprocessor.py
├── archive/__init__.py
└── archive/flight_overlay.py
```

### 12.3 Files to Modify

```
backend/db/models.py          # Add DetectionArchive model
backend/chemtrail/handlers/detection_handler.py  # Add archive call
backend/common/requirements.txt  # Add chromadb, imageio-ffmpeg, google-genai
```

---

*Document prepared by Dr. Sarah Kim, Technical Product Strategist & Engineering Lead*
