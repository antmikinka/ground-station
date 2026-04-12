# Chemtrail Webcam Tracker - API Reference

**Version:** 1.5.0  
**Last Updated:** 2026-04-11  
**Status:** Production Ready

---

## Table of Contents

1. [Phase 1 Modules](#phase-1-modules)
   - [API Clients](#api-clients)
   - [Services](#services)
   - [Computer Vision](#computer-vision)
   - [Storage](#storage)
2. [Phase 1.5 Archive Modules](#phase-15-archive-modules)
   - [Chunker](#chunker)
   - [Vector Store](#vector-store)
   - [Embedder](#embedder)
   - [Searcher](#searcher)
   - [Telemetry Overlay](#telemetry-overlay)
   - [Detection Service](#detection-service)
3. [FR24 Integration](#fr24-integration)
   - [FR24 Client](#fr24-client)
   - [FR24 Flight Service](#fr24-flight-service)
4. [Database Models](#database-models)
5. [Error Classes](#error-classes)

---

## Phase 1 Modules

### API Clients

#### OpenSky Client

```python
from chemtrail.api.opensky_client import OpenSkyClient, OpenSkyStateVector
```

##### `OpenSkyClient`

HTTP client for the OpenSky Network API.

```python
class OpenSkyClient:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        rate_limit: int = 10,
    )
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | `None` | OpenSky member username |
| `password` | `str` | `None` | OpenSky member password |
| `rate_limit` | `int` | `10` | Requests per second limit |

##### Methods

```python
async def get_all_states(self) -> list[OpenSkyStateVector]
```
Get current state of all aircraft.

**Returns:** List of `OpenSkyStateVector` objects

```python
async def get_state_by_icao24(self, icao24: str) -> OpenSkyStateVector | None
```
Get state for specific aircraft.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `icao24` | `str` | ICAO24 hex code |

**Returns:** `OpenSkyStateVector` or `None`

```python
async def get_history(self, icao24: str, start: int, end: int) -> list[OpenSkyStateVector]
```
Get historical flight data.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `icao24` | `str` | ICAO24 hex code |
| `start` | `int` | Start timestamp (Unix epoch) |
| `end` | `int` | End timestamp (Unix epoch) |

**Returns:** List of historical state vectors

##### `OpenSkyStateVector`

```python
@dataclass
class OpenSkyStateVector:
    icao24: str
    callsign: str | None
    origin_country: str
    latitude: float | None
    longitude: float | None
    altitude: float | None
    velocity: float | None
    heading: float | None
    vertical_rate: float | None
    on_ground: bool
    timestamp: int
```

---

#### Webcam Client

```python
from chemtrail.api.webcam_client import WebcamClient, WebcamImage
```

##### `WebcamClient`

Client for ingesting images from webcam APIs and RTSP streams.

```python
class WebcamClient:
    def __init__(self, timeout: int = 30)
```

##### Methods

```python
async def fetch_image(self, url: str) -> WebcamImage | None
```
Fetch single image from URL.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `str` | Image or stream URL |

**Returns:** `WebcamImage` or `None`

```python
async def fetch_rtsp_frame(self, stream_url: str, timeout: int = 10) -> np.ndarray | None
```
Capture single frame from RTSP stream.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `stream_url` | `str` | RTSP URL |
| `timeout` | `int` | Capture timeout in seconds |

**Returns:** BGR frame as numpy array or `None`

```python
async def fetch_mjpeg_stream(self, stream_url: str, frames: int = 1) -> AsyncIterator[np.ndarray]
```
Capture frames from MJPEG stream.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `stream_url` | `str` | MJPEG stream URL |
| `frames` | `int` | Number of frames to capture |

**Returns:** Async iterator of BGR frames

##### `WebcamImage`

```python
@dataclass
class WebcamImage:
    data: np.ndarray
    timestamp: datetime
    source_url: str
    width: int
    height: int
```

---

### Services

#### Camera Service

```python
from chemtrail.services.camera_service import CameraService, Camera
```

##### `CameraService`

Manages camera registration and metadata.

```python
class CameraService:
    def __init__(self, session: AsyncSession)
```

##### Methods

```python
async def create_camera(
    self,
    name: str,
    url: str,
    camera_type: str,
    latitude: float,
    longitude: float,
    altitude: float,
    azimuth: float = 0.0,
    elevation: float = 0.0,
    fov_horizontal: float | None = None,
    fov_vertical: float | None = None,
) -> Camera
```
Register new camera.

**Returns:** Created `Camera` object

```python
async def get_camera(self, camera_id: UUID) -> Camera | None
```
Get camera by ID.

```python
async def list_cameras(
    self,
    status: str | None = None,
    limit: int = 50,
) -> list[Camera]
```
List cameras with optional status filter.

```python
async def update_camera(self, camera_id: UUID, **kwargs) -> Camera | None
```
Update camera metadata.

```python
async def delete_camera(self, camera_id: UUID) -> bool
```
Delete camera.

##### `Camera`

```python
@dataclass
class Camera:
    id: UUID
    name: str
    url: str
    type: str
    latitude: float
    longitude: float
    altitude: float
    azimuth: float
    elevation: float
    fov_horizontal: float | None
    fov_vertical: float | None
    status: str
    metadata: dict
```

---

#### Flight Service

```python
from chemtrail.services.flight_service import FlightService, Flight
```

##### `FlightService`

Caches and manages flight data from OpenSky.

```python
class FlightService:
    def __init__(
        self,
        opensky_client: OpenSkyClient,
        cache_ttl: int = 30,
    )
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `opensky_client` | `OpenSkyClient` | - | API client |
| `cache_ttl` | `int` | `30` | Cache TTL in seconds |

##### Methods

```python
async def get_flight(self, icao24: str) -> Flight | None
```
Get flight from cache or API.

**Returns:** `Flight` or `None`

```python
async def get_flights_near_position(
    self,
    lat: float,
    lon: float,
    radius_km: float = 10,
    limit: int = 10,
) -> list[Flight]
```
Get flights near geographic position.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat` | `float` | - | Latitude |
| `lon` | `float` | - | Longitude |
| `radius_km` | `float` | `10` | Search radius |
| `limit` | `int` | `10` | Max results |

**Returns:** List of `Flight` objects sorted by distance

```python
async def refresh_cache(self) -> int
```
Refresh flight cache from API.

**Returns:** Number of flights cached

##### `Flight`

```python
@dataclass
class Flight:
    icao24: str
    callsign: str | None
    registration: str | None
    aircraft_type: str | None
    origin: str | None
    destination: str | None
    position: dict
    last_position_update: datetime | None
```

---

## FR24 Integration

### FR24 Client

```python
from chemtrail.api import FR24Client, FR24FlightPosition, FR24FlightSummary, FR24FlightTrack
```

#### `FR24Client`

Synchronous wrapper for Flightradar24 SDK.

```python
class FR24Client:
    def __init__(self, api_token: str | None = None)
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_token` | `str` | `None` | FR24 API token (falls back to env var) |

**Context Manager:**
```python
with FR24Client(api_token="your-token") as client:
    positions = client.get_live_positions(limit=100)
```

##### Methods

```python
def get_live_positions(
    self,
    bounds: dict[str, float] | None = None,
    callsigns: list[str] | None = None,
    limit: int = 1000,
) -> list[FR24FlightPosition]
```
Get live flight positions from FR24.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bounds` | `dict` | `None` | Bounding box {north, south, west, east} |
| `callsigns` | `list` | `None` | Filter by callsigns |
| `limit` | `int` | `1000` | Max results |

**Returns:** List of `FR24FlightPosition` objects

```python
def get_historic_positions(
    self,
    timestamp: datetime | int,
    bounds: dict[str, float] | None = None,
    limit: int = 1000,
) -> list[FR24FlightPosition]
```
Get historical flight positions.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timestamp` | `datetime` | - | Target timestamp |
| `bounds` | `dict` | `None` | Bounding box |
| `limit` | `int` | `1000` | Max results |

**Returns:** List of `FR24FlightPosition` objects

```python
def get_flight_tracks(self, flight_id: str) -> FR24FlightTrack
```
Get flight track for specific flight.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `flight_id` | `str` | FR24 flight ID (hex format) |

**Returns:** `FR24FlightTrack` with tracks list

```python
def get_flight_summary(
    self,
    flight_ids: list[str] | None = None,
    limit: int = 100,
) -> list[FR24FlightSummary]
```
Get flight summaries.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `flight_ids` | `list` | `None` | Flight IDs to fetch |
| `limit` | `int` | `100` | Max results |

**Returns:** List of `FR24FlightSummary` objects

#### Data Classes

```python
@dataclass
class FR24FlightPosition:
    fr24_id: str
    hex: str
    callsign: str | None
    latitude: float
    longitude: float
    altitude: float
    ground_speed: float
    vertical_rate: int
    track: int
    squawk: str | None
    timestamp: datetime
    aircraft_type: str | None
    registration: str | None
    origin_icao: str | None
    destination_icao: str | None
    painted_as: str | None
    operating_as: str | None
    eta: datetime | None
```

```python
@dataclass
class FR24FlightSummary:
    fr24_id: str
    hex: str
    callsign: str | None
    flight_number: str | None
    aircraft_type: str | None
    registration: str | None
    origin_icao: str | None
    origin_iata: str | None
    destination_icao: str | None
    destination_iata: str | None
    datetime_takeoff: datetime | None
    runway_takeoff: str | None
    datetime_landed: datetime | None
    runway_landed: str | None
    flight_time: int | None
    actual_distance: float | None
    first_seen: datetime | None
    last_seen: datetime | None
    flight_ended: bool
    painted_as: str | None
    operating_as: str | None
```

```python
@dataclass
class FR24FlightTrack:
    fr24_id: str
    callsign: str | None
    tracks: list[dict]  # List of track points with lat, lon, alt, speed, etc.
```

---

### FR24 Flight Service

```python
from chemtrail.services import FR24FlightService, FR24Config
```

#### `FR24FlightService`

Service for FR24 data enrichment.

```python
class FR24FlightService:
    def __init__(
        self,
        api_token: str | None = None,
        config: FR24Config | None = None,
    )
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_token` | `str` | `None` | FR24 API token |
| `config` | `FR24Config` | `None` | Configuration object (falls back to from_env()) |

**Configuration from Environment:**
```python
from chemtrail.services import FR24Config

config = FR24Config.from_env()
# Reads: FR24_API_TOKEN, FR24_RATE_LIMIT, FR24_ENRICHMENT_LIMIT, etc.
```

##### Methods

```python
def validate_api_token(self) -> bool
```
Validate FR24 API token by making test request.

**Returns:** `True` if token is valid, `False` otherwise

```python
def health_check(self) -> dict
```
Perform FR24 service health check.

**Returns:** Health status dict:
```python
{
    "status": "healthy" | "degraded" | "unhealthy",
    "api_accessible": bool,
    "token_valid": bool,
    "last_check": datetime,
}
```

```python
def get_positions_near_time_and_location(
    self,
    timestamp: datetime,
    lat: float,
    lon: float,
    radius_km: float = 50.0,
    time_tolerance_seconds: int = 60,
    limit: int = 50,
) -> list[dict]
```
Get FR24 flight positions near time and location.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timestamp` | `datetime` | - | Target timestamp |
| `lat` | `float` | - | Latitude center |
| `lon` | `float` | - | Longitude center |
| `radius_km` | `float` | `50.0` | Search radius |
| `limit` | `int` | `50` | Max results |

**Returns:** List of normalized flight position dicts

```python
def get_flight_track(self, fr24_id: str) -> dict | None
```
Get flight track for specific flight.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `fr24_id` | `str` | FR24 flight ID |

**Returns:** Dict with `fr24_id` and `tracks` list, or `None`

```python
def get_flight_summary_by_hex(self, hex_code: str) -> dict | None
```
Get flight summary by ICAO hex code.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `hex_code` | `str` | ICAO 24-bit hex code |

**Returns:** Dict with flight summary data, or `None`

```python
def enrich_flight_cache_entry(
    self,
    icao24: str,
    existing_data: dict | None = None,
) -> dict
```
Enrich FlightCache entry with FR24-specific data.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `icao24` | `str` | ICAO 24-bit hex code |
| `existing_data` | `dict` | Existing OpenSky data (optional) |

**Returns:** Dict with merged data including:
- `fr24_id`, `painted_as`, `operating_as`
- `origin_icao`, `origin_iata`, `destination_icao`, `destination_iata`
- `flight_track` (list of track points)
- `datetime_takeoff`, `datetime_landed`, `flight_time`

**Example:**
```python
from chemtrail.services import FR24FlightService

service = FR24FlightService()

# Health check
health = service.health_check()
print(f"FR24 Status: {health['status']}")

# Enrich flight
enriched = service.enrich_flight_cache_entry("4b1a02")
print(enriched)  # Contains fr24_id, painted_as, flight_track, etc.
```

---

#### Geocalc Service

```python
from chemtrail.services.geocalc_service import pixel_to_az_el, estimate_position_single
```

##### `pixel_to_az_el()`

Convert pixel coordinates to azimuth/elevation.

```python
def pixel_to_az_el(
    x: float,
    y: float,
    width: int,
    height: int,
    cam_azimuth: float,
    cam_elevation: float,
    fov_h: float,
    fov_v: float,
) -> tuple[float, float]
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | `float` | Pixel X coordinate |
| `y` | `float` | Pixel Y coordinate |
| `width` | `int` | Image width in pixels |
| `height` | `int` | Image height in pixels |
| `cam_azimuth` | `float` | Camera heading (0-360) |
| `cam_elevation` | `float` | Camera tilt (-90 to 90) |
| `fov_h` | `float` | Horizontal FOV in degrees |
| `fov_v` | `float` | Vertical FOV in degrees |

**Returns:** `(azimuth, elevation)` in degrees

**Example:**
```python
az, el = pixel_to_az_el(
    x=960, y=540,
    width=1920, height=1080,
    cam_azimuth=180, cam_elevation=45,
    fov_h=60, fov_v=40
)
# Returns: (180.0, 45.0) - center of image
```

##### `estimate_position_single()`

Estimate object position from single camera observation.

```python
def estimate_position_single(
    cam_lat: float,
    cam_lon: float,
    cam_alt: float,
    az_obj: float,
    el_obj: float,
    assumed_alt: float = 10000,
) -> tuple[float, float]
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cam_lat` | `float` | - | Camera latitude |
| `cam_lon` | `float` | - | Camera longitude |
| `cam_alt` | `float` | - | Camera altitude (meters) |
| `az_obj` | `float` | - | Object azimuth |
| `el_obj` | `float` | - | Object elevation |
| `assumed_alt` | `float` | `10000` | Assumed object altitude |

**Returns:** `(latitude, longitude)` in degrees

**Example:**
```python
lat, lon = estimate_position_single(
    cam_lat=47.6062, cam_lon=-122.3321, cam_alt=100,
    az_obj=180.0, el_obj=45.0,
    assumed_alt=10000
)
```

---

#### Detection Handler

```python
from chemtrail.handlers.detection_handler import DetectionHandler
```

##### `DetectionHandler`

Processes and stores detection events.

```python
class DetectionHandler:
    def __init__(
        self,
        session: AsyncSession,
        flight_service: FlightService,
        geocalc_service: GeoCalculator,
    )
```

##### Methods

```python
async def process_detection(
    self,
    camera_id: UUID,
    detection: ContrailDetection,
    frame: np.ndarray,
    timestamp: datetime,
) -> ChemtrailDetection
```
Process single detection event.

**Returns:** Stored `ChemtrailDetection` object

```python
async def correlate_with_flight(
    self,
    detection: ChemtrailDetection,
    radius_km: float = 10,
) -> Flight | None
```
Find matching flight for detection.

**Returns:** Matching `Flight` or `None`

---

### Computer Vision

#### Contrail Detector

```python
from chemtrail.cv.contrail_detector import ContrailDetector, ContrailDetection
```

##### `ContrailDetector`

Hough transform-based contrail detection.

```python
class ContrailDetector:
    def __init__(
        self,
        min_line_length: int = 100,
        max_line_gap: int = 10,
        threshold: int = 80,
        min_confidence: float = 0.5,
    )
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_line_length` | `int` | `100` | Minimum line length in pixels |
| `max_line_gap` | `int` | `10` | Maximum gap between line segments |
| `threshold` | `int` | `80` | Hough accumulator threshold |
| `min_confidence` | `float` | `0.5` | Minimum confidence score |

##### Methods

```python
def detect(self, frame: np.ndarray) -> list[ContrailDetection]
```
Detect contrails in frame.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `frame` | `np.ndarray` | BGR frame |

**Returns:** List of `ContrailDetection` objects

```python
def detect_with_preprocessing(
    self,
    frame: np.ndarray,
    apply_clahe: bool = True,
    denoise: bool = True,
) -> list[ContrailDetection]
```
Detect with preprocessing pipeline.

##### `ContrailDetection`

```python
@dataclass
class ContrailDetection:
    detection_type: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    confidence: float
    angle: float
    length_px: float
    width_px: float | None
    persistence: int | None
    
    def to_dict(self) -> dict
    def to_vector(self) -> list[float]
```

---

#### CV Utils

```python
from chemtrail.cv.cv_utils import preprocess_frame, extract_contrail_region
```

##### `preprocess_frame()`

Preprocess frame for CV detection.

```python
def preprocess_frame(
    frame: np.ndarray,
    target_resolution: int = 480,
    apply_clahe: bool = True,
    clahe_clip_limit: float = 2.0,
    denoise: bool = True,
    denoise_strength: int = 10,
) -> np.ndarray
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `frame` | `np.ndarray` | - | Input BGR frame |
| `target_resolution` | `int` | `480` | Target height in pixels |
| `apply_clahe` | `bool` | `True` | Apply CLAHE enhancement |
| `clahe_clip_limit` | `float` | `2.0` | CLAHE clip limit |
| `denoise` | `bool` | `True` | Apply denoising |
| `denoise_strength` | `int` | `10` | Denoising strength |

**Returns:** Preprocessed grayscale frame

##### `extract_contrail_region()`

Extract contrail crop from detection.

```python
def extract_contrail_region(
    frame: np.ndarray,
    detection: ContrailDetection,
    padding: int = 20,
) -> np.ndarray
```

**Returns:** Cropped contrail region

---

### Storage

#### Image Storage

```python
from chemtrail.storage.image_storage import save_detection_image, get_image_path
```

##### `save_detection_image()`

Save detection image to storage.

```python
def save_detection_image(
    image: np.ndarray,
    detection_id: UUID,
    base_dir: str = "./storage/images",
) -> str
```

**Returns:** Path to saved image

##### `get_image_path()`

Get image path by detection ID.

```python
def get_image_path(
    detection_id: UUID,
    base_dir: str = "./storage/images",
) -> str
```

---

## Phase 1.5 Archive Modules

### Chunker

```python
from chemtrail.archive.chunker import (
    chunk_video,
    is_still_frame_chunk,
    is_still_frame_sequence,
    preprocess_chunk,
    scan_directory,
)
```

#### `chunk_video()`

Split video into overlapping chunks.

```python
def chunk_video(
    video_path: str,
    chunk_duration: int = 30,
    overlap: int = 5,
    continuous_mode: bool = False,
    output_dir: str | None = None,
) -> list[dict] | Iterator[dict]
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `video_path` | `str` | - | Video file path or RTSP URL |
| `chunk_duration` | `int` | `30` | Chunk duration in seconds |
| `overlap` | `int` | `5` | Overlap between chunks |
| `continuous_mode` | `bool` | `False` | Continuous stream mode |
| `output_dir` | `str` | `None` | Output directory |

**Returns:** List of chunk dicts or iterator (continuous mode)

**Chunk Dict:**
```python
{
    "chunk_path": str,       # Path to chunk file
    "source_file": str,      # Original source
    "start_time": float,     # Start time in seconds
    "end_time": float,       # End time in seconds
}
```

**Example:**
```python
# Batch mode
chunks = chunk_video("feed.mp4", chunk_duration=30, overlap=5)
for chunk in chunks:
    print(f"Chunk: {chunk['chunk_path']}")

# Continuous mode
for chunk in chunk_video("rtsp://stream", continuous_mode=True):
    process_chunk(chunk)
```

#### `is_still_frame_chunk()`

Check if chunk contains static scene.

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
| `threshold` | `float` | `0.98` | JPEG size ratio threshold |
| `verbose` | `bool` | `False` | Print debug info |

**Returns:** `True` if chunk appears static

#### `is_still_frame_sequence()`

Check if frame sequence is static.

```python
def is_still_frame_sequence(
    frames: list[np.ndarray],
    threshold: float = 0.98,
) -> bool
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `frames` | `list[np.ndarray]` | List of BGR frames |

**Returns:** `True` if frames appear static

#### `preprocess_chunk()`

Downscale video chunk.

```python
def preprocess_chunk(
    chunk_path: str,
    target_resolution: int = 480,
    target_fps: int = 5,
) -> str
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk_path` | `str` | - | Input chunk path |
| `target_resolution` | `int` | `480` | Target height |
| `target_fps` | `int` | `5` | Target frame rate |

**Returns:** Path to preprocessed file

#### `scan_directory()`

Find video files in directory.

```python
def scan_directory(directory_path: str) -> list[str]
```

**Returns:** Sorted list of video file paths

---

### Vector Store

```python
from chemtrail.archive.vector_store import (
    ChemtrailVectorStore,
    detect_backend,
    detect_index,
    BackendMismatchError,
)
```

#### `ChemtrailVectorStore`

ChromaDB-backed vector store.

```python
class ChemtrailVectorStore:
    def __init__(
        self,
        db_path: str | Path | None = None,
        backend: str = "gemini",
        model: str | None = None,
    )
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db_path` | `str` | `None` | Database path |
| `backend` | `str` | `"gemini"` | Embedding backend |
| `model` | `str` | `None` | Local model name |

##### Methods

```python
def add_detection(
    self,
    chunk_id: str,
    embedding: list[float],
    metadata: dict,
) -> None
```
Store single detection.

**Metadata Schema:**
```python
{
    # Required
    "source_file": str,
    "start_time": float,
    "end_time": float,
    "camera_id": str,
    "confidence": float,
    
    # Auto-added
    "indexed_at": str,  # ISO timestamp
    
    # Optional
    "camera_name": str,
    "camera_lat": float,
    "camera_lon": float,
    "camera_alt": float,
    "detection_type": str,  # "contrail" or "aircraft"
    "pixel_x": float,
    "pixel_y": float,
    "azimuth": float,
    "elevation": float,
    "contrail_vector": dict,
    "icao24": str,
    "callsign": str,
    "aircraft_type": str,
    "estimated_lat": float,
    "estimated_lon": float,
    "estimated_alt": float,
    "correlation_score": float,
    "position_method": str,
    "overlay_applied": bool,
    "clip_path": str,
}
```

```python
def add_detections(self, chunks: list[dict]) -> None
```
Batch store detections.

```python
def search(
    self,
    query_embedding: list[float],
    n_results: int = 5,
) -> list[dict]
```
Search by vector similarity.

**Returns:** List of results with `source_file`, `start_time`, `score`, `distance`

```python
def search_by_flight(
    self,
    icao24: str,
    n_results: int = 10,
) -> list[dict]
```
Search by flight ICAO24.

```python
def search_by_camera(
    self,
    camera_id: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    n_results: int = 10,
) -> list[dict]
```
Search by camera with optional date range.

```python
def search_by_location(
    self,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    n_results: int = 10,
) -> list[dict]
```
Search by geographic bounding box.

```python
def search_by_date_range(
    self,
    date_from: datetime,
    date_to: datetime,
    n_results: int = 50,
) -> list[dict]
```
Search by indexed date range.

```python
def is_indexed(self, source_file: str) -> bool
```
Check if file is already indexed.

```python
def remove_file(self, source_file: str) -> int
```
Remove all chunks for file.

**Returns:** Number of chunks removed

```python
def get_stats(self) -> dict
```
Get store statistics.

**Returns:**
```python
{
    "total_chunks": int,
    "unique_source_files": int,
    "source_files": list[str],
}
```

```python
def get_backend(self) -> str
```
Get embedding backend.

```python
def get_model(self) -> str | None
```
Get embedding model name.

```python
def check_backend(self, backend: str) -> None
```
Validate backend matches index.

**Raises:** `BackendMismatchError` if mismatch

#### `detect_backend()`

Detect backend from existing database.

```python
def detect_backend(db_path: str | Path | None = None) -> str | None
```

**Returns:** `"gemini"`, `"local"`, or `None`

#### `detect_index()`

Detect backend and model.

```python
def detect_index(db_path: str | Path | None = None) -> tuple[str | None, str | None]
```

**Returns:** `(backend, model)` tuple

---

### Embedder

```python
from chemtrail.archive.embedder import (
    get_embedder,
    reset_embedder,
    embed_video_chunk,
    embed_query,
    GeminiAPIKeyError,
    GeminiQuotaError,
)
```

#### `get_embedder()`

Factory function for embedder instances.

```python
def get_embedder(
    backend: str = "gemini",
    **kwargs,
) -> BaseEmbedder
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `backend` | `str` | `"gemini"` or `"local"` |
| `model` | `str` | For local: `"qwen8b"`, `"qwen2b"` |
| `dimensions` | `int` | Output dimensions |
| `quantize` | `bool` | Quantize local model |

**Returns:** `BaseEmbedder` instance

#### `reset_embedder()`

Reset cached embedder.

```python
def reset_embedder() -> None
```

#### `embed_video_chunk()`

Embed video chunk.

```python
def embed_video_chunk(
    chunk_path: str,
    verbose: bool = False,
) -> list[float]
```

**Returns:** 768-dimensional embedding vector

#### `embed_query()`

Embed text query.

```python
def embed_query(
    query_text: str,
    verbose: bool = False,
) -> list[float]
```

**Returns:** 768-dimensional embedding vector

#### `GeminiAPIKeyError`

Raised when `GEMINI_API_KEY` is missing.

#### `GeminiQuotaError`

Raised when API quota exceeded.

---

### BaseEmbedder

```python
from chemtrail.archive.base_embedder import BaseEmbedder
```

Abstract base class for embedding backends.

```python
class BaseEmbedder(ABC):
    @abstractmethod
    def embed_video_chunk(
        self,
        chunk_path: str,
        verbose: bool = False,
    ) -> list[float]
        ...
    
    @abstractmethod
    def embed_query(
        self,
        query_text: str,
        verbose: bool = False,
    ) -> list[float]
        ...
    
    @abstractmethod
    def dimensions(self) -> int
        ...
```

---

### GeminiEmbedder

```python
from chemtrail.archive.gemini_embedder import GeminiEmbedder
```

Gemini API embedding backend.

```python
class GeminiEmbedder(BaseEmbedder):
    def __init__(self)
```

**Requires:** `GEMINI_API_KEY` environment variable

##### Methods

```python
def embed_video_chunk(
    self,
    chunk_path: str,
    verbose: bool = False,
) -> list[float]
```
Embed video using Gemini Video API.

```python
def embed_query(
    self,
    query_text: str,
    verbose: bool = False,
) -> list[float]
```
Embed query text.

```python
def dimensions(self) -> int
```
**Returns:** 768

---

### Searcher

```python
from chemtrail.archive.searcher import search_detections, search_footage
```

#### `search_detections()`

Search with natural language and filters.

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

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Natural language query |
| `vector_store` | `ChemtrailVectorStore` | Store to search |
| `n_results` | `int` | Max results |
| `icao24` | `str` | Filter by flight |
| `camera_id` | `str` | Filter by camera |
| `date_from` | `datetime` | Start date |
| `date_to` | `datetime` | End date |
| `detection_type` | `str` | `"contrail"` or `"aircraft"` |
| `verbose` | `bool` | Debug output |

**Returns:** List of result dicts:
```python
{
    "chunk_id": str,
    "source_file": str,
    "start_time": float,
    "end_time": float,
    "score": float,
    "camera_id": str,
    "camera_name": str,
    "icao24": str | None,
    "callsign": str | None,
    "detection_type": str,
    "confidence": float,
    "estimated_lat": float | None,
    "estimated_lon": float | None,
}
```

#### `search_footage()`

Legacy function name (alias for `search_detections`).

```python
def search_footage(
    query: str,
    store: ChemtrailVectorStore,
    n_results: int = 5,
    verbose: bool = False,
) -> list[dict]
```

---

### Telemetry Overlay

```python
from chemtrail.archive.telemetry_overlay import (
    apply_flight_overlay,
    build_hud_overlay,
    get_flight_metadata,
    reverse_geocode,
)
```

#### `apply_flight_overlay()`

Burn flight HUD onto clip.

```python
def apply_flight_overlay(
    input_path: str,
    output_path: str,
    flight_metadata: dict,
) -> str
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `input_path` | `str` | Input video path |
| `output_path` | `str` | Output video path |
| `flight_metadata` | `dict` | Flight data dict |

**Returns:** `output_path` on success, `input_path` on failure

**Flight Metadata Schema:**
```python
{
    "callsign": str,
    "altitude": float | None,
    "velocity": float | None,
    "heading": float | None,
    "latitude": float | None,
    "longitude": float | None,
    "timestamp": datetime,
}
```

#### `get_flight_metadata()`

Get flight data for overlay.

```python
def get_flight_metadata(
    icao24: str,
    flight_service,
    timestamp: datetime,
) -> dict | None
```

**Returns:** Flight metadata dict or `None`

#### `build_hud_overlay()`

Build complete HUD metadata.

```python
def build_hud_overlay(
    flight_data: dict,
    camera_name: str,
    timestamp: datetime,
    contrail_vector: dict | None = None,
) -> dict
```

**Returns:** Complete metadata dict for overlay

#### `reverse_geocode()`

Reverse geocode coordinates.

```python
def reverse_geocode(
    lat: float,
    lon: float,
) -> dict | None
```

**Returns:** `{"city": str, "road": str}` or `None`

---

### Detection Service

```python
from chemtrail.archive.detection_service import DetectionService, rtsp_to_segment
```

#### `DetectionService`

Orchestrates detection pipeline.

```python
class DetectionService:
    def __init__(
        self,
        session: AsyncSession,
        vector_store: ChemtrailVectorStore,
        flight_service: FlightService,
        contrail_detector: ContrailDetector,
        embedder: BaseEmbedder | None = None,
    )
```

##### Methods

```python
async def process_detection_batch(
    self,
    chunks: list[dict],
    camera_id: str,
    camera_metadata: dict,
    skip_still_frames: bool = True,
    apply_overlay: bool = False,
) -> list[dict]
```
Process batch of chunks.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `chunks` | `list[dict]` | Chunk dicts from chunker |
| `camera_id` | `str` | Camera UUID |
| `camera_metadata` | `dict` | Camera geolocation |
| `skip_still_frames` | `bool` | Skip static chunks |
| `apply_overlay` | `bool` | Burn HUD overlay |

**Returns:** List of processed detection records

**Camera Metadata Schema:**
```python
{
    "name": str,
    "latitude": float,
    "longitude": float,
    "altitude": float,
    "azimuth": float,
    "elevation": float,
    "fov_horizontal": float,
    "fov_vertical": float,
}
```

```python
async def _process_single_detection(
    self,
    detection: ContrailDetection,
    chunk: dict,
    camera_id: str,
    camera_metadata: dict,
    apply_overlay: bool,
) -> dict
```
Process single detection.

**Returns:** Detection record with chunk_id, detection, metadata

#### `rtsp_to_segment()`

Capture RTSP stream segment.

```python
def rtsp_to_segment(
    stream_url: str,
    duration_seconds: int = 10,
    output_dir: str | None = None,
) -> dict | None
```

**Returns:** Chunk dict or `None` on failure

---

## Database Models

```python
from db.models import (
    ChemtrailCameras,
    ChemtrailDetections,
    FlightCache,
    DetectionFrames,
    TriangulationResults,
    DetectionType,
    ProcessingStatus,
)
```

### `ChemtrailCameras`

Camera registration model.

```python
class ChemtrailCameras(Base):
    id: UUID
    name: str
    url: str
    type: CameraType
    latitude: float
    longitude: float
    altitude: float
    azimuth: float
    elevation: float
    fov_horizontal: float | None
    fov_vertical: float | None
    image_width: int | None
    image_height: int | None
    lens_distortion: dict | None
    status: str
    metadata: dict
```

### `ChemtrailDetections`

Detection records.

```python
class ChemtrailDetections(Base):
    id: UUID
    camera_id: UUID
    icao24: str | None
    detection_type: DetectionType
    timestamp: datetime
    image_path: str
    pixel_x: float
    pixel_y: float
    azimuth: float
    elevation: float
    estimated_latitude: float | None
    estimated_longitude: float | None
    estimated_altitude: float | None
    confidence: float
    correlation_score: float | None
    contrail_vector: dict | None
```

### `FlightCache`

Cached flight data.

```python
class FlightCache(Base):
    icao24: str
    callsign: str | None
    registration: str | None
    aircraft_type: str | None
    position: dict | None
    last_position_update: datetime | None
    position_history: list | None
```

---

## Error Classes

| Error | Base | Description |
|-------|------|-------------|
| `GeminiAPIKeyError` | `RuntimeError` | GEMINI_API_KEY not set |
| `GeminiQuotaError` | `RuntimeError` | API rate limit exceeded |
| `BackendMismatchError` | `RuntimeError` | Backend doesn't match index |

---

## Quick Reference

### Common Imports

```python
# Core archive functionality
from chemtrail.archive import (
    chunk_video,
    ChemtrailVectorStore,
    search_detections,
    apply_flight_overlay,
    embed_query,
)

# Services
from chemtrail.services import (
    CameraService,
    FlightService,
    DetectionService,
)

# Computer Vision
from chemtrail.cv import (
    ContrailDetector,
    ContrailDetection,
    preprocess_frame,
)

# Utilities
from chemtrail.archive.vector_store import detect_backend
from chemtrail.services.geocalc_service import pixel_to_az_el
```

### Type Aliases

```python
from typing import List, Dict, Optional, Tuple

ChunkDict = Dict[str, float | str]
DetectionRecord = Dict[str, any]
Embedding = List[float]
GeoCoords = Tuple[float, float]  # (lat, lon)
```

---

## Support

For additional documentation:
- [Architecture Overview](./ARCHITECTURE.md)
- [Integration Guide](./INTEGRATION_GUIDE.md)
- [Implementation Brief](./IMPLEMENTATION_BRIEF.md)
