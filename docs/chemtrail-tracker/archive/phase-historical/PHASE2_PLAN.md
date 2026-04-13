# Chemtrail Webcam Tracker - Phase 2 Implementation Plan
## Footage Acquisition, Sorting, and End-to-End Pipeline Orchestration

**Version:** 1.0.0  
**Author:** Dr. Sarah Kim, Technical Product Strategist & Engineering Lead  
**Date:** 2026-04-11  
**Timeline:** 2 Weeks (10 Working Days)  
**Status:** Ready for Execution

---

## Executive Summary

This document provides the detailed implementation plan for Phase 2 of the Chemtrail Webcam Tracker. The phase delivers:

1. **Live Webcam Feed Acquisition** - RTSP/MJPEG stream ingestion
2. **Historical Video Ingestion** - Local file scanning and cataloging
3. **Video Sorting & Cataloging** - Quality scoring, weather tagging, metadata indexing
4. **Pipeline Orchestration** - End-to-end workflow coordination

### Deliverables

| Deliverable | File/Module | Priority |
|-------------|-------------|----------|
| Webcam Manager | `sources/webcam_manager.py` | P0 |
| Historical Ingestor | `sources/historical_ingestor.py` | P0 |
| Video Catalog | `sources/video_catalog.py` | P0 |
| Weather Enrichment | `sources/weather_enrichment.py` | P1 |
| Pipeline Orchestrator | `sources/pipeline_orchestrator.py` | P0 |
| Database Migrations | `db/migrations/phase2_*.sql` | P0 |
| Integration Tests | `tests/chemtrail/test_phase2_*.py` | P0 |
| API Endpoints | `api/video_sources.py` | P1 |

---

## Sprint Breakdown (2 Weeks)

### Week 1: Foundation Modules

| Day | Focus | Tasks | Deliverables |
|-----|-------|-------|--------------|
| **Day 1** | Database & Catalog | Schema migration, VideoCatalog class | DB tables, catalog module |
| **Day 2** | Historical Ingestion | VideoScanner, MetadataExtractor | historical_ingestor.py |
| **Day 3** | Webcam Management | StreamConnection, HealthMonitor | webcam_manager.py |
| **Day 4** | Weather Enrichment | Open-Meteo integration | weather_enrichment.py |
| **Day 5** | Quality Scoring | Video quality analysis | Quality scoring functions |

### Week 2: Orchestration & Integration

| Day | Focus | Tasks | Deliverables |
|-----|-------|-------|--------------|
| **Day 6** | Pipeline Orchestrator | Workflow engine, job queue | pipeline_orchestrator.py |
| **Day 7** | API Endpoints | REST API for video sources | api/video_sources.py |
| **Day 8** | Integration Testing | End-to-end test suite | test_phase2_*.py |
| **Day 9** | Documentation & Polish | README updates, docstrings | Updated docs |
| **Day 10** | Testing & Bug Fixes | Full test run, fixes | Test report |

---

## Detailed Task Breakdown

### Day 1: Database & Video Catalog

#### Task 1.1: Database Schema Migration
**File:** `backend/db/migrations/phase2_video_catalog.sql`
**Priority:** P0
**Estimated Hours:** 2

```sql
-- Create video_catalog table
-- Create indexes for camera_id, time range, quality_score, weather_condition
-- Add constraints for processing_status enum
```

**Acceptance Criteria:**
- [ ] Migration file created
- [ ] Migration can be applied successfully
- [ ] Indexes created for performance
- [ ] Rollback migration tested

#### Task 1.2: VideoCatalog Class (Database Layer)
**File:** `backend/chemtrail/sources/video_catalog.py`
**Priority:** P0
**Estimated Hours:** 4

**Implementation:**
```python
class VideoCatalog:
    async def initialize() -> None
    async def add_video(video: VideoRecord) -> None
    async def search(filters...) -> List[VideoRecord]
    async def get_pending_processing() -> List[VideoRecord]
    async def update_processing_status(id, status) -> None
    async def update_weather(id, weather_data) -> None
    async def update_quality(id, quality_score) -> None
```

**Acceptance Criteria:**
- [ ] All CRUD operations implemented
- [ ] Search with filters working (camera, date, quality, weather)
- [ ] Async operations with proper error handling
- [ ] Unit tests passing

#### Task 1.3: Data Classes and Enums
**File:** `backend/chemtrail/sources/__init__.py`
**Priority:** P0
**Estimated Hours:** 1

```python
@dataclass
class VideoRecord:
    id: str
    source_type: str
    # ... all fields from architecture doc

class ProcessingStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

### Day 2: Historical Video Ingestion

#### Task 2.1: VideoScanner Class
**File:** `backend/chemtrail/sources/historical_ingestor.py`
**Priority:** P0
**Estimated Hours:** 3

```python
class VideoScanner:
    SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}
    
    async def scan(directory: str, recursive: bool) -> ScanResult
    async def _is_video_file(path: Path) -> bool
```

**Acceptance Criteria:**
- [ ] Recursive directory scanning
- [ ] File extension filtering
- [ ] Returns sorted list of absolute paths
- [ ] Handles permission errors gracefully

#### Task 2.2: MetadataExtractor Class
**File:** `backend/chemtrail/sources/historical_ingestor.py`
**Priority:** P0
**Estimated Hours:** 3

```python
class MetadataExtractor:
    async def extract(file_path: str) -> VideoMetadata
    async def _run_ffprobe(file_path: str) -> dict
    async def _calculate_checksum(file_path: str) -> str
```

**Metadata to Extract:**
- Duration, resolution, FPS, codec
- File size, creation date
- SHA256 checksum for deduplication

**Acceptance Criteria:**
- [ ] ffprobe integration working
- [ ] All metadata fields populated
- [ ] Checksum calculation correct
- [ ] Error handling for corrupt files

#### Task 2.3: HistoricalIngestor Main Class
**File:** `backend/chemtrail/sources/historical_ingestor.py`
**Priority:** P0
**Estimated Hours:** 2

```python
class HistoricalIngestor:
    async def scan_directory(directory: str) -> ScanResult
    async def import_video(file_path: str, camera_id: str) -> str
    async def _check_duplicate(checksum: str) -> Optional[str]
    async def _create_catalog_entry(metadata, camera_id) -> str
```

**Acceptance Criteria:**
- [ ] Full scan-to-import flow working
- [ ] Deduplication by checksum
- [ ] Returns video_id on success
- [ ] Integration test passing

---

### Day 3: Webcam Management

#### Task 3.1: StreamConnection Class
**File:** `backend/chemtrail/sources/webcam_manager.py`
**Priority:** P0
**Estimated Hours:** 3

```python
class StreamConnection:
    async def start() -> None
    async def stop() -> None
    def _build_ffmpeg_cmd(output_pattern: str) -> List[str]
```

**Stream Types:**
- RTSP (with TCP transport)
- MJPEG (direct HTTP)
- HLS (m3u8 playlists)

**Acceptance Criteria:**
- [ ] ffmpeg subprocess launches correctly
- [ ] Segment files created at expected intervals
- [ ] Clean stop with process termination
- [ ] Error handling for unreachable streams

#### Task 3.2: HealthMonitor Class
**File:** `backend/chemtrail/sources/webcam_manager.py`
**Priority:** P1
**Estimated Hours:** 2

```python
class HealthMonitor:
    def add_stream(camera_id: str) -> None
    def get_health(camera_id: str) -> StreamHealth
    async def check_all() -> None
```

**Health Metrics:**
- Stream status (CONNECTING, STREAMING, ERROR, OFFLINE)
- Uptime tracking
- Segment production monitoring
- Auto-reconnect triggers

**Acceptance Criteria:**
- [ ] Health status tracked per stream
- [ ] Stale segment detection (>2 min)
- [ ] Error messages captured

#### Task 3.3: WebcamManager Main Class
**File:** `backend/chemtrail/sources/webcam_manager.py`
**Priority:** P0
**Estimated Hours:** 2

```python
class WebcamManager:
    async def add_stream(config: StreamConfig) -> None
    async def remove_stream(camera_id: str) -> None
    async def start_all() -> None
    async def stop_all() -> None
    async def run_forever() -> None
```

**Acceptance Criteria:**
- [ ] Multiple concurrent streams supported
- [ ] Configurable max concurrent limit
- [ ] Context manager support (async with)
- [ ] Integration test with mock streams

---

### Day 4: Weather Enrichment

#### Task 4.1: Open-Meteo API Client
**File:** `backend/chemtrail/sources/weather_enrichment.py`
**Priority:** P1
**Estimated Hours:** 3

```python
class WeatherEnrichmentService:
    ARCHIVE_API_URL = "https://api.open-meteo.com/v1/archive"
    
    async def get_historical_weather(
        lat, lon, start_time, end_time
    ) -> List[WeatherData]
    
    def get_weather_for_video(
        weather_data, video_start, video_end
    ) -> dict
```

**Weather Data Fields:**
- Temperature, humidity, cloud cover
- Visibility, wind speed/direction
- Weather condition code

**Acceptance Criteria:**
- [ ] API calls return valid data
- [ ] In-memory caching (24h TTL)
- [ ] Date range handling correct
- [ ] Weather codes mapped to descriptions

#### Task 4.2: Catalog Weather Update
**File:** `backend/chemtrail/sources/video_catalog.py`
**Priority:** P1
**Estimated Hours:** 1

```python
async def update_weather(self, video_id: str, weather_data: dict) -> None
```

**Acceptance Criteria:**
- [ ] Weather data persisted to catalog
- [ ] All fields updated atomically

---

### Day 5: Quality Scoring

#### Task 5.1: Quality Analysis Functions
**File:** `backend/chemtrail/sources/video_quality.py`
**Priority:** P1
**Estimated Hours:** 4

```python
def calculate_quality_score(video_path: str) -> dict:
    """
    Calculate video quality metrics.
    
    Returns:
        {
            'overall_score': 0.0-1.0,
            'resolution_score': 0.0-1.0,
            'stability_score': 0.0-1.0,
            'lighting_score': 0.0-1.0,
            'sharpness_score': 0.0-1.0,
            'metadata': {...}
        }
    """
```

**Quality Metrics:**
- **Resolution Score**: Normalized to 1080p = 1.0
- **Stability Score**: Optical flow variance (camera shake)
- **Lighting Score**: Histogram analysis (brightness distribution)
- **Sharpness Score**: Laplacian variance (focus quality)

**Acceptance Criteria:**
- [ ] All four metrics calculated
- [ ] Weighted average for overall score
- [ ] OpenCV integration working
- [ ] Performance acceptable (<5s per video)

#### Task 5.2: Catalog Quality Update
**File:** `backend/chemtrail/sources/video_catalog.py`
**Priority:** P1
**Estimated Hours:** 1

```python
async def update_quality(self, video_id: str, quality_scores: dict) -> None
```

---

### Day 6: Pipeline Orchestrator

#### Task 6.1: PipelineJob and PipelineConfig
**File:** `backend/chemtrail/sources/pipeline_orchestrator.py`
**Priority:** P0
**Estimated Hours:** 2

```python
@dataclass
class PipelineJob:
    job_id: str
    video_id: str
    current_stage: PipelineStage
    status: PipelineStatus
    # ... tracking fields

@dataclass
class PipelineConfig:
    max_concurrent_jobs: int = 5
    stage_timeout_seconds: Dict[PipelineStage, int]
    enable_weather_enrichment: bool = True
    enable_quality_scoring: bool = True
```

#### Task 6.2: PipelineOrchestrator Main Class
**File:** `backend/chemtrail/sources/pipeline_orchestrator.py`
**Priority:** P0
**Estimated Hours:** 4

```python
class PipelineOrchestrator:
    async def start() -> None
    async def stop() -> None
    async def submit_job(source_path, camera_id, priority) -> str
    async def get_job_status(job_id) -> PipelineJob
    async def wait_for_job(job_id, timeout) -> PipelineJob
    
    async def _worker(worker_id: int) -> None
    async def _process_job(job: PipelineJob) -> None
    async def _execute_stage(job, stage) -> None
```

**Pipeline Stages:**
1. ACQUISITION - Import video to catalog
2. SORTING - Categorize by metadata
3. WEATHER_ENRICHMENT - Fetch weather data
4. QUALITY_SCORING - Calculate quality metrics
5. CHUNKING - Segment video
6. DETECTION - Run CV pipeline
7. ARCHIVAL - Store in ChromaDB

**Acceptance Criteria:**
- [ ] Worker pool manages concurrent jobs
- [ ] Stage timeouts enforced
- [ ] Retry logic with max retries
- [ ] Job status tracking accurate
- [ ] Clean shutdown on stop()

#### Task 6.3: Stage Execution Handlers
**File:** `backend/chemtrail/sources/pipeline_orchestrator.py`
**Priority:** P0
**Estimated Hours:** 2

```python
async def _execute_stage(self, job: PipelineJob, stage: PipelineStage):
    if stage == PipelineStage.ACQUISITION:
        video_id = await self.video_catalog.import_video(...)
    elif stage == PipelineStage.WEATHER_ENRICHMENT:
        weather = await self.weather_service.get_weather_for_video(...)
    elif stage == PipelineStage.CHUNKING:
        chunks = chunk_video(job.source_path, ...)
    elif stage == PipelineStage.DETECTION:
        results = await self.detection_service.process_detection_batch(...)
    # ... etc
```

---

### Day 7: API Endpoints

#### Task 7.1: Video Sources REST API
**File:** `backend/chemtrail/api/video_sources.py`
**Priority:** P1
**Estimated Hours:** 4

**Endpoints:**

```python
# GET /api/video-sources
# List all registered video sources (webcams + file sources)
async def list_video_sources(
    source_type: Optional[str] = None,
    camera_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    ...

# POST /api/video-sources/webcam
# Register a new webcam stream
async def register_webcam(
    name: str,
    url: str,
    stream_type: str,  # rtsp, mjpeg, hls
    location: dict,  # lat, lon, alt
    orientation: dict,  # azimuth, elevation
):
    ...

# POST /api/video-sources/historical/scan
# Scan directory for historical videos
async def scan_historical_videos(
    directory: str,
    recursive: bool = True,
):
    ...

# POST /api/video-sources/historical/import
# Import a specific video file
async def import_video(
    file_path: str,
    camera_id: Optional[str] = None,
):
    ...

# GET /api/video-catalog
# Search video catalog with filters
async def search_catalog(
    camera_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_quality: Optional[float] = None,
    weather_condition: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    ...

# GET /api/video-catalog/{video_id}
# Get video details
async def get_video(video_id: str):
    ...

# POST /api/pipeline/jobs
# Submit a processing job
async def submit_pipeline_job(
    video_id: str,
    priority: int = 0,
):
    ...

# GET /api/pipeline/jobs/{job_id}
# Get job status
async def get_job_status(job_id: str):
    ...
```

**Acceptance Criteria:**
- [ ] All endpoints implemented
- [ ] Request/response validation with Pydantic
- [ ] Error handling with appropriate HTTP codes
- [ ] API documentation in OpenAPI/Swagger

---

### Day 8: Integration Testing

#### Task 8.1: Test Historical Ingestor
**File:** `tests/chemtrail/test_historical_ingestor.py`
**Priority:** P0
**Estimated Hours:** 2

```python
class TestVideoScanner:
    async def test_scan_directory_recursive(self, test_videos_dir):
        scanner = VideoScanner()
        result = await scanner.scan(test_videos_dir, recursive=True)
        assert result.count > 0
    
    async def test_scan_empty_directory(self, tmp_path):
        scanner = VideoScanner()
        result = await scanner.scan(str(tmp_path))
        assert result.count == 0

class TestMetadataExtractor:
    async def test_extract_metadata(self, test_video_path):
        extractor = MetadataExtractor()
        metadata = await extractor.extract(test_video_path)
        assert metadata.duration_seconds > 0
        assert metadata.width > 0
        assert metadata.height > 0
    
    async def test_calculate_checksum(self, test_video_path):
        extractor = MetadataExtractor()
        checksum = await extractor._calculate_checksum(test_video_path)
        assert len(checksum) == 64
```

#### Task 8.2: Test Webcam Manager
**File:** `tests/chemtrail/test_webcam_manager.py`
**Priority:** P0
**Estimated Hours:** 2

```python
class TestStreamConnection:
    @pytest.mark.asyncio
    async def test_start_rtsp_stream(self, mock_rtsp_server):
        config = StreamConfig(
            camera_id="test-cam",
            url=mock_rtsp_server.url,
            stream_type=StreamType.RTSP,
            location={...},
            orientation={...},
        )
        conn = StreamConnection(config)
        await conn.start()
        assert conn.status == StreamStatus.STREAMING
        await conn.stop()
        assert conn.status == StreamStatus.OFFLINE

class TestWebcamManager:
    @pytest.mark.asyncio
    async def test_add_and_start_stream(self):
        manager = WebcamManager()
        config = StreamConfig(...)
        await manager.add_stream(config)
        await manager.start_all()
        # Verify segment files created
```

#### Task 8.3: Test Pipeline Orchestrator
**File:** `tests/chemtrail/test_pipeline_orchestrator.py`
**Priority:** P0
**Estimated Hours:** 3

```python
class TestPipelineOrchestrator:
    @pytest.mark.asyncio
    async def test_submit_and_process_job(self, test_video_path):
        orchestrator = PipelineOrchestrator(config, ...)
        await orchestrator.start()
        
        job_id = await orchestrator.submit_job(test_video_path)
        await orchestrator.wait_for_job(job_id, timeout_seconds=300)
        
        job = await orchestrator.get_job_status(job_id)
        assert job.status == PipelineStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_job_retry_on_failure(self):
        # Test retry logic when a stage fails
        ...
    
    @pytest.mark.asyncio
    async def test_stage_timeout(self):
        # Test timeout handling
        ...
```

#### Task 8.4: End-to-End Integration Test
**File:** `tests/chemtrail/test_phase2_integration.py`
**Priority:** P0
**Estimated Hours:** 3

```python
class TestPhase2Integration:
    @pytest.mark.asyncio
    async def test_full_pipeline(
        self, 
        test_video_path,
        mock_webcam_stream,
        db_session,
    ):
        """Test complete flow from ingestion to archive."""
        
        # 1. Import historical video
        ingestor = HistoricalIngestor(db_path)
        video_id = await ingestor.import_video(test_video_path)
        
        # 2. Submit to pipeline
        orchestrator = PipelineOrchestrator(...)
        await orchestrator.start()
        job_id = await orchestrator.submit_job(video_id)
        
        # 3. Wait for completion
        await orchestrator.wait_for_job(job_id, timeout=600)
        
        # 4. Verify results
        job = await orchestrator.get_job_status(job_id)
        assert job.status == PipelineStatus.COMPLETED
        assert len(job.stage_results['detections']) >= 0
        
        # 5. Verify catalog updated
        catalog = VideoCatalog(db_url)
        video = await catalog.get_by_id(video_id)
        assert video.processing_status == ProcessingStatus.COMPLETED
```

---

### Day 9: Documentation & Polish

#### Task 9.1: Module Docstrings
**Priority:** P1
**Estimated Hours:** 2

- [ ] All public classes have docstrings
- [ ] All public methods have docstrings with Args/Returns
- [ ] Module-level docstrings explain purpose

#### Task 9.2: README Updates
**File:** `docs/chemtrail-tracker/README.md`
**Priority:** P1
**Estimated Hours:** 2

Add Phase 2 sections:
- Quick start for historical video import
- Webcam registration guide
- Pipeline job submission examples
- Video catalog search examples

#### Task 9.3: API Documentation
**File:** `docs/chemtrail-tracker/API_REFERENCE.md`
**Priority:** P1
**Estimated Hours:** 2

Add Phase 2 API sections:
- Video Sources API endpoints
- Pipeline Jobs API endpoints
- Request/response schemas

---

### Day 10: Testing & Bug Fixes

#### Task 10.1: Full Test Suite Run
**Priority:** P0
**Estimated Hours:** 2

```bash
# Run all Phase 2 tests
pytest tests/chemtrail/test_phase2_*.py -v

# Run with coverage
pytest tests/chemtrail/test_phase2_*.py --cov=chemtrail/sources --cov-report=html

# Run integration tests
pytest tests/chemtrail/test_phase2_integration.py -v
```

**Target Coverage:**
- Module coverage: >80%
- Integration test pass rate: 100%

#### Task 10.2: Bug Fixes
**Priority:** P0
**Estimated Hours:** 4

Address any issues found during testing:
- [ ] Fix failing tests
- [ ] Fix edge cases discovered during testing
- [ ] Performance optimizations if needed
- [ ] Memory leak checks for long-running processes

#### Task 10.3: Final Code Review
**Priority:** P1
**Estimated Hours:** 2

Review checklist:
- [ ] Type hints on all function signatures
- [ ] Error handling consistent across modules
- [ ] Logging appropriate (info/warning/error levels)
- [ ] No hardcoded paths or credentials
- [ ] Async/await usage correct

---

## Dependencies to Add

### requirements.txt Additions

```python
# Phase 2 dependencies - append to backend/requirements.txt

# YouTube download
yt-dlp>=2024.1.0

# Weather API client (optional, can use httpx directly)
# openmeteo-requests>=1.1.0

# Note: httpx already in requirements.txt
# Note: asyncpg already in requirements.txt
# Note: chromadb already in requirements.txt
```

### Installation Command

```bash
cd C:\Users\antmi\ground-station
pip install yt-dlp>=2024.1.0
```

---

## Test Strategy

### Test Categories

| Category | Count | Priority | Purpose |
|----------|-------|----------|---------|
| Unit Tests | 20+ | P0 | Test individual functions/classes |
| Integration Tests | 5+ | P0 | Test module interactions |
| End-to-End Tests | 2+ | P0 | Test full pipeline flow |
| Performance Tests | 2 | P1 | Test quality scoring performance |

### Test Fixtures

```python
# tests/chemtrail/conftest.py

import pytest
from pathlib import Path

@pytest.fixture
def test_videos_dir() -> str:
    """Directory with sample video files for testing."""
    return str(Path(__file__).parent / "test_data" / "videos")

@pytest.fixture
def test_video_path(test_videos_dir) -> str:
    """Path to a sample video file."""
    return str(Path(test_videos_dir) / "sample_1min.mp4")

@pytest.fixture
async def db_session():
    """Async database session for tests."""
    async with asyncpg.create_pool(TEST_DB_URL) as pool:
        async with pool.acquire() as conn:
            yield conn

@pytest.fixture
def mock_rtsp_server():
    """Mock RTSP server for webcam tests."""
    # Use v4l2loopback or similar for mock stream
    ...
```

### Mock External Services

```python
# tests/chemtrail/test_mocks.py

class MockWeatherAPI:
    """Mock Open-Meteo API for testing."""
    
    async def get(self, url, params):
        return {
            "hourly": {
                "time": ["2026-04-11T00:00", "2026-04-11T01:00"],
                "temperature_2m": [15.2, 14.8],
                "cloud_cover": [20, 25],
                # ... etc
            }
        }

class MockChromaDB:
    """Mock ChromaDB client for testing."""
    ...
```

---

## Priority Order Summary

### P0 (Critical - Must Have)

| Priority | Task | File | Hours |
|----------|------|------|-------|
| 1 | Database Schema Migration | db/migrations/phase2_video_catalog.sql | 2 |
| 2 | VideoCatalog Class | sources/video_catalog.py | 4 |
| 3 | HistoricalIngestor | sources/historical_ingestor.py | 8 |
| 4 | WebcamManager | sources/webcam_manager.py | 7 |
| 5 | PipelineOrchestrator | sources/pipeline_orchestrator.py | 8 |
| 6 | Integration Tests | tests/chemtrail/test_phase2_*.py | 10 |

### P1 (Important - Should Have)

| Priority | Task | File | Hours |
|----------|------|------|-------|
| 7 | WeatherEnrichment | sources/weather_enrichment.py | 4 |
| 8 | Quality Scoring | sources/video_quality.py | 5 |
| 9 | API Endpoints | api/video_sources.py | 4 |
| 10 | Documentation | docs/, README updates | 6 |

### P2 (Nice to Have)

| Priority | Task | File | Hours |
|----------|------|------|-------|
| 11 | YouTube Ingestor | sources/youtube_ingestor.py | 4 |
| 12 | Performance Tests | tests/chemtrail/test_performance.py | 3 |

---

## File Creation Summary

### New Files to Create

```
backend/chemtrail/
├── sources/
│   ├── __init__.py                        # Data classes, enums
│   ├── video_catalog.py                   # PostgreSQL catalog
│   ├── historical_ingestor.py             # File scanning, import
│   ├── webcam_manager.py                  # Stream management
│   ├── weather_enrichment.py              # Open-Meteo integration
│   ├── video_quality.py                   # Quality scoring
│   └── pipeline_orchestrator.py           # Workflow engine
├── api/
│   └── video_sources.py                   # REST API endpoints
└── db/
    └── migrations/
        └── phase2_video_catalog.sql       # Schema migration

tests/chemtrail/
├── test_historical_ingestor.py
├── test_webcam_manager.py
├── test_weather_enrichment.py
├── test_video_quality.py
├── test_pipeline_orchestrator.py
└── test_phase2_integration.py

docs/chemtrail-tracker/
├── PHASE2_ARCHITECTURE.md                 # Already created
├── PHASE2_PLAN.md                         # This document
└── PHASE2_TEST_REPORT.md                  # To be created
```

### Files to Modify

```
backend/
├── requirements.txt                       # Add yt-dlp
├── chemtrail/archive/detection_service.py # Minor: accept video_id
└── chemtrail/services/__init__.py         # Export new services

docs/chemtrail-tracker/
├── README.md                              # Add Phase 2 sections
└── API_REFERENCE.md                       # Add new endpoints
```

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ffmpeg compatibility issues | Medium | Medium | Test on all target platforms, use imageio-ffmpeg fallback |
| Open-Meteo API rate limits | Low | Low | Implement caching, respect rate limits |
| RTSP stream reliability | High | Medium | Robust error handling, auto-reconnect logic |
| Quality scoring performance | Medium | Low | Optimize OpenCV operations, async processing |
| ChromaDB schema conflicts | Low | Medium | Separate collection for video catalog |

### Mitigation Strategies

1. **Daily testing** - Run test suite at end of each day
2. **Incremental integration** - Test each module before moving to next
3. **Mock external services** - Avoid flaky tests due to API issues
4. **Documentation first** - Clear interfaces reduce integration issues

---

## Success Criteria

### Functional Criteria

- [ ] Historical video import working end-to-end
- [ ] Webcam stream capture producing segments
- [ ] Video catalog searchable by all filters
- [ ] Weather enrichment completing successfully
- [ ] Quality scoring returning valid scores
- [ ] Pipeline orchestrator processing jobs without manual intervention
- [ ] API endpoints returning correct responses

### Quality Criteria

- [ ] 136+ existing tests still passing (backward compatibility)
- [ ] 30+ new Phase 2 tests passing
- [ ] Code coverage >80% for new modules
- [ ] No critical bugs in issue tracker
- [ ] Documentation complete

### Performance Criteria

- [ ] Video import <10s for 1GB file (metadata extraction)
- [ ] Quality scoring <5s per minute of video
- [ ] Weather enrichment <2s per video
- [ ] Pipeline throughput: 5+ concurrent jobs
- [ ] API response time <500ms (P95)

---

## Post-Phase 2 Next Steps

### Phase 3 Planning (Enhancement)

After Phase 2 completion, consider:

1. **Motion Tracking** - Optical flow for contrail movement analysis
2. **Deep Learning** - Train custom contrail segmentation model
3. **Batch Processing** - Process large video libraries overnight
4. **Analytics Dashboard** - Detection statistics, trends over time

### Production Deployment

- Docker containerization
- Kubernetes orchestration for scale
- Monitoring and alerting setup
- CI/CD pipeline configuration

---

*Document prepared by Dr. Sarah Kim, Technical Product Strategist & Engineering Lead*
