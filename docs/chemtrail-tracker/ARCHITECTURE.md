# Chemtrail Webcam Tracker - Technical Architecture

**Version:** 1.0.0  
**Author:** Dr. Sarah Kim, Technical Product Strategist & Engineering Lead  
**Date:** 2026-04-11  
**Status:** Draft - For Review

---

## Executive Summary

The Chemtrail Webcam Tracker is a ground-station extension that correlates public webcam sky imagery with flight tracking data to detect and log aircraft contrails. The system leverages computer vision for automated detection, multiple API integrations for data correlation, and geolocalization mathematics for position triangulation.

### Business Objectives

1. **Automated Detection**: Identify contrails and aircraft in sky imagery using computer vision
2. **Flight Correlation**: Match detected objects with actual flight data from ADS-B sources
3. **Geolocalization**: Calculate aircraft positions using camera metadata and detection angles
4. **Historical Logging**: Maintain a searchable database of detections with metadata
5. **Public Visualization**: Provide web interface for browsing detections and statistics

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CHEMTRAIL WEBCAM TRACKER                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────┐    ┌─────────────────────────────────────┐                │
│  │   WEBCAM SOURCES │    │  FLIGHT DATA APIS (Dual-Source)    │                │
│  │                  │    │                                     │                │
│  │  • OpenSky Web   │    │  • OpenSky Network (Primary)        │                │
│  │  • EarthCam      │    │  • Flightradar24 (Enrichment)       │                │
│  │  • Webcam Taxi   │    │  • ADS-B Exchange (Redundancy)      │                │
│  │  • RTSP/MJPEG    │    │                                     │                │
│  │  • Local Cams    │    │  FR24 adds:                         │                │
│  │                  │    │  - Airline branding (painted_as)    │                │
│  │                  │    │  - Flight tracks (historical paths) │                │
│  │                  │    │  - Airport codes (ICAO/IATA)        │                │
│  │                  │    │  - Historical data (since 2016)     │                │
│  └────────┬─────────┘    └────────────────┬────────────────────┘                │
│           │                               │                                      │
│           └───────────────┬───────────────┘                                      │
│                           │                                                       │
│                           ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐            │
│  │                    API GATEWAY LAYER                             │            │
│  │         (FastAPI Endpoints + Rate Limiting + Caching)            │            │
│  └─────────────────────────────────────────────────────────────────┘            │
│                           │                                                       │
│                           ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐            │
│  │                   PROCESSING PIPELINE                            │            │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │            │
│  │  │ Image       │  │ Dual-Source │  │ Correlation │             │            │
│  │  │ Ingestion   │  │ Flight Data │  │ Engine      │             │            │
│  │  │             │  │ (OpenSky+   │  │ (ICAO hex   │             │            │
│  │  │             │  │  FR24)      │  │  merge)     │             │            │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │            │
│  │         │                │                │                      │            │
│  │         ▼                ▼                ▼                      │            │
│  │  ┌─────────────────────────────────────────────────┐           │            │
│  │  │        COMPUTER VISION MODULE                    │           │            │
│  │  │  • Contrail Detection (Hough/Edge)              │           │            │
│  │  │  • Aircraft Detection (YOLO/CV)                 │           │            │
│  │  │  • Motion Tracking (Optical Flow)               │           │            │
│  │  └─────────────────────────────────────────────────┘           │            │
│  │         │                                                       │            │
│  │         ▼                                                       │            │
│  │  ┌─────────────────────────────────────────────────┐           │            │
│  │  │        GEOLOCALIZATION ENGINE                    │           │            │
│  │  │  • Camera Position + Azimuth/EL Calculation     │           │            │
│  │  │  • Triangulation (Multi-Camera)                 │           │            │
│  │  │  • Flight Path Correlation                      │           │            │
│  │  └─────────────────────────────────────────────────┘           │            │
│  └─────────────────────────────────────────────────────────────────┘            │
│                                  │                                               │
│                                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────┐            │
│  │                    DATA LAYER                                    │            │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │            │
│  │  │ PostgreSQL  │  │ TimescaleDB │  │ Redis       │             │            │
│  │  │ (Detections)│  │ (Time Series│  │ (Cache/     │             │            │
│  │  │ +FlightCache│  │  Metadata)  │  │  Queue)     │             │            │
│  │  │ +13 FR24    │  │             │  │             │             │            │
│  │  │ fields      │  │             │  │             │             │            │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │            │
│  └─────────────────────────────────────────────────────────────────┘            │
│                                  │                                               │
│                                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────┐            │
│  │                    PRESENTATION LAYER                            │            │
│  │         (React Frontend + Map Visualization + Dashboard)         │            │
│  └─────────────────────────────────────────────────────────────────┘            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   WEBCAM    │────▶│   IMAGE     │────▶│   CONTRAIL  │────▶│   DETECTION │
│   API/RTSP  │     │   ACQUIS    │     │   DETECTION │     │   RECORD    │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
┌─────────────┐     ┌─────────────────────────────────┐           │
│  OPENSKY    │────▶│   DUAL-SOURCE FLIGHT DATA       │───────────┤
│   API       │     │   (OpenSky + FR24 Enrichment)   │           │
└─────────────┘     └─────────────────────────────────┘           │
                                                                  │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│   FR24 SDK  │────▶│  FR24Flight │────▶│  Flight     │───────────┤
│  (sync)     │     │  Service    │     │  Cache +13  │           │
└─────────────┘     └─────────────┘     │  fields     │           │
                                        └─────────────┘           │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│   CAMERA    │────▶│  AZIMUTH/   │────▶│  GEO-       │───────────┤
│  METADATA   │     │  EL CALC    │     │  LOCALIZE   │           │
└─────────────┘     └─────────────┘     └─────────────┘           │
                                                                  │
                    ┌─────────────────────────────────────────────▼──────┐
                    │              DETECTION EVENT                        │
                    │  {timestamp, camera_id, flight_id, position,        │
                    │   confidence, image_data, contrail_vector,          │
                    │   fr24_id, painted_as, flight_track,                │
                    │   data_sources: ["opensky", "fr24"]}                │
                    └─────────────────────────────────────────────────────┘
```

---

## 2. API Research & Comparison Matrix

### 2.1 Public Webcam APIs

| API/Service | Type | Cost | Authentication | Image Format | Metadata | Pros | Cons |
|-------------|------|------|----------------|--------------|----------|------|------|
| **OpenSky Webcams** | Web API | Free | None required | JPEG | Lat/Lon/Alt, Heading | No API key needed, open data | Limited camera count, static images only |
| **EarthCam API** | REST/WebSocket | Paid ($$$) | API Key | JPEG/MJPEG/HLS | Pan/Tilt/Zoom, Location | High quality, PTZ control | Expensive, rate limited |
| **Webcam Taxi** | Direct Stream | Free/Donation | None | MJPEG/HLS | Basic location | Many sky/webcams, direct streams | Unreliable uptime, no official API |
| **Windy.com Webcams** | REST API | Freemium | API Key | JPEG | Lat/Lon, Alt | Good metadata, weather overlay | Rate limits on free tier |
| **SkyWeather Network** | RTSP/MJPEG | Free | None | MJPEG | Azimuth/Elevation | Designed for sky watching | Limited geographic coverage |
| **Raspberry Pi Astro Cam** | Self-hosted RTSP | Free | Configurable | RTSP/MJPEG | Full metadata | Complete control, customizable | Requires hardware setup |
| **NASA Earth Observatory** | REST API | Free | API Key | GeoTIFF/JPEG | Geospatial | Scientific grade, calibrated | Not real-time, satellite only |
| **IP Camera Direct** | RTSP/ONVIF | Varies | Configurable | RTSP/MJPEG/H.264 | Varies | Universal standard | Configuration complexity |

**Recommendation:** Start with **OpenSky Webcams** (free, no auth) + **Direct RTSP/MJPEG** for self-hosted cameras. Add **Windy.com** for expanded coverage.

### 2.2 Flight Tracking APIs

| API/Service | Cost | Rate Limit | Data Fields | Historical | Pros | Cons |
|-------------|------|------------|-------------|------------|------|------|
| **OpenSky Network** | Free (basic) | 10 sec (anon), 1 sec (member) | ICAO24, Callsign, Origin/Country, Lat/Lon/Baro Alt, Velocity, Heading, Vertical Rate | 24h free, full history (member) | Open source, no key for basic, extensive coverage | Rate limits, some military filtered |
| **Flightradar24 (FR24)** | Paid ($$$) | 60-1000 req/min (tier-based) | ICAO24 (hex), Callsign, Registration, Aircraft Type, Origin/Dest (ICAO/IATA), ETA, Squawk, Vertical Rate, Flight Track | Full history (since 2016-05-11) | Richest metadata, airline branding, flight tracks, historical depth | Paid API, requires token |
| **ADS-B Exchange** | Free (API) | Reasonable use | ICAO24, Reg, Type, Lat/Lon, Alt, Speed, Heading, Squawk, MLAT | Limited free | No filtering (military visible), good accuracy | API can be unstable, no official rate limit docs |
| **AviationStack** | Freemium ($0-$199/mo) | 100-1000 req/hr | Flight status, airport info, aircraft data, real-time position | Paid tiers | Well documented, enterprise options | Free tier very limited, expensive for production |
| **FlightAware** | Freemium | API key required | Flight status, position, airport data | Paid | Excellent accuracy, enterprise support | Cost prohibitive for hobby projects |

**Recommendation:** Primary: **OpenSky Network** (free tier sufficient for development). Secondary: **Flightradar24** for enrichment (airline branding, flight tracks, historical data). Tertiary: **ADS-B Exchange** for unfiltered redundancy.

### 2.3 Dual-Source Flight Data Architecture

The system implements a dual-source flight data architecture combining OpenSky (primary, real-time) with Flightradar24 (secondary, enrichment):

```
┌─────────────────────────────────────────────────────────────────┐
│                    DUAL-SOURCE FLIGHT DATA                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐      ┌─────────────────────────────────┐  │
│  │  OpenSkyClient   │─────►│     FlightService (Async)       │  │
│  │  (Async Native)  │      │  - Primary: OpenSky (async)     │  │
│  │                  │      │  - Enrichment: FR24 (executor)  │  │
│  └──────────────────┘      │  - Correlation: ICAO hex merge  │  │
│                            └─────────────────────────────────┘  │
│  ┌──────────────────┐                    │                       │
│  │  FR24Client      │                    │                       │
│  │  (Sync Wrapper)  │────────────────────┘                       │
│  │  asyncio.to_thread()                                         │
│  └──────────────────┘                                           │
│                                                                  │
│  Data Priority Matrix:                                           │
│  ┌─────────────────────┬──────────────┬──────────────┐         │
│  │ Field               │ Primary      │ Enrichment   │         │
│  ├─────────────────────┼──────────────┼──────────────┤         │
│  │ Position (lat/lon)  │ OpenSky      │ FR24 backup  │         │
│  │ Callsign            │ OpenSky      │ FR24 backup  │         │
│  │ Aircraft Type       │ OpenSky      │ FR24 preferred│        │
│  │ Registration        │ OpenSky      │ FR24 preferred│        │
│  │ Origin/Destination  │ Country      │ ICAO/IATA    │         │
│  │ Airline Branding    │ N/A          │ FR24 only    │         │
│  │ Flight Track        │ N/A          │ FR24 only    │         │
│  │ Historical Data     │ 24h-90 days  │ Since 2016   │         │
│  └─────────────────────┴──────────────┴──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- **Redundancy:** FR24 supplements OpenSky data, improving coverage reliability
- **Rich Metadata:** Access to airline branding (`painted_as`, `operating_as`), detailed airport codes
- **Historical Analysis:** Query flight positions dating back to May 2016
- **Flight Track Correlation:** Complete positional tracks for verified path matching
- **Graceful Degradation:** System continues in OpenSky-only mode when FR24 unavailable

**Implementation:**
- `chemtrail/api/fr24_client.py` - Synchronous FR24 SDK wrapper
- `chemtrail/services/fr24_flight_service.py` - FR24 service with config, health checks, enrichment
- `chemtrail/services/flight_service.py` - Dual-source integration with automatic merging
- `db/models.py` - FlightCache extended with 13 FR24-specific fields

**Configuration:**
```bash
# Required for FR24 enrichment
FR24_API_TOKEN=your-fr24-api-token-here

# Optional configuration
FR24_RATE_LIMIT=60           # Requests per minute
FR24_ENRICHMENT_LIMIT=50     # Max flights to enrich per batch
FR24_CACHE_TTL=300           # Cache TTL in seconds
```

### 2.3 API Integration Priority

```
PHASE 1 (MVP):
├── OpenSky Network (flights) - No auth, immediate start
├── Direct RTSP/MJPEG (webcams) - Self-hosted control
└── Manual camera metadata entry

PHASE 2 (Expansion):
├── Windy.com Webcams API - Expanded coverage
├── OpenSky member account - Higher rate limits
└── ADS-B Exchange - Redundancy

PHASE 3 (Enterprise):
├── EarthCam API - Premium camera access
├── AviationStack - Commercial flight data
└── Custom camera network deployment
```

---

## 3. Computer Vision Approaches

### 3.1 Contrail Detection Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTRAIL DETECTION PIPELINE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   INPUT     │────▶│ PREPROCESS  │────▶│   EDGE      │       │
│  │   FRAME     │     │  (CLAHE,    │     │  DETECTION  │       │
│  │  (1920x1080)│     │   Denoise)  │     │  (Canny)    │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│                                                 │                │
│                                                 ▼                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │  OUTPUT:    │◀────│ CONTRAIL    │◀────│   LINE      │       │
│  │  Vectors +  │     │ VALIDATION  │     │  DETECTION  │       │
│  │  Confidence │     │  (ML Filter)│     │ (Probabilistic│     │
│  └─────────────┘     └─────────────┘     │   Hough)     │       │
│                                          └─────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Detection Algorithms Comparison

| Technique | Library | Accuracy | Speed | Use Case | Notes |
|-----------|---------|----------|-------|----------|-------|
| **Probabilistic Hough Transform** | OpenCV | Medium-High | Fast | Straight contrail detection | Sensitive to noise, needs preprocessing |
| **Canny Edge + Line Fitting** | OpenCV/scikit-image | Medium | Fast | General edge detection | Good first-pass filter |
| **YOLOv8 (Custom Trained)** | Ultralytics | High | Medium | Aircraft silhouette detection | Requires training dataset |
| **Optical Flow (Farneback)** | OpenCV | Medium | Slow | Motion-based detection | Good for video sequences |
| **Background Subtraction** | OpenCV | Medium | Fast | Stationary camera motion detect | Requires stable background |
| **DeepLabV3+ (Semantic Seg)** | PyTorch/TensorFlow | Very High | Slow | Sky/contrail segmentation | Needs GPU, training data |
| **Template Matching** | OpenCV | Low-Medium | Fast | Known aircraft shapes | Limited real-world applicability |

### 3.3 Recommended CV Stack

```python
# Core Computer Vision Dependencies
opencv-python>=4.8.0          # Core CV operations
opencv-contrib-python>=4.8.0  # Extended algorithms (xfeatures2d, etc.)
scikit-image>=0.21.0          # Alternative CV algorithms
numpy>=1.24.0                 # Numerical operations
scipy>=1.11.0                 # Scientific computing

# Deep Learning (Optional, GPU-accelerated)
ultralytics>=8.0.0            # YOLOv8 for aircraft detection
torch>=2.0.0                  # PyTorch backend
torchvision>=0.15.0           # Computer vision models

# Image Processing
pillow>=10.0.0                # Image loading/manipulation
imageio>=2.31.0               # Video/image I/O

# Sky/Cloud Segmentation (Research Phase)
segmentation-models-pytorch   # Pretrained segmentation models
```

### 3.4 Contrail Detection Algorithm (Initial Implementation)

```python
def detect_contrails(frame: np.ndarray) -> list[ContrailDetection]:
    """
    Detect contrails in sky image using multi-stage pipeline.
    
    Returns list of detections with:
    - Start/end coordinates (image space)
    - Confidence score
    - Contrail vector (angle, length)
    """
    # Stage 1: Preprocessing
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
    
    # Stage 2: Edge Detection
    edges = cv2.Canny(denoised, threshold1=50, threshold2=150)
    
    # Stage 3: Line Detection (Probabilistic Hough)
    lines = cv2.HoughLinesP(
        edges, 
        rho=1, 
        theta=np.pi/180, 
        threshold=80,
        minLineLength=100,
        maxLineGap=10
    )
    
    # Stage 4: Contrail Validation
    contrails = []
    for line in lines:
        if is_likely_contrail(line, frame):
            contrails.append(ContrailDetection.from_line(line))
    
    return contrails
```

---

## 4. Geolocalization Mathematics

### 4.1 Problem Statement

Given:
- Camera position: `(lat_c, lon_c, alt_c)` in WGS84
- Camera orientation: `(azimuth, elevation, fov_h, fov_v)`
- Detection in image: `(x, y)` pixel coordinates
- Image dimensions: `(width, height)`

Calculate:
- Object azimuth relative to camera: `az_obj`
- Object elevation relative to camera: `el_obj`
- Object 3D position: `(lat_obj, lon_obj, alt_obj)`

### 4.2 Azimuth/Elevation from Pixel Coordinates

```python
def pixel_to_az_el(
    x: float, y: float,
    width: int, height: int,
    cam_azimuth: float, cam_elevation: float,
    fov_h: float, fov_v: float
) -> tuple[float, float]:
    """
    Convert pixel coordinates to absolute azimuth/elevation.
    
    Args:
        x, y: Pixel coordinates (center = 0,0)
        width, height: Image dimensions
        cam_azimuth: Camera heading (0-360 degrees, N=0, E=90)
        cam_elevation: Camera tilt (-90 to 90, 0=horizon)
        fov_h, fov_v: Horizontal/vertical field of view (degrees)
    
    Returns:
        (azimuth, elevation) in degrees
    """
    # Normalize pixel to [-1, 1] range (center = 0)
    x_norm = (x - width / 2) / (width / 2)
    y_norm = (height / 2 - y) / (height / 2)  # Flip Y axis
    
    # Convert to angular offset from camera center
    az_offset = x_norm * (fov_h / 2)
    el_offset = y_norm * (fov_v / 2)
    
    # Calculate absolute azimuth/elevation
    az_obj = (cam_azimuth + az_offset) % 360
    el_obj = cam_elevation + el_offset
    
    return az_obj, el_obj
```

### 4.3 Single-Camera Position Estimation (with assumed altitude)

```python
def estimate_position_single(
    cam_lat: float, cam_lon: float, cam_alt: float,
    az_obj: float, el_obj: float,
    assumed_alt: float
) -> tuple[float, float]:
    """
    Estimate object lat/lon assuming known altitude.
    Uses simple spherical projection (sufficient for visual range < 50km).
    
    Args:
        cam_lat, cam_lon, cam_alt: Camera position (alt in meters AMSL)
        az_obj: Object azimuth (degrees)
        el_obj: Object elevation (degrees)
        assumed_alt: Assumed object altitude (meters AMSL)
    
    Returns:
        (lat_obj, lon_obj) in degrees
    """
    from math import radians, degrees, sin, cos, atan, sqrt
    from pyproj import Geod
    
    # Altitude difference
    delta_alt = assumed_alt - cam_alt
    
    # Horizontal distance (assuming flat earth for short range)
    el_rad = radians(el_obj)
    if el_rad <= 0:
        el_rad = radians(0.1)  # Prevent division by zero
    horizontal_dist = delta_alt / tan(el_rad)
    
    # Calculate displacement
    az_rad = radians(az_obj)
    delta_north = horizontal_dist * cos(az_rad)
    delta_east = horizontal_dist * sin(az_rad)
    
    # Convert to lat/lon offset (approximate)
    lat_obj = cam_lat + degrees(delta_north / 111320)
    lon_obj = cam_lon + degrees(delta_east / (111320 * cos(radians(cam_lat))))
    
    return lat_obj, lon_obj
```

### 4.4 Multi-Camera Triangulation

```python
def triangulate_position(
    cam1_pos: tuple, cam1_az: float, cam1_el: float,
    cam2_pos: tuple, cam2_az: float, cam2_el: float,
) -> tuple[float, float, float, float]:
    """
    Triangulate 3D position from two camera observations.
    
    Uses least-squares intersection of two bearing vectors.
    
    Args:
        cam1_pos, cam2_pos: (lat, lon, alt) for each camera
        cam1_az, cam1_el: Azimuth/elevation from camera 1
        cam2_az, cam2_el: Azimuth/elevation from camera 2
    
    Returns:
        (lat, lon, alt, confidence) - confidence based on intersection quality
    """
    from scipy.optimize import least_squares
    
    def residual(point_3d):
        """Calculate angular residual from both cameras."""
        lat, lon, alt = point_3d
        
        # Calculate expected az/el from each camera to point
        exp_az1, exp_el1 = calculate_az_el(cam1_pos, (lat, lon, alt))
        exp_az2, exp_el2 = calculate_az_el(cam2_pos, (lat, lon, alt))
        
        # Residual = difference from measured
        return [
            exp_az1 - cam1_az,
            exp_el1 - cam1_el,
            exp_az2 - cam2_az,
            exp_el2 - cam2_el
        ]
    
    # Initial guess (intersection of two rays at average altitude)
    initial_guess = [
        (cam1_pos[0] + cam2_pos[0]) / 2,
        (cam1_pos[1] + cam2_pos[1]) / 2,
        10000  # Typical commercial altitude
    ]
    
    result = least_squares(residual, initial_guess)
    confidence = 1.0 / (1.0 + sum(result.cost))
    
    return (*result.x, confidence)
```

### 4.5 Required Camera Metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `latitude` | float | Yes | WGS84 latitude (decimal degrees) |
| `longitude` | float | Yes | WGS84 longitude (decimal degrees) |
| `altitude` | float | Yes | Meters above sea level (AMSL) |
| `azimuth` | float | Yes | Camera heading (0-360, N=0, E=90) |
| `elevation` | float | Yes | Camera tilt (-90 to 90, 0=horizon) |
| `fov_horizontal` | float | Recommended | Horizontal field of view (degrees) |
| `fov_vertical` | float | Recommended | Vertical field of view (degrees) |
| `image_width` | int | Yes | Image resolution width (pixels) |
| `image_height` | int | Yes | Image resolution height (pixels) |
| `lens_distortion` | JSON | Optional | Radial/tangential distortion coefficients |

---

## 5. Database Schema

### 5.1 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATABASE SCHEMA                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐         ┌─────────────────┐               │
│  │     CAMERAS     │         │   FLIGHT_CACHE  │               │
│  ├─────────────────┤         ├─────────────────┤               │
│  │ id (UUID) PK    │         │ icao24 (str) PK │               │
│  │ name (str)      │         │ callsign (str)  │               │
│  │ url (str)       │         │ registration (str)              │
│  │ type (enum)     │         │ aircraft_type (str)             │
│  │ latitude (float)│         │ origin (str)    │               │
│  │ longitude (float)│        │ destination (str)               │
│  │ altitude (float)│         │ last_seen (ts)  │               │
│  │ azimuth (float) │         │ position (point)│               │
│  │ elevation (float)│        │ altitude (float)│               │
│  │ fov_h (float)   │         │ heading (float) │               │
│  │ fov_v (float)   │         │ velocity (float)│               │
│  │ image_width (int)│        │ vertical_rate (f)│              │
│  │ image_height (int)│       │ timestamps (arr)│               │
│  │ status (enum)   │         │ raw_messages (j)│               │
│  │ metadata (json) │         │ created_at (ts) │               │
│  │ created_at (ts) │         │ updated_at (ts) │               │
│  │ updated_at (ts) │         └────────┬────────┘               │
│  └────────┬────────┘                  │                         │
│           │                          │                          │
│           │ 1:N                      │ N:M                      │
│           │                          │                          │
│           ▼                          ▼                          │
│  ┌─────────────────────────────────────────────────┐           │
│  │              DETECTIONS                          │           │
│  ├─────────────────────────────────────────────────┤           │
│  │ id (UUID) PK                                     │           │
│  │ camera_id (UUID) FK ─────────────────────────────┤           │
│  │ icao24 (str) FK ─────────────────────────────────┤           │
│  │ timestamp (ts)                                   │           │
│  │ detection_type (enum) [contrail, aircraft]       │           │
│  │ image_path (str)                                 │           │
│  │ image_center_lat (float)                         │           │
│  │ image_center_lon (float)                         │           │
│  │ pixel_x (int)                                    │           │
│  │ pixel_y (int)                                    │           │
│  │ azimuth (float)                                  │           │
│  │ elevation (float)                                │           │
│  │ estimated_lat (float)                            │           │
│  │ estimated_lon (float)                            │           │
│  │ estimated_alt (float)                            │           │
│  │ confidence (float)                               │           │
│  │ contrail_vector (json) {angle, length, width}    │           │
│  │ processing_metadata (json)                       │           │
│  │ correlation_score (float)                        │           │
│  │ created_at (ts)                                  │           │
│  └─────────────────────────────────────────────────┘           │
│           │                                                      │
│           │ 1:N                                                  │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────┐           │
│  │         DETECTION_FRAMES (Time Series)          │           │
│  ├─────────────────────────────────────────────────┤           │
│  │ id (BIGINT) PK (Timescale hypertable)           │           │
│  │ detection_id (UUID) FK                          │           │
│  │ frame_timestamp (ts)                            │           │
│  │ frame_sequence (int)                            │           │
│  │ pixel_x (float)                                 │           │
│  │ pixel_y (float)                                 │           │
│  │ azimuth (float)                                 │           │
│  │ elevation (float)                               │           │
│  │ velocity_x (float)                              │           │
│  │ velocity_y (float)                              │           │
│  │ blob_data (bytea)                               │           │
│  └─────────────────────────────────────────────────┘           │
│                                                                  │
│  ┌─────────────────┐         ┌─────────────────┐               │
│  │   TRIANGULATIONS│         │  PROCESSING_LOG │               │
│  ├─────────────────┤         ├─────────────────┤               │
│  │ id (UUID) PK    │         │ id (UUID) PK    │               │
│  │ detection_1 (FK)│         │ timestamp (ts)  │               │
│  │ detection_2 (FK)│         │ camera_id (FK)  │               │
│  │ triangulated_at │         │ job_type (enum) │               │
│  │ lat (float)     │         │ status (enum)   │               │
│  │ lon (float)     │         │ duration_ms (int)              │
│  │ alt (float)     │         │ error (text)    │               │
│  │ confidence (f)  │         │ metadata (json) │               │
│  │ method (str)    │         └─────────────────┘               │
│  └─────────────────┘                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 SQLAlchemy Model Definitions

```python
# New models for chemtrail-tracker extension
# Add to: backend/db/models.py

class DetectionType(str, PyEnum):
    CONTRAIL = "contrail"
    AIRCRAFT = "aircraft"
    UNKNOWN = "unknown"


class ProcessingStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChemtrailCameras(Base):
    """Extended camera model with geolocalization metadata."""
    __tablename__ = "chemtrail_cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)  # RTSP/MJPEG URL or API endpoint
    type = Column(Enum(CameraType), nullable=False)
    
    # Geolocation (required for triangulation)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    altitude = Column(Float, nullable=False)  # meters AMSL
    
    # Orientation (required for az/el calculation)
    azimuth = Column(Float, nullable=False, default=0.0)  # 0-360
    elevation = Column(Float, nullable=False, default=0.0)  # -90 to 90
    
    # Optical characteristics
    fov_horizontal = Column(Float, nullable=True)  # degrees
    fov_vertical = Column(Float, nullable=True)  # degrees
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    lens_distortion = Column(JSON, nullable=True)  # {k1, k2, p1, p2}
    
    # Operational
    status = Column(Enum("active", "inactive", "error"), default="inactive")
    last_image_at = Column(AwareDateTime, nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional camera-specific data
    
    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(AwareDateTime, nullable=True, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class ChemtrailDetections(Base):
    """Core detection records linking cameras, flights, and observations."""
    __tablename__ = "chemtrail_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    camera_id = Column(UUID(as_uuid=True), ForeignKey("chemtrail_cameras.id"), nullable=False, index=True)
    icao24 = Column(String, ForeignKey("flight_cache.icao24"), nullable=True, index=True)  # May be null for uncorrelated
    
    # Detection type
    detection_type = Column(Enum(DetectionType), nullable=False, index=True)
    
    # Timing
    timestamp = Column(AwareDateTime, nullable=False, index=True)
    processing_latency_ms = Column(Integer, nullable=True)
    
    # Image reference
    image_path = Column(String, nullable=False)  # Path to stored image/frame
    image_hash = Column(String, nullable=True, index=True)  # For deduplication
    
    # Detection location (image space)
    pixel_x = Column(Float, nullable=False)
    pixel_y = Column(Float, nullable=False)
    bounding_box = Column(JSON, nullable=True)  # [x1, y1, x2, y2] for aircraft
    
    # Calculated az/el from camera
    azimuth = Column(Float, nullable=False)
    elevation = Column(Float, nullable=False)
    
    # Estimated 3D position (WGS84)
    estimated_latitude = Column(Float, nullable=True, index=True)
    estimated_longitude = Column(Float, nullable=True, index=True)
    estimated_altitude = Column(Float, nullable=True)  # meters AMSL
    position_method = Column(String, nullable=True)  # "single_camera", "triangulation", "flight_correlation"
    
    # Detection quality
    confidence = Column(Float, nullable=False)  # 0.0-1.0
    correlation_score = Column(Float, nullable=True)  # 0.0-1.0 for flight match
    
    # Contrail-specific data
    contrail_vector = Column(JSON, nullable=True)  # {angle, length_px, width_px, persistence}
    
    # Processing metadata
    processing_metadata = Column(JSON, nullable=True)  # Algorithm outputs, intermediate results
    
    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(AwareDateTime, nullable=True, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    __table_args__ = (
        # Compound index for time-range queries by camera
        Index("idx_detections_camera_time", "camera_id", "timestamp"),
    )


class FlightCache(Base):
    """
    Cached flight data from OpenSky/FR24 APIs.

    Stores recent flight positions and history for correlation with detections.
    Supports dual-source data from both OpenSky and Flightradar24.
    
    FR24 Integration: 13 additional fields for enriched flight data.
    """
    __tablename__ = "flight_cache"

    icao24 = Column(String, primary_key=True, nullable=False)
    callsign = Column(String, nullable=True, index=True)
    registration = Column(String, nullable=True)
    aircraft_type = Column(String, nullable=True)
    origin = Column(String, nullable=True)  # OpenSky origin_country
    destination = Column(String, nullable=True)
    
    # FR24-specific fields (enrichment)
    fr24_id = Column(String, nullable=True, index=True)  # FR24 flight ID
    squawk = Column(String, nullable=True)  # Transponder code
    vertical_rate = Column(Integer, nullable=True)  # Feet per minute
    painted_as = Column(String, nullable=True)  # Airline ICAO (branding)
    operating_as = Column(String, nullable=True)  # Airline ICAO (operator)
    eta = Column(AwareDateTime, nullable=True)  # Estimated time of arrival
    
    # FR24 airport codes (more detailed than origin/destination)
    origin_icao = Column(String, nullable=True)
    origin_iata = Column(String, nullable=True)
    destination_icao = Column(String, nullable=True)
    destination_iata = Column(String, nullable=True)

    # Current position (updated from API)
    position = Column(JSON, nullable=True)  # {lat, lon, alt, heading, velocity}
    last_position_update = Column(AwareDateTime, nullable=True, index=True)

    # Position history (for correlation with detections)
    position_history = Column(JSON, nullable=True)  # Array of {timestamp, lat, lon, alt}

    # Flight track data from FR24
    flight_track = Column(JSON, nullable=True)  # Array of track points from FR24

    # Raw API responses (for debugging/reprocessing)
    raw_message = Column(JSON, nullable=True)  # OpenSky raw response
    fr24_raw_message = Column(JSON, nullable=True)  # FR24 raw response

    # Data source tracking
    data_sources = Column(JSON, nullable=True)  # ["opensky", "fr24"] - which sources contributed

    # Timestamps
    first_seen = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )


class DetectionFrames(Base):
    """Time-series tracking data for moving detections (contrail evolution)."""
    __tablename__ = "detection_frames"

    # Using TimescaleDB-style hypertable design
    id = Column(Integer, primary_key=True, autoincrement=True)
    detection_id = Column(UUID(as_uuid=True), ForeignKey("chemtrail_detections.id"), nullable=False, index=True)
    frame_timestamp = Column(AwareDateTime, nullable=False, index=True)
    frame_sequence = Column(Integer, nullable=False)
    
    # Position in frame
    pixel_x = Column(Float, nullable=False)
    pixel_y = Column(Float, nullable=False)
    
    # Motion data
    velocity_x = Column(Float, nullable=True)
    velocity_y = Column(Float, nullable=True)
    
    # Blob/contour data (compressed)
    blob_data = Column(LargeBinary, nullable=True)
    
    # Timestamp
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))

    __table_args__ = (
        # Optimized for time-range queries
        Index("idx_frames_detection_time", "detection_id", "frame_timestamp"),
    )


class TriangulationResults(Base):
    """Results from multi-camera triangulation."""
    __tablename__ = "triangulation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Linked detections
    detection_1_id = Column(UUID(as_uuid=True), ForeignKey("chemtrail_detections.id"), nullable=False)
    detection_2_id = Column(UUID(as_uuid=True), ForeignKey("chemtrail_detections.id"), nullable=False)
    
    # Camera baseline
    baseline_km = Column(Float, nullable=True)  # Distance between cameras
    
    # Result
    triangulated_latitude = Column(Float, nullable=False)
    triangulated_longitude = Column(Float, nullable=False)
    triangulated_altitude = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    intersection_angle = Column(Float, nullable=True)  # Quality metric
    
    # Method
    method = Column(String, nullable=False)  # "least_squares", "geometric", etc.
    
    # Timestamp
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
```

### 5.3 Database Migration Strategy

```python
# Migration file: alembic/versions/xxxx_add_chemtrail_tracker_schema.py

"""Add chemtrail tracker schema

Revision ID: xxxx
Revises: previous_revision
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'xxxx'
down_revision = 'previous_revision'


def upgrade():
    # Create chemtrail_cameras table
    op.create_table('chemtrail_cameras',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('url', sa.String, nullable=True),
        sa.Column('type', sa.Enum('webrtc', 'hls', 'mjpeg', name='cameratype'), nullable=False),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('altitude', sa.Float, nullable=False),
        sa.Column('azimuth', sa.Float, nullable=False, default=0.0),
        sa.Column('elevation', sa.Float, nullable=False, default=0.0),
        sa.Column('fov_horizontal', sa.Float, nullable=True),
        sa.Column('fov_vertical', sa.Float, nullable=True),
        sa.Column('image_width', sa.Integer, nullable=True),
        sa.Column('image_height', sa.Integer, nullable=True),
        sa.Column('lens_distortion', sa.JSON, nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'error', name='camerastatus'), default='inactive'),
        sa.Column('last_image_at', sa.DateTime(timezone=False), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), default=datetime.now(timezone.utc)),
        sa.Column('updated_at', sa.DateTime(timezone=False), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc)),
    )
    op.create_index('idx_cameras_location', 'chemtrail_cameras', ['latitude', 'longitude'])
    
    # Create flight_cache table
    op.create_table('flight_cache',
        sa.Column('icao24', sa.String, primary_key=True),
        sa.Column('callsign', sa.String, nullable=True),
        sa.Column('registration', sa.String, nullable=True),
        sa.Column('aircraft_type', sa.String, nullable=True),
        sa.Column('origin', sa.String, nullable=True),
        sa.Column('destination', sa.String, nullable=True),
        sa.Column('position', sa.JSON, nullable=True),
        sa.Column('last_position_update', sa.DateTime(timezone=False), nullable=True),
        sa.Column('position_history', sa.JSON, nullable=True),
        sa.Column('raw_message', sa.JSON, nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=False), default=datetime.now(timezone.utc)),
        sa.Column('updated_at', sa.DateTime(timezone=False), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc)),
    )
    op.create_index('idx_flight_cache_callsign', 'flight_cache', ['callsign'])
    op.create_index('idx_flight_cache_last_pos', 'flight_cache', ['last_position_update'])
    
    # Create chemtrail_detections table
    op.create_table('chemtrail_detections',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('camera_id', sa.UUID(as_uuid=True), sa.ForeignKey('chemtrail_cameras.id'), nullable=False),
        sa.Column('icao24', sa.String, sa.ForeignKey('flight_cache.icao24'), nullable=True),
        sa.Column('detection_type', sa.Enum('contrail', 'aircraft', 'unknown', name='detectiontype'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=False), nullable=False),
        sa.Column('processing_latency_ms', sa.Integer, nullable=True),
        sa.Column('image_path', sa.String, nullable=False),
        sa.Column('image_hash', sa.String, nullable=True),
        sa.Column('pixel_x', sa.Float, nullable=False),
        sa.Column('pixel_y', sa.Float, nullable=False),
        sa.Column('bounding_box', sa.JSON, nullable=True),
        sa.Column('azimuth', sa.Float, nullable=False),
        sa.Column('elevation', sa.Float, nullable=False),
        sa.Column('estimated_latitude', sa.Float, nullable=True),
        sa.Column('estimated_longitude', sa.Float, nullable=True),
        sa.Column('estimated_altitude', sa.Float, nullable=True),
        sa.Column('position_method', sa.String, nullable=True),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('correlation_score', sa.Float, nullable=True),
        sa.Column('contrail_vector', sa.JSON, nullable=True),
        sa.Column('processing_metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), default=datetime.now(timezone.utc)),
        sa.Column('updated_at', sa.DateTime(timezone=False), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc)),
    )
    op.create_index('idx_detections_camera', 'chemtrail_detections', ['camera_id'])
    op.create_index('idx_detections_icao24', 'chemtrail_detections', ['icao24'])
    op.create_index('idx_detections_time', 'chemtrail_detections', ['timestamp'])
    op.create_index('idx_detections_camera_time', 'chemtrail_detections', ['camera_id', 'timestamp'])
    op.create_index('idx_detections_location', 'chemtrail_detections', ['estimated_latitude', 'estimated_longitude'])
    
    # Create detection_frames table (time-series)
    op.create_table('detection_frames',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('detection_id', sa.UUID(as_uuid=True), sa.ForeignKey('chemtrail_detections.id'), nullable=False),
        sa.Column('frame_timestamp', sa.DateTime(timezone=False), nullable=False),
        sa.Column('frame_sequence', sa.Integer, nullable=False),
        sa.Column('pixel_x', sa.Float, nullable=False),
        sa.Column('pixel_y', sa.Float, nullable=False),
        sa.Column('velocity_x', sa.Float, nullable=True),
        sa.Column('velocity_y', sa.Float, nullable=True),
        sa.Column('blob_data', sa.LargeBinary, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), default=datetime.now(timezone.utc)),
    )
    op.create_index('idx_frames_detection', 'detection_frames', ['detection_id'])
    op.create_index('idx_frames_detection_time', 'detection_frames', ['detection_id', 'frame_timestamp'])
    
    # Create triangulation_results table
    op.create_table('triangulation_results',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('detection_1_id', sa.UUID(as_uuid=True), sa.ForeignKey('chemtrail_detections.id'), nullable=False),
        sa.Column('detection_2_id', sa.UUID(as_uuid=True), sa.ForeignKey('chemtrail_detections.id'), nullable=False),
        sa.Column('baseline_km', sa.Float, nullable=True),
        sa.Column('triangulated_latitude', sa.Float, nullable=False),
        sa.Column('triangulated_longitude', sa.Float, nullable=False),
        sa.Column('triangulated_altitude', sa.Float, nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('intersection_angle', sa.Float, nullable=True),
        sa.Column('method', sa.String, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=False), default=datetime.now(timezone.utc)),
    )


def downgrade():
    op.drop_table('triangulation_results')
    op.drop_table('detection_frames')
    op.drop_table('chemtrail_detections')
    op.drop_table('flight_cache')
    op.drop_table('chemtrail_cameras')
```

---

## 6. Implementation Phases

### 6.1 Phase 1: Foundation (Weeks 1-3)

**Priority: CRITICAL**

#### Goals
- Establish basic infrastructure
- Implement OpenSky API integration
- Create camera management system
- Build detection data models

#### Tasks

| ID | Task | Priority | Dependencies | Est. Hours |
|----|------|----------|--------------|------------|
| 1.1 | Database schema migration | P0 | None | 4 |
| 1.2 | OpenSky Network API client | P0 | None | 8 |
| 1.3 | Camera CRUD endpoints | P0 | 1.1 | 6 |
| 1.4 | Camera metadata calibration UI | P1 | 1.3 | 8 |
| 1.5 | Basic image ingestion (MJPEG/RTSP) | P0 | 1.3 | 12 |
| 1.6 | Contrail detection MVP (Hough) | P0 | 1.5 | 16 |
| 1.7 | Detection logging pipeline | P0 | 1.2, 1.6 | 8 |
| 1.8 | Flight correlation (manual) | P1 | 1.2, 1.7 | 6 |

**Deliverables:**
- Working camera ingestion pipeline
- Basic contrail detection with logging
- OpenSky flight data cached
- Manual correlation interface

### 6.2 Phase 2: Automation (Weeks 4-6)

**Priority: HIGH**

#### Goals
- Automated flight correlation
- Geolocalization calculations
- Enhanced detection algorithms

#### Tasks

| ID | Task | Priority | Dependencies | Est. Hours |
|----|------|----------|--------------|------------|
| 2.1 | Auto flight correlation algorithm | P0 | Phase 1 | 12 |
| 2.2 | Single-camera geolocalization | P0 | Phase 1 | 10 |
| 2.3 | Aircraft detection (YOLOv8) | P1 | Phase 1 | 16 |
| 2.4 | Multi-camera triangulation | P1 | 2.2 | 14 |
| 2.5 | Detection API endpoints | P0 | 1.7 | 6 |
| 2.6 | Detection browser UI | P1 | 2.5 | 12 |
| 2.7 | Map visualization (Leaflet) | P1 | 2.5 | 10 |

**Deliverables:**
- Automated detection-to-flight matching
- Position estimation on map
- Enhanced detection accuracy
- Web interface for browsing detections

### 6.3 Phase 3: Enhancement (Weeks 7-9)

**Priority: MEDIUM**

#### Goals
- Improved CV accuracy
- Performance optimization
- Advanced analytics

#### Tasks

| ID | Task | Priority | Dependencies | Est. Hours |
|----|------|----------|--------------|------------|
| 3.1 | Motion tracking (optical flow) | P1 | Phase 2 | 14 |
| 3.2 | Deep learning contrail seg | P2 | Phase 2 | 20 |
| 3.3 | Batch processing pipeline | P1 | Phase 2 | 10 |
| 3.4 | Detection statistics dashboard | P2 | 2.6 | 8 |
| 3.5 | API rate limiting/caching | P1 | Phase 2 | 6 |
| 3.6 | Redis caching layer | P1 | Phase 2 | 8 |

**Deliverables:**
- Improved detection accuracy
- Performance optimizations
- Analytics dashboard

### 6.4 Phase 4: Scale (Weeks 10-12)

**Priority: LOW**

#### Goals
- Multi-camera network
- External API expansion
- Production hardening

#### Tasks

| ID | Task | Priority | Dependencies | Est. Hours |
|----|------|----------|--------------|------------|
| 4.1 | Windy.com API integration | P2 | Phase 2 | 8 |
| 4.2 | ADS-B Exchange redundancy | P2 | 1.2 | 6 |
| 4.3 | WebSocket real-time updates | P1 | 2.6 | 10 |
| 4.4 | Scheduled processing jobs | P1 | Phase 2 | 8 |
| 4.5 | Alerting system | P2 | 3.4 | 6 |
| 4.6 | Docker containerization | P1 | All | 8 |
| 4.7 | Documentation | P1 | All | 8 |

**Deliverables:**
- Production-ready system
- Multi-camera support
- Real-time updates
- Complete documentation

---

## 7. Technology Stack Recommendations

### 7.1 Backend (Python/FastAPI)

```yaml
# Core Framework
fastapi: ^0.104.0
uvicorn: ^0.24.0
python-multipart: ^0.0.6

# Database
sqlalchemy: ^2.0.0
alembic: ^1.12.0
asyncpg: ^0.29.0          # PostgreSQL async driver
redis: ^5.0.0             # Caching layer

# Computer Vision
opencv-python: ^4.8.0
opencv-contrib-python: ^4.8.0
scikit-image: ^0.21.0
numpy: ^1.24.0
scipy: ^1.11.0
pillow: ^10.0.0
imageio: ^2.31.0

# Deep Learning (Optional GPU)
ultralytics: ^8.0.0       # YOLOv8
torch: ^2.0.0
torchvision: ^0.15.0

# Video/Stream Processing
aiortc: ^1.6.0            # WebRTC handling
hls4ml: ^0.1.0            # HLS stream parsing
requests: ^2.31.0         # HTTP client

# Geospatial
pyproj: ^3.6.0            # Coordinate transformations
geopy: ^2.4.0             # Geocoding/distance calculations

# Task Queue/Scheduling
celery: ^5.3.0            # Background task processing
apscheduler: ^3.10.0      # Scheduled jobs

# Utilities
pydantic: ^2.0.0
python-jose: ^3.3.0       # JWT handling
httpx: ^0.25.0            # Async HTTP client
```

### 7.2 Frontend (React)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "redux": "^4.2.0",
    "@reduxjs/toolkit": "^1.9.0",
    "@mui/material": "^5.14.0",
    "@mui/icons-material": "^5.14.0",
    "leaflet": "^1.9.0",
    "react-leaflet": "^4.2.0",
    "axios": "^1.6.0",
    "socket.io-client": "^4.7.0",
    "date-fns": "^2.30.0",
    "recharts": "^2.10.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "vitest": "^1.0.0",
    "playwright": "^1.40.0",
    "@types/leaflet": "^1.9.0"
  }
}
```

### 7.3 Infrastructure

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Database** | PostgreSQL 15 + TimescaleDB | Time-series support, geospatial extensions |
| **Cache** | Redis 7 | Low-latency caching, pub/sub |
| **Task Queue** | Celery + Redis | Background CV processing |
| **Container** | Docker + Docker Compose | Consistent deployment |
| **GPU** | NVIDIA CUDA (optional) | Deep learning acceleration |
| **Storage** | Local SSD + S3 (optional) | Image storage, archival |

---

## 8. System Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CHEMTRAIL TRACKER - COMPONENT VIEW               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  FRONTEND LAYER (React)                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Camera     │  │  Detection  │  │   Map       │  │  Analytics  │    │
│  │  Config UI  │  │  Browser    │  │  Viewer     │  │  Dashboard  │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
│         │                │                │                │            │
│         └────────────────┴────────────────┴────────────────┘            │
│                                  │                                       │
│                         Socket.IO + REST                                 │
│                                  │                                       │
│  BACKEND LAYER (FastAPI)                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  API ROUTES                                                      │    │
│  │  /api/cameras      /api/detections    /api/flights    /api/stats │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│         │                │                │                │            │
│         └────────────────┴────────────────┴────────────────┘            │
│                                  │                                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SERVICES                                                        │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ Camera      │  │ Detection   │  │ Flight      │              │    │
│  │  │ Service     │  │ Service     │  │ Service     │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ Geo         │  │ Correlation │  │ FR24Flight  │              │    │
│  │  │ Calculator  │  │ Engine      │  │ Service     │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│         │                │                                               │
│         └────────────────┴───────────────────────────────┐              │
│                                                          │              │
│  WORKER LAYER (Celery)                                   │              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  CV WORKERS                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ Image       │  │ Contrail    │  │ Aircraft    │              │    │
│  │  │ Ingestion   │  │ Detector    │  │ Detector    │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  │  ┌─────────────┐  ┌─────────────┐                               │    │
│  │  │ Motion      │  │ Frame       │                               │    │
│  │  │ Tracker     │  │ Analyzer    │                               │    │
│  │  └─────────────┘  └─────────────┘                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│         │                                                                │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  EXTERNAL API CLIENTS                                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ OpenSky     │  │ FR24 SDK    │  │ Webcam      │              │    │
│  │  │ Network     │  │ (sync→async)│  │ APIs        │              │    │
│  │  │ (async)     │  │             │  │             │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  DATA LAYER                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  PostgreSQL │  │   Redis     │  │   Local     │  │    S3/MinIO │    │
│  │  (Primary)  │  │   (Cache)   │  │   Storage   │  │   (Archive) │    │
│  │             │  │             │  │             │  │             │    │
│  │  FlightCache│  │             │  │             │  │             │    │
│  │  +13 FR24   │  │             │  │             │  │             │    │
│  │  fields     │  │             │  │             │  │             │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Risk Assessment & Mitigation

### 9.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Webcam API reliability | High | High | Multi-provider fallback, local camera option |
| CV false positives | High | Medium | Multi-stage validation, ML filtering |
| API rate limiting | Medium | Medium | Caching, request queuing, member accounts |
| Geolocalization accuracy | Medium | Medium | Multi-camera triangulation, flight correlation |
| Processing performance | Medium | Medium | GPU acceleration, batch processing, Redis cache |

### 9.2 Legal/Ethical Considerations

| Concern | Status | Notes |
|---------|--------|-------|
| Webcam ToS compliance | Review required | Verify each API's terms of service |
| Flight data usage | Compliant | OpenSky/ADS-B Exchange allow research use |
| Privacy considerations | Low risk | Public airspace, public webcams |
| Data retention policy | Define needed | Recommend 90-day default, configurable |

---

## 10. Success Metrics

### 10.1 Technical KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Detection accuracy | >85% | Manual validation sample |
| False positive rate | <15% | Per 1000 images processed |
| Processing latency | <5s | Image ingest to logged detection |
| Flight correlation rate | >70% | Detections matched to flights |
| Geolocalization error | <5km | Triangulated vs actual position |
| System uptime | >99% | Production deployment |

### 10.2 Adoption Metrics

| Metric | Target | Timeline |
|--------|--------|----------|
| Active cameras | 10+ | Phase 3 |
| Detections/day | 100+ | Phase 3 |
| API consumers | 5+ | Phase 4 |
| GitHub stars | 50+ | 3 months post-launch |

---

## 11. Appendix

### 11.1 File Paths

All chemtrail tracker artifacts will be stored in:

```
C:\Users\antmi\ground-station\
├── docs\chemtrail-tracker\
│   ├── ARCHITECTURE.md          (this document)
│   ├── FR24_INTEGRATION_ARCHITECTURE.md  (FR24 detailed architecture)
│   ├── FR24_DEPLOYMENT.md       (FR24 deployment guide)
│   ├── FR24_IMPLEMENTATION_STATUS.md  (FR24 implementation status)
│   ├── API-INTEGRATION.md       (detailed API docs)
│   ├── CV-ALGORITHMS.md         (computer vision details)
│   └── DEPLOYMENT.md            (deployment guide)
├── backend\chemtrail\           (new module)
│   ├── __init__.py
│   ├── api\
│   │   ├── opensky_client.py
│   │   ├── fr24_client.py       (FR24 SDK wrapper, ~360 LOC)
│   │   └── webcam_clients.py
│   ├── services\
│   │   ├── camera_service.py
│   │   ├── flight_service.py    (dual-source: OpenSky + FR24)
│   │   ├── fr24_flight_service.py  (FR24 service, ~345 LOC)
│   │   └── geocalc_service.py
│   ├── archive\
│   │   ├── detection_service.py  (FR24 enrichment in detection pipeline)
│   │   └── ...
│   └── workers\
│       ├── cv_worker.py
│       └── ...
├── backend\db\
│   └── models.py                (FlightCache +13 FR24 fields)
├── backend\alembic\versions\
│   └── fr24_001_add_fr24_fields_to_flight_cache.py  (DB migration)
├── backend\tests\chemtrail\
│   └── test_fr24_integration.py  (32 FR24 tests, all passing)
└── frontend\src\features\chemtrail\
    ├── components\
    ├── pages\
    ├── store\
    └── api\
```

### 11.2 References

1. OpenSky Network API: https://opensky-network.org/apidoc/
2. ADS-B Exchange API: https://www.adsbexchange.com/data/
3. OpenCV Documentation: https://docs.opencv.org/
4. YOLOv8 (Ultralytics): https://docs.ultralytics.com/
5. Hough Transform: https://en.wikipedia.org/wiki/Hough_transform
6. PyProj: https://pyproj4.github.io/pyproj/

### 11.3 Glossary

| Term | Definition |
|------|------------|
| **AOS** | Acquisition of Signal - when aircraft enters camera view |
| **ADS-B** | Automatic Dependent Surveillance-Broadcast |
| **Azimuth** | Horizontal angle from North (0-360 degrees) |
| **Contrail** | Condensation trail from aircraft |
| **Dual-Source** | Flight data from both OpenSky and FR24 |
| **Elevation** | Vertical angle from horizon (-90 to 90 degrees) |
| **FOV** | Field of View - angular extent visible to camera |
| **FR24** | Flightradar24 - secondary flight data source for enrichment |
| **FR24 SDK** | Python SDK for Flightradar24 API (fr24sdk>=1.0.0) |
| **ICAO24** | 24-bit aircraft identifier (hex code) |
| **LOS** | Loss of Signal - when aircraft exits camera view |
| **MLAT** | Multilateration - position from multiple receivers |
| **RTSP** | Real Time Streaming Protocol |
| **WGS84** | World Geodetic System 1984 (GPS coordinate system) |

---

*Document prepared by Dr. Sarah Kim, Technical Product Strategist & Engineering Lead*
