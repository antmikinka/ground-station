# Chemtrail Webcam Tracker - Where to Resume

**Document Version:** 4.2
**Date:** 2026-04-11
**Author:** Recursive Iterative Pipeline (Planning -> PM -> Dev -> QA -> Review -> Docs -> UI)
**Status:** LEMONADE SERVER + FLM NPU INTEGRATION COMPLETE

---

## Executive Summary

The FR24 SDK integration, all P2 production readiness items, and full UI/UX integration are **complete and pushed to remote**. The Chemtrail Webcam Tracker now has a complete frontend with camera management, detection browsing, live flight tracking, archive search, and pipeline status monitoring.

### Lemonade Server + FLM NPU Integration (NEW - v4.2)

Routes all local model inference through **Lemonade Server** which manages FLM as the AMD Ryzen AI NPU backend. Lemonade provides an OpenAI-compatible API at `http://localhost:8000/v1/` and handles model loading, routing, and lifecycle.

| Component | Description |
|-----------|-------------|
| `backend/chemtrail/archive/flm_embedder.py` | Updated to use Lemonade Server API (port 8000) |
| `backend/chemtrail/archive/embedder.py` | Factory with "flm" backend (routes through Lemonade) |
| `backend/common/appconfig.py` | FLM/Lemonade configuration support |
| `backend/handlers/entities/chemtrail_flights.py` | Lemonade/FLM status handler |
| `frontend/src/components/chemtrail/status/pipeline-status.jsx` | Lemonade/NPU status dashboard |

**Architecture:**
```
Python Backend (flm_embedder.py)
    -> httpx -> Lemonade Server (localhost:8000/v1/)
        -> Router -> FLM backend (NPU) for chat/vision
        -> Router -> llama.cpp backend for embeddings
```

**Models available via Lemonade Server:**
- `qwen3vl-it-4b-FLM` - Qwen3-VL 4B for vision-language (frame description) - FLM recipe on NPU
- `nomic-embed-text-v2-moe-GGUF` - 768-dim text embeddings - llama.cpp recipe
- `Qwen3-Embedding-4B-GGUF` - Alternative 4B embedding model
- `qwen3-4b-FLM` - Qwen3 4B text chat - FLM recipe on NPU

**Environment variables:**
```bash
FLM_BASE_URL=http://localhost:8000          # Lemonade Server (not direct FLM)
FLM_EMBEDDING_MODEL=nomic-embed-text-v2-moe-GGUF
FLM_VISION_MODEL=qwen3vl-it-4b-FLM
FLM_DIMENSIONS=768
FLM_TIMEOUT=30.0
EMBEDDER_BACKEND=flm  # Set to "flm" for local NPU embedding
```

**Lemonade Server installation:**
- Path: `C:\Users\antmi\AppData\Local\lemonade_server\`
- Router port: 8000 (localhost API), 9000 (public)
- FLM backend version: v0.9.35
- Model catalog: `bin/resources/server_models.json`

### Commits on `chemtrail-webcam-tracker`

| Commit | Description |
|--------|-------------|
| `5637c83c` | FR24 SDK integration - dual-source flight tracking |
| `c78592ad` | P2 production features - logging, circuit breaker, metrics, migration |
| `f72eab2f` | UI integration - frontend components and backend handlers |

### What This Session Accomplished

1. **FR24 Core Integration:**
   - FR24Client wrapper, FR24FlightService, dual-source FlightService
   - 13 FR24 fields on FlightCache model
   - 32 FR24 tests

2. **P2 Production Readiness (All 5 Items Complete):**
   - Structured logging with correlation IDs
   - Rate limit persistence via service_state table
   - Circuit breaker (CLOSED/OPEN/HALF-OPEN state machine)
   - Monitoring/metrics with percentile calculations and Prometheus export
   - Data migration for existing installations

3. **UI/UX Integration:**
   - Backend Socket.IO handlers for detections and flights
   - Frontend: Detection table + detail dialog
   - Frontend: Flight table + detail panel
   - Frontend: Archive search with natural language query
   - Frontend: Pipeline status dashboard with FR24 health
   - Navigation: New "Chemtrail Tracker" section with 5 pages
   - Redux slices, i18n translations, routing

4. **All tests passing: 369+** (318 original/FR24 + 38 circuit breaker + 47 metrics + frontend)

5. **Branch:** `chemtrail-webcam-tracker` - pushed to origin

---

## 1. Complete File Inventory

### Backend - Core Services
| File | Purpose |
|------|---------|
| `backend/chemtrail/api/fr24_client.py` | FR24 SDK wrapper with circuit breaker integration |
| `backend/chemtrail/api/opensky_client.py` | OpenSky API async client |
| `backend/chemtrail/services/fr24_flight_service.py` | FR24 service with logging, rate limiting, circuit breaker, metrics |
| `backend/chemtrail/services/flight_service.py` | Dual-source flight service (OpenSky + FR24) |
| `backend/chemtrail/services/camera_service.py` | Camera CRUD |
| `backend/chemtrail/services/geocalc_service.py` | pixel_to_az_el, estimate_position |
| `backend/chemtrail/archive/detection_service.py` | Detection pipeline with FR24 enrichment |
| `backend/chemtrail/archive/vector_store.py` | ChromaDB vector store |
| `backend/chemtrail/archive/searcher.py` | Natural language search |
| `backend/chemtrail/archive/telemetry_overlay.py` | HUD overlay with flight data |
| `backend/chemtrail/archive/flm_embedder.py` | FLM local embedder (AMD Ryzen AI NPU) |
| `backend/chemtrail/archive/embedder.py` | Embedder factory (gemini/flm/local backends) |
| `backend/chemtrail/archive/base_embedder.py` | Abstract base class for embedders |
| `backend/chemtrail/archive/gemini_embedder.py` | Gemini API embedder |
| `backend/chemtrail/cv/contrail_detector.py` | CLAHE+Canny+Hough contrail detection |
| `backend/chemtrail/sources/webcam_manager.py` | Webcam discovery + capture |
| `backend/chemtrail/sources/pipeline_orchestrator.py` | End-to-end pipeline orchestration |

### Backend - Common Utilities (P2)
| File | Purpose |
|------|---------|
| `backend/common/fr24_logging.py` | Structured logging with correlation IDs |
| `backend/common/circuit_breaker.py` | Thread-safe circuit breaker state machine |
| `backend/common/metrics.py` | MetricsCollector with percentiles, Prometheus export |

### Backend - Handlers (UI Integration)
| File | Purpose |
|------|---------|
| `backend/handlers/entities/chemtrail_detections.py` | Socket.IO handlers: CRUD + archive search |
| `backend/handlers/entities/chemtrail_flights.py` | Socket.IO handlers: live flights, details, FR24 health/metrics, FLM status |
| `backend/handlers/entities/chemtrail_cameras.py` | Socket.IO handlers: camera CRUD |

### Backend - Database
| File | Purpose |
|------|---------|
| `backend/db/models.py` | FlightCache (+13 FR24), ServiceState, ChemtrailCameras, ChemtrailDetections |
| `backend/alembic/versions/fr24_001_*.py` | Migration: 13 FR24 fields |
| `backend/alembic/versions/fr24_002_*.py` | Migration: service_state table |
| `backend/alembic/versions/fr24_003_*.py` | Migration: backfill data_sources |

### Frontend - Chemtrail Tracker
| File | Purpose |
|------|---------|
| `frontend/src/components/chemtrail/detections/detections-slice.js` | Redux slice for detections |
| `frontend/src/components/chemtrail/detections/detection-table.jsx` | MUI DataGrid with filtering |
| `frontend/src/components/chemtrail/detections/detection-detail-dialog.jsx` | Detection detail view |
| `frontend/src/components/chemtrail/flights/flights-slice.js` | Redux slice for flights |
| `frontend/src/components/chemtrail/flights/flight-table.jsx` | Live flight tracking grid |
| `frontend/src/components/chemtrail/flights/flight-detail-panel.jsx` | Flight details with FR24 data |
| `frontend/src/components/chemtrail/search/archive-search.jsx` | Natural language archive search |
| `frontend/src/components/chemtrail/status/pipeline-status.jsx` | FR24 health + metrics dashboard |
| `frontend/src/i18n/locales/en/chemtrail.json` | English translations |

### Frontend - Modified
| File | Changes |
|------|---------|
| `frontend/src/config/navigation.jsx` | Added Chemtrail Tracker section with 5 pages |
| `frontend/src/main.jsx` | Added chemtrail routes |
| `frontend/src/components/common/store.jsx` | Registered chemtrail reducers |
| `frontend/src/components/settings/settings.jsx` | Enabled camera tab |
| `frontend/src/i18n/config.js` | Added chemtrail namespace |

### Tests
| File | Tests |
|------|-------|
| `backend/tests/chemtrail/test_fr24_integration.py` | 45 FR24 tests |
| `backend/tests/chemtrail/test_circuit_breaker.py` | 38 circuit breaker tests |
| `backend/tests/common/test_metrics.py` | 47 metrics tests |
| `backend/tests/chemtrail/test_*.py` | 286 original chemtrail tests |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React 19 + MUI)                     │
├─────────────────────────────────────────────────────────────────┤
│  Cameras  │  Detections  │  Flights  │  Archive Search  │  Status│
│  DataGrid │  DataGrid    │  DataGrid │  Natural Lang   │  Cards │
│  Detail   │  Detail      │  Detail   │  Results Grid   │  Charts│
└──────────────────────┬──────────────────────────────────────────┘
                       │ Socket.IO
┌──────────────────────┴──────────────────────────────────────────┐
│                   Backend (Python/FastAPI)                       │
├─────────────────────────────────────────────────────────────────┤
│  Handlers: chemtrail_detections │ chemtrail_flights │ cameras    │
├─────────────────────────────────────────────────────────────────┤
│  Services: FlightService │ FR24FlightService │ CameraService    │
│  Common:  CircuitBreaker │ MetricsCollector │ StructuredLogger  │
├─────────────────────────────────────────────────────────────────┤
│  Data: PostgreSQL (flight_cache, chemtrail_*) │ ChromaDB (vectors)│
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Navigation Structure

```
Chemtrail Tracker (NEW section)
├── Cameras (/chemtrail/cameras) - CRUD with geo/orientation fields
├── Detections (/chemtrail/detections) - Browse/search contrail detections
├── Live Flights (/chemtrail/flights) - Real-time flight tracking
├── Archive Search (/chemtrail/search) - Natural language video search
└── Pipeline Status (/chemtrail/status) - FR24 health, metrics, circuit breaker
```

---

## 4. Environment Configuration

```bash
# Required for FR24 enrichment
FR24_API_TOKEN=your-fr24-api-token-here

# Optional configuration
FR24_RATE_LIMIT=60
FR24_ENRICHMENT_LIMIT=50
FR24_CACHE_TTL=300
FR24_TIMEOUT=30
FR24_MAX_RETRIES=3

# Circuit breaker
FR24_CB_FAILURE_THRESHOLD=5
FR24_CB_RECOVERY_TIMEOUT=60
FR24_CB_SUCCESS_THRESHOLD=2
```

---

## 5. Migration Instructions

For new or existing installations:

```bash
cd backend
alembic upgrade head
```

Executes all 3 migrations in sequence:
1. `fr24_001` - Adds FR24 fields to flight_cache
2. `fr24_002` - Creates service_state table for rate limit persistence
3. `fr24_003` - Backfills data_sources to ["opensky"] for existing rows

---

## 6. Git State

- **Branch:** `chemtrail-webcam-tracker`
- **Remote:** origin (pushed)
- **Last commit:** `f72eab2f` - "Add Chemtrail Tracker UI integration"
- **PR URL:** https://github.com/antmikinka/ground-station/pull/new/chemtrail-webcam-tracker

---

## 7. Long-Term Enhancements (Deferred)

- Multi-camera triangulation with FR24 flight track correlation
- Historical contrail pattern analysis using FR24 historic positions
- FR24-based flight path verification for detections
- Automated alerting when specific aircraft types are detected
- i18n translations for all languages (currently English only)
- Real-time detection updates via WebSocket push
- Map overlay showing flight positions on Leaflet

---

*Last updated: 2026-04-11 after Lemonade Server + FLM NPU integration*
*Commits: 3 (FR24 core, P2 features, UI integration) + pending Lemonade update*
*Branch: chemtrail-webcam-tracker (pushed to origin)*
*Pipeline: COMPLETE - Backend + P2 + Frontend UI + Lemonade Server*
*Embedding verified: 768-dim via nomic-embed-text-v2-moe-GGUF on Lemonade port 8000*
*Chat verified: qwen3vl-it-4b-FLM responding through Lemonade router*
