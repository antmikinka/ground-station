# Chemtrail Webcam Tracker - Phase 1 Implementation Plan

**Document Version:** 1.0.0  
**Phase:** Foundation (Weeks 1-3)  
**Status:** Ready for Development  
**Created:** 2026-04-11  

---

## Executive Summary

Phase 1 establishes the foundational infrastructure for the Chemtrail Webcam Tracker system. This phase focuses on database schema creation, OpenSky API integration, camera management system, image ingestion pipeline, and basic contrail detection using Hough transform algorithms.

### Phase 1 Goals

1. **Database Foundation**: Extend existing SQLAlchemy models with chemtrail-specific schema
2. **Flight Data Integration**: Implement OpenSky Network API client for flight data
3. **Camera Management**: Create CRUD endpoints for camera configuration with geolocalization metadata
4. **Image Pipeline**: Build image ingestion from RTSP/MJPEG sources
5. **Contrail Detection MVP**: Implement Hough transform-based line detection for contrail identification

---

## Sprint Breakdown

### Sprint 1: Database & API Foundation (Days 1-5)

#### Objectives
- Create database migrations for chemtrail schema
- Implement OpenSky API client
- Set up basic service layer structure

#### Tasks

| Task ID | Description | File Path(s) | Priority | Est. Hours | Dependencies |
|---------|-------------|--------------|----------|------------|--------------|
| 1.1.1 | Add chemtrail models to `backend/db/models.py` | `backend/db/models.py` | P0 | 4 | None |
| 1.1.2 | Create Alembic migration for chemtrail tables | `backend/alembic/versions/xxxx_add_chemtrail_tracker_schema.py` | P0 | 3 | 1.1.1 |
| 1.2.1 | Create OpenSky API client module | `backend/chemtrail/api/opensky_client.py` | P0 | 6 | None |
| 1.2.2 | Create OpenSky service layer | `backend/chemtrail/services/flight_service.py` | P0 | 4 | 1.2.1 |
| 1.3.1 | Create camera CRUD operations | `backend/crud/chemtrail_cameras.py` | P0 | 4 | 1.1.1 |
| 1.3.2 | Create camera FastAPI router | `backend/handlers/entities/chemtrail_cameras.py` | P0 | 4 | 1.3.1 |

#### Deliverables
- [ ] Database schema with `chemtrail_cameras`, `chemtrail_detections`, `flight_cache` tables
- [ ] Working OpenSky API client with rate limiting
- [ ] Camera CRUD API endpoints

#### Milestone Checkpoint: End of Sprint 1
- Database migration runs successfully
- OpenSky API returns flight data
- Camera CRUD operations functional via API

---

### Sprint 2: Camera Management & Image Ingestion (Days 6-10)

#### Objectives
- Complete camera management UI integration
- Build image ingestion pipeline for MJPEG/RTSP streams
- Create image storage and retrieval system

#### Tasks

| Task ID | Description | File Path(s) | Priority | Est. Hours | Dependencies |
|---------|-------------|--------------|----------|------------|--------------|
| 2.1.1 | Create camera service layer | `backend/chemtrail/services/camera_service.py` | P0 | 4 | 1.3.2 |
| 2.1.2 | Create geocalc service for az/el calculations | `backend/chemtrail/services/geocalc_service.py` | P1 | 6 | None |
| 2.2.1 | Create image ingestion worker | `backend/chemtrail/workers/ingestion_worker.py` | P0 | 8 | 2.1.1 |
| 2.2.2 | Create MJPEG stream handler | `backend/chemtrail/video/mjpeg_handler.py` | P0 | 6 | 2.2.1 |
| 2.2.3 | Create RTSP stream handler | `backend/chemtrail/video/rtsp_handler.py` | P1 | 8 | 2.2.1 |
| 2.3.1 | Create image storage utility | `backend/chemtrail/storage/image_storage.py` | P0 | 4 | 2.2.1 |
| 2.4.1 | Create detection CRUD operations | `backend/crud/chemtrail_detections.py` | P0 | 4 | 1.1.1 |

#### Deliverables
- [ ] Camera service with geolocalization support
- [ ] Working MJPEG stream ingestion
- [ ] Image storage with path management
- [ ] Detection logging infrastructure

#### Milestone Checkpoint: End of Sprint 2
- Cameras can be added/edited with full metadata
- MJPEG stream successfully captured and stored
- Images stored with proper metadata linking to camera

---

### Sprint 3: Contrail Detection & Integration (Days 11-15)

#### Objectives
- Implement contrail detection algorithm using Hough transform
- Create detection processing pipeline
- Build flight correlation (manual mode)
- End-to-end integration testing

#### Tasks

| Task ID | Description | File Path(s) | Priority | Est. Hours | Dependencies |
|---------|-------------|--------------|----------|------------|--------------|
| 3.1.1 | Create contrail detector module | `backend/chemtrail/cv/contrail_detector.py` | P0 | 10 | 2.2.1 |
| 3.1.2 | Create CV utilities module | `backend/chemtrail/cv/cv_utils.py` | P0 | 4 | None |
| 3.2.1 | Create detection service layer | `backend/chemtrail/services/detection_service.py` | P0 | 6 | 3.1.1, 2.4.1 |
| 3.2.2 | Create CV worker for background processing | `backend/chemtrail/workers/cv_worker.py` | P0 | 8 | 3.1.1 |
| 3.3.1 | Create flight correlation service | `backend/chemtrail/services/correlation_service.py` | P1 | 6 | 1.2.2, 3.2.1 |
| 3.4.1 | Create detection FastAPI router | `backend/handlers/entities/chemtrail_detections.py` | P0 | 4 | 3.2.1 |
| 3.5.1 | Create unit tests for OpenSky client | `backend/tests/chemtrail/test_opensky_client.py` | P0 | 4 | 1.2.1 |
| 3.5.2 | Create unit tests for contrail detector | `backend/tests/chemtrail/test_contrail_detector.py` | P0 | 6 | 3.1.1 |
| 3.5.3 | Create integration tests | `backend/tests/chemtrail/test_detection_pipeline.py` | P1 | 8 | 3.2.1 |

#### Deliverables
- [ ] Working contrail detection with Hough transform
- [ ] Background processing pipeline
- [ ] Flight correlation (manual)
- [ ] Comprehensive test suite

#### Milestone Checkpoint: End of Sprint 3 (Phase 1 Complete)
- Contrails detected in test images with >70% accuracy
- Detection logged to database with metadata
- Flight data correlated with detections
- All Phase 1 tests passing

---

## File Structure

### New Directories to Create

```
backend/chemtrail/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── opensky_client.py
│   └── webcam_clients.py
├── services/
│   ├── __init__.py
│   ├── camera_service.py
│   ├── detection_service.py
│   ├── flight_service.py
│   ├── geocalc_service.py
│   └── correlation_service.py
├── workers/
│   ├── __init__.py
│   ├── cv_worker.py
│   └── ingestion_worker.py
├── cv/
│   ├── __init__.py
│   ├── contrail_detector.py
│   └── cv_utils.py
├── video/
│   ├── __init__.py
│   ├── mjpeg_handler.py
│   └── rtsp_handler.py
└── storage/
    ├── __init__.py
    └── image_storage.py

backend/tests/chemtrail/
├── __init__.py
├── test_opensky_client.py
├── test_contrail_detector.py
├── test_camera_service.py
├── test_geocalc_service.py
└── test_detection_pipeline.py
```

### Files to Modify

| File | Changes |
|------|---------|
| `backend/db/models.py` | Add `ChemtrailCameras`, `ChemtrailDetections`, `FlightCache`, `DetectionFrames`, `TriangulationResults` models |
| `backend/crud/__init__.py` | Export new chemtrail CRUD modules |
| `backend/handlers/entities/__init__.py` | Register new chemtrail handlers |
| `backend/pyproject.toml` | Add OpenCV, scipy, scikit-image, requests dependencies |

---

## Dependencies

### Python Packages to Install

Add to `backend/pyproject.toml` dependencies:

```python
# Computer Vision (Phase 1)
opencv-python>=4.8.0
opencv-contrib-python>=4.8.0
scikit-image>=0.21.0

# Geospatial calculations
pyproj>=3.6.0
geopy>=2.4.0

# HTTP client (already have httpx, but ensure version)
httpx>=0.25.0

# Image processing
Pillow>=10.0.0
imageio>=2.31.0
```

### Installation Command

```bash
cd backend
pip install opencv-python opencv-contrib-python scikit-image pyproj geopy imageio
```

---

## Test Strategy

### Module-Level Tests

| Module | Test File | Test Coverage |
|--------|-----------|---------------|
| `opensky_client.py` | `test_opensky_client.py` | API connection, rate limiting, data parsing |
| `camera_service.py` | `test_camera_service.py` | CRUD operations, validation |
| `geocalc_service.py` | `test_geocalc_service.py` | Az/el calculations, edge cases |
| `contrail_detector.py` | `test_contrail_detector.py` | Detection accuracy, false positive rate |
| `detection_pipeline.py` | `test_detection_pipeline.py` | End-to-end flow |

### Test Commands

```bash
# Run all Phase 1 tests
pytest backend/tests/chemtrail/ -v --cov=chemtrail --cov-report=term-missing

# Run specific module tests
pytest backend/tests/chemtrail/test_opensky_client.py -v
pytest backend/tests/chemtrail/test_contrail_detector.py -v

# Run with coverage
pytest backend/tests/chemtrail/ --cov=chemtrail --cov-report=html
```

### Test Data Requirements

- Sample MJPEG stream URL for integration testing
- Test images with known contrails for detection validation
- Mock OpenSky API responses for unit testing

---

## Risk Mitigation

### Sprint 1 Risks

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| OpenSky API rate limiting blocks development | Medium | High | Implement caching layer; use mock responses for unit tests; member account for higher limits |
| Database migration conflicts with existing schema | Low | High | Test migration on separate DB first; create rollback script |
| SQLAlchemy model conflicts | Low | Medium | Review existing models; follow existing patterns exactly |

### Sprint 2 Risks

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| MJPEG/RTSP stream format incompatibility | Medium | Medium | Test with multiple stream sources; implement format detection |
| Image storage performance issues | Medium | Medium | Use async file operations; implement batch writes |
| Camera metadata calibration complexity | High | Medium | Start with manual entry; add calibration UI in Phase 2 |

### Sprint 3 Risks

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| Hough transform produces too many false positives | High | High | Implement multi-stage validation; tune thresholds; add ML filter placeholder |
| CV processing too slow for real-time | Medium | Medium | Run detection in background worker; optimize with numpy vectorization |
| Flight correlation accuracy too low | Medium | Medium | Start with time-window based matching; improve algorithm in Phase 2 |

---

## Success Criteria for Phase 1

### Technical Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Database schema complete | 100% tables created | Migration verification |
| OpenSky API integration | Working with rate limiting | API response tests |
| Camera CRUD operations | All 4 operations functional | API endpoint tests |
| Image ingestion | MJPEG stream captured | Integration test |
| Contrail detection | >70% accuracy on test set | Manual validation of 100 test images |
| False positive rate | <30% | Test image analysis |
| Processing latency | <10s per frame | Performance benchmark |
| Test coverage | >80% | pytest --cov report |

### Deliverable Checklist

- [ ] Database migration executed successfully
- [ ] OpenSky API client returns flight data
- [ ] Camera API endpoints functional (create, read, update, delete)
- [ ] MJPEG stream ingestion working
- [ ] Contrail detection produces valid detections
- [ ] Detection records stored in database
- [ ] All unit tests passing
- [ ] Integration test pipeline working

---

## Handoff to Development Team

### Pre-Development Setup

1. **Branch**: Ensure working on `chemtrail-webcam-tracker` branch
2. **Dependencies**: Install new Python packages
3. **Database**: Run Alembic migration
4. **Test Data**: Prepare sample images and stream URLs

### Code Review Checklist

- [ ] Follow existing CRUD patterns (see `backend/crud/locations.py`)
- [ ] Follow existing handler patterns (see `backend/handlers/entities/locations.py`)
- [ ] Use async/await consistently
- [ ] Include proper error handling and logging
- [ ] Add type hints to all functions
- [ ] Write unit tests for all new modules
- [ ] Update API documentation

### Integration Points

| Component | Integration Point | Notes |
|-----------|-------------------|-------|
| Database | `backend/db/models.py` | Extend existing Base class |
| CRUD | `backend/crud/__init__.py` | Export new modules |
| Handlers | `backend/handlers/entities/__init__.py` | Register new handlers |
| App startup | `backend/app.py` | No changes needed for Phase 1 |
| Pyproject | `backend/pyproject.toml` | Add dependencies |

---

## Appendix: Reference Implementations

### CRUD Pattern Example

See `backend/crud/locations.py` for the standard pattern:
- `fetch_all_*` - Get all records
- `fetch_*` - Get single record
- `add_*` - Create new record
- `edit_*` - Update existing record
- `delete_*` - Remove record

### Handler Pattern Example

See `backend/handlers/entities/locations.py`:
- Use `AsyncSessionLocal` for DB sessions
- Call CRUD functions
- Return standardized response format
- Register with handler registry

### Model Pattern Example

See `backend/db/models.py`:
- Use `Base` declarative class
- Include `added` and `updated` timestamps
- Use `AwareDateTime` for timezone handling
- Use `UUID` for primary keys

---

*Document prepared for Chemtrail Webcam Tracker Phase 1 Implementation*
