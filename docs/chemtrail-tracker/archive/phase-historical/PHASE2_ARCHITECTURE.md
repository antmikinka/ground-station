# Chemtrail Webcam Tracker - Phase 2 Architecture
## Footage Acquisition, Sorting, and End-to-End Pipeline Orchestration

**Version:** 2.0.0  
**Author:** Dr. Sarah Kim, Technical Product Strategist & Engineering Lead  
**Date:** 2026-04-11  
**Status:** Ready for Implementation

---

## Executive Summary

Phase 2 transforms the Chemtrail Webcam Tracker from a detection-focused pipeline into a **complete end-to-end footage management system**. This phase adds:

1. **Live Webcam Feed Acquisition** - Continuous ingestion from RTSP/MJPEG sky-facing webcams
2. **Historical Video Ingestion** - Scan and import local video archives with metadata cataloging
3. **Video Sorting & Cataloging** - Intelligent organization by camera, date, weather, and quality
4. **Pipeline Orchestration** - Unified workflow from acquisition through detection to archive

### Business Objectives

| Objective | Description | Success Metric |
|-----------|-------------|----------------|
| **Continuous Monitoring** | 24/7 webcam feed ingestion | >95% uptime on registered cameras |
| **Archive Integration** | Import existing video libraries | 100% of local videos cataloged |
| **Intelligent Sorting** | Auto-categorize by location, weather, quality | <2s search latency |
| **End-to-End Automation** | Zero-touch processing pipeline | <5% manual intervention rate |

---

## 1. System Architecture Overview

### 1.1 Phase 2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: FOOTAGE ACQUISITION & ORCHESTRATION                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  EXTERNAL SOURCES                                                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│  │  LIVE WEBCAMS   │  │  HISTORICAL     │  │  FLIGHT DATA    │                 │
│  │                 │  │  VIDEO FILES    │  │  (Dual-Source)  │                 │
│  │  • RTSP Streams │  │                 │  │                 │                 │
│  │  • MJPEG Feeds  │  │  • Local Files  │  │  • OpenSky      │                 │
│  │  • YouTube Live │  │  • Network      │  │  • FR24         │                 │
│  │  • Airport Cams │  │  • Archives     │  │  • ADS-B Exch   │                 │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                 │
│           │                     │                     │                          │
│           └─────────────────────┴─────────────────────┘                          │
│                                   │                                              │
│  ┌────────────────────────────────▼─────────────────────────────────────────┐   │
│  │                    SOURCES LAYER (NEW - Phase 2)                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Webcam     │  │ Historical  │  │   Video     │  │   Weather   │     │   │
│  │  │  Manager    │  │ Ingestor    │  │  Catalog    │  │  Enrichment │     │   │
│  │  │             │  │             │  │             │  │             │     │   │
│  │  │  • RTSP     │  │  • Scan     │  │  • Index    │  │  • Tag      │     │   │
│  │  │  • MJPEG    │  │  • Import   │  │  • Sort     │  │  • enrich   │     │   │
│  │  │  • YouTube  │  │  • Catalog  │  │  • Filter   │  │  • Weather  │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                              │
│                                   ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    PIPELINE ORCHESTRATOR (NEW - Phase 2)                 │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Workflow Engine: Acquisition → Sorting → Detection → Archive   │    │    │
│  │  │  • Schedule management    • Quality scoring    • Error handling │    │    │
│  │  │  • Resource allocation    • Priority queuing   • Progress track │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                                   │                                              │
│                                   ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    EXISTING DETECTION PIPELINE (Phase 1.5 + FR24)        │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │    │
│  │  │   Chunker   │  │  CV Detect  │  │   Flight    │  │   Archive   │    │    │
│  │  │             │  │             │  │  Correlate  │  │  (ChromaDB) │    │    │
│  │  └─────────────┘  └─────────────┘  └──────┬──────┘  └─────────────┘    │    │
│  │                                           │                              │    │
│  │  ┌────────────────────────────────────────┘                              │    │
│  │  │  FR24 Enrichment:                                                     │    │
│  │  │  • Airline branding (painted_as, operating_as)                        │    │
│  │  │  • Airport codes (ICAO/IATA)                                          │    │
│  │  │  • Flight tracks                                                      │    │
│  │  │  • Enhanced correlation scoring                                       │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  DATA LAYER                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  PostgreSQL │  │   Redis     │  │  ChromaDB   │  │   File      │            │
│  │  (Catalog)  │  │   (Queue)   │  │  (Archive)  │  │  Storage    │            │
│  │  +FlightCache│  │             │  │  +metadata  │  │             │            │
│  │  +13 FR24   │  │             │  │             │  │             │            │
│  │  fields     │  │             │  │             │  │             │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Module Responsibilities

| Module | Responsibility | Phase |
|--------|---------------|-------|
| `sources/webcam_manager.py` | Live stream acquisition, health monitoring | Phase 2 (NEW) |
| `sources/historical_ingestor.py` | Local video scanning, import, cataloging | Phase 2 (NEW) |
| `sources/video_catalog.py` | Video metadata, sorting, filtering | Phase 2 (NEW) |
| `sources/weather_enrichment.py` | Weather API integration, tagging | Phase 2 (NEW) |
| `sources/pipeline_orchestrator.py` | End-to-end workflow coordination | Phase 2 (NEW) |
| `api/fr24_client.py` | FR24 SDK wrapper (sync, asyncio.to_thread) | FR24 Integration (COMPLETE) |
| `services/fr24_flight_service.py` | FR24 service with config, health checks, enrichment | FR24 Integration (COMPLETE) |
| `services/flight_service.py` | Dual-source flight data (OpenSky + FR24) | FR24 Integration (COMPLETE) |
| `archive/detection_service.py` | Detection pipeline with FR24 enrichment | Phase 1.5 + FR24 (COMPLETE) |
| `archive/chunker.py` | Video segmentation | Phase 1.5 (EXISTING) |
| `archive/vector_store.py` | Vector archive | Phase 1.5 (EXISTING) |

**FR24 Integration Status:**
- ✅ All P0/P1 items complete
- ✅ 32 FR24-specific tests passing
- ✅ 318 total tests passing (286 original + 32 FR24)
- ✅ Database migration created and applied
- ✅ Production-ready with graceful degradation

---

## 2. Public Webcam Source Catalog

### 2.1 Sky-Facing Webcam APIs

#### Windy.com Webcams API
```
Base URL: https://api.windy.com/api/webcams
Authentication: API Key (free tier: 5000 calls/day)
Response Format: JSON

Endpoints:
  GET /webcams/nearby/{lat},{lon},{radius}
  GET /webcams/category/sky
  GET /webcams/category/airport

Example Request:
  GET https://api.windy.com/api/webcams/nearby/47.6062,-122.3321,50
  ?category=sky,airport
  &lang=en
  &fields=location,image,player,embed
  &apikey={YOUR_API_KEY}

Response Fields:
  - id: Webcam identifier
  - status: active | inactive
  - location: {lat, lon, city, country}
  - image: {current {preview, thumbnail}, sizes {preview, thumbnail}}
  - player: {live {available, embed}, day {available, embed}}
  - update: Last update timestamp
```

#### WebcamTaxi (Direct Stream Access)
```
Base URLs: Various (per-camera)
Authentication: None (open streams)
Stream Types: MJPEG, HLS

Discovery:
  - Browse: https://webcamtaxi.com/en/usa/washington/seattle.html
  - Filter: sky, airport, outdoor categories
  
Direct Stream Pattern:
  MJPEG: https://webcamtaxi.com/stream/{camera_id}.mjpeg
  HLS:   https://webcamtaxi.com/stream/{camera_id}/playlist.m3u8

Note: No official API - screen scraping or direct URL discovery required
```

#### EarthCam API (Premium)
```
Base URL: https://api.earthcam.com
Authentication: API Key + OAuth 2.0
Cost: $99-499/month (enterprise)

Endpoints:
  GET /cameras/search?lat={lat}&lon={lon}&radius={km}
  GET /cameras/{id}/live
  GET /cameras/{id}/timelapse

Features:
  - PTZ (Pan-Tilt-Zoom) control
  - High-definition streams
  - Historical timelapse access
  - Metadata: lat/lon, orientation, zoom level
```

#### Airport Webcam Networks
```
Major Airport Live Webcam Sources:

1. Seattle-Tacoma (SEA):
   - URL: https://www.portseattle.org/sea-tac-webcams
   - Streams: Terminal, runway, parking views
   - Format: MJPEG snapshots (updated every 5s)

2. San Francisco (SFO):
   - URL: https://www.flysfo.com/webcams
   - Streams: Runway, bay view, terminal

3. Los Angeles (LAX):
   - URL: https://www.flylax.com/lax-webcams
   - Streams: Runway overlook, theme building

4. European Airports (via Skyweather Network):
   - RTSP endpoints available for research partnerships
```

### 2.2 YouTube Live Stream Integration (yt-dlp)

```python
# YouTube Live Stream URLs for sky/airport cams
YOUTUBE_SKY_CAM_CHANNELS = [
    # Airport live streams
    "https://www.youtube.com/watch?v=XXX_live_airport",
    "https://www.youtube.com/c/AirportWebcam/live",
    
    # Sky watching channels
    "https://www.youtube.com/c/SkyWatcher/live",
    "https://www.youtube.com/c/ContrailSpotter/live",
]

# yt-dlp extraction pattern
import yt_dlp

ydl_opts = {
    'format': 'best[height<=720]',  # Limit resolution for bandwidth
    'live_from_start': True,
    'fragment_retries': 3,
    'http_chunk_size': '10M',
    'outtmpl': '/tmp/yt_dl_%(id)s.%(ext)s',
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(youtube_url, download=False)
    live_url = info['url']  # Direct stream URL for ffmpeg
```

### 2.3 Self-Hosted Camera Registration

```python
# Camera registration schema for self-hosted RTSP/MJPEG cameras
CAMERA_REGISTRATION_SCHEMA = {
    "required": {
        "name": str,                    # Human-readable name
        "url": str,                     # RTSP or MJPEG URL
        "camera_type": "rtsp" | "mjpeg" | "hls",
        "location": {
            "latitude": float,          # WGS84 decimal degrees
            "longitude": float,
            "altitude": float,          # Meters AMSL
        },
        "orientation": {
            "azimuth": float,           # 0-360 (N=0, E=90)
            "elevation": float,         # -90 to 90 (0=horizon)
        },
    },
    "optional": {
        "fov_horizontal": float,        # Degrees
        "fov_vertical": float,
        "image_width": int,
        "image_height": int,
        "weather_station_id": str,      # Link to weather data
        "quality_threshold": float,     # Minimum quality score (0-1)
        "schedule": {                   # Recording schedule
            "enabled": bool,
            "start_time": str,          # HH:MM (local time)
            "end_time": str,
            "days": [str],              # ["mon", "tue", ...]
        },
    }
}
```

---

## 3. Video Sorting & Cataloging Schema

### 3.1 Video Metadata Schema

```python
VIDEO_CATALOG_SCHEMA = {
    "id": UUID,                         # Unique video identifier
    "source": {
        "type": "live_webcam" | "historical_file" | "youtube_archive",
        "source_id": str,               # Camera ID or file path
        "source_url": str,              # Original URL or path
        "ingested_at": datetime,        # UTC timestamp
    },
    "location": {
        "camera_id": UUID,              # Linked camera record
        "camera_name": str,
        "latitude": float,
        "longitude": float,
        "altitude": float,
        "azimuth": float,
        "elevation": float,
    },
    "temporal": {
        "start_time": datetime,         # Video start (UTC)
        "end_time": datetime,           # Video end (UTC)
        "duration_seconds": float,
        "day_night": "day" | "night" | "dawn" | "dusk",
    },
    "weather": {
        "condition": str,               # "clear", "cloudy", "overcast", "rain"
        "temperature_c": float,
        "humidity_pct": float,
        "wind_speed_ms": float,
        "wind_direction": float,        # Degrees
        "visibility_km": float,
        "cloud_cover_pct": float,
        "weather_source": str,          # "open_meteo" | "manual"
    },
    "quality": {
        "score": float,                 # Overall quality (0-1)
        "resolution": str,              # "480p" | "720p" | "1080p" | "4K"
        "resolution_width": int,
        "resolution_height": int,
        "fps": float,
        "bitrate_kbps": int,
        "codec": str,                   # "h264" | "h265" | "vp9"
        "stability_score": float,       # Camera stability (0-1)
        "lighting_score": float,        # Lighting quality (0-1)
        "sharpness_score": float,       # Image sharpness (0-1)
    },
    "content": {
        "sky_coverage_pct": float,      # Percentage of sky in frame
        "has_contrails": bool,          # Pre-detection flag
        "has_aircraft": bool,
        "obstruction_pct": float,       # Buildings/trees blocking view
    },
    "processing": {
        "status": "pending" | "processing" | "completed" | "failed",
        "chunk_count": int,
        "detection_count": int,
        "archived": bool,
        "processed_at": datetime,
        "error_message": str,
    },
    "storage": {
        "file_path": str,               # Local file path
        "file_size_bytes": int,
        "checksum_sha256": str,
        "thumbnail_path": str,
    }
}
```

### 3.2 Quality Scoring Algorithm

```python
def calculate_quality_score(video_path: str) -> dict:
    """
    Calculate video quality metrics for sorting and filtering.
    
    Returns dict with:
    - overall_score: 0.0-1.0
    - resolution_score: Based on pixel count
    - stability_score: Camera shake detection
    - lighting_score: Brightness histogram analysis
    - sharpness_score: Edge detection variance
    """
    import cv2
    import numpy as np
    from pathlib import Path
    
    # Extract metadata via ffprobe
    metadata = get_video_metadata(video_path)
    
    # Resolution score (normalized to 1080p = 1.0)
    target_pixels = 1920 * 1080
    actual_pixels = metadata['width'] * metadata['height']
    resolution_score = min(1.0, actual_pixels / target_pixels)
    
    # Sample frames for analysis
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Analyze 5 evenly-spaced frames
    frame_indices = np.linspace(0, total_frames - 1, 5, dtype=int)
    
    stability_scores = []
    lighting_scores = []
    sharpness_scores = []
    
    prev_frame = None
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Stability: Compare with previous frame (optical flow magnitude)
        if prev_frame is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_frame, gray, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2,
                flags=0
            )
            motion_magnitude = np.mean(np.linalg.norm(flow, axis=2))
            # Lower motion = more stable (for stationary cameras)
            stability = max(0, 1.0 - (motion_magnitude / 50))
            stability_scores.append(stability)
        
        # Lighting: Histogram analysis (ideal = well-distributed)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_norm = hist.flatten() / hist.sum()
        # Avoid under/over exposed (penalize extreme histograms)
        mean_brightness = np.mean(gray)
        lighting = 1.0 - abs(mean_brightness - 128) / 128
        lighting_scores.append(lighting)
        
        # Sharpness: Variance of Laplacian
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = np.var(laplacian)
        # Normalize (typical range 100-1000 for good focus)
        sharpness_score = min(1.0, sharpness / 500)
        sharpness_scores.append(sharpness_score)
        
        prev_frame = gray
    
    cap.release()
    
    # Weighted average for overall score
    weights = {
        'resolution': 0.25,
        'stability': 0.25,
        'lighting': 0.25,
        'sharpness': 0.25,
    }
    
    overall_score = (
        weights['resolution'] * resolution_score +
        weights['stability'] * np.mean(stability_scores) if stability_scores else 0.5 +
        weights['lighting'] * np.mean(lighting_scores) if lighting_scores else 0.5 +
        weights['sharpness'] * np.mean(sharpness_scores) if sharpness_scores else 0.5
    )
    
    return {
        'overall_score': overall_score,
        'resolution_score': resolution_score,
        'stability_score': np.mean(stability_scores) if stability_scores else 0.5,
        'lighting_score': np.mean(lighting_scores) if lighting_scores else 0.5,
        'sharpness_score': np.mean(sharpness_scores) if sharpness_scores else 0.5,
        'metadata': metadata,
    }
```

### 3.3 ChromaDB Extended Schema for Video Catalog

```python
# ChromaDB collection for video catalog (separate from detection archive)
VIDEO_CATALOG_COLLECTION = "chemtrail_video_catalog"

VIDEO_METADATA_SCHEMA = {
    # Base identification
    "video_id": str,                    # UUID
    "source_type": str,                 # "live_webcam" | "historical_file"
    "source_id": str,                   # Camera ID or file hash
    
    # Location (for filtering)
    "camera_id": str,
    "camera_name": str,
    "camera_lat": float,
    "camera_lon": float,
    
    # Temporal (for filtering)
    "start_timestamp": float,           # Unix timestamp
    "end_timestamp": float,
    "day_night": str,                   # "day" | "night" | "dawn" | "dusk"
    
    # Weather (for filtering)
    "weather_condition": str,           # "clear", "cloudy", etc.
    "cloud_cover_pct": float,
    "visibility_km": float,
    
    # Quality (for filtering/sorting)
    "quality_score": float,             # 0.0-1.0
    "resolution": str,                  # "480p", "720p", "1080p"
    "stability_score": float,
    "lighting_score": float,
    
    # Content (for filtering)
    "sky_coverage_pct": float,
    "has_contrails": bool,
    
    # Processing status
    "processing_status": str,           # "pending" | "processing" | "completed"
    "detection_count": int,
    
    # Storage
    "file_path": str,
    "file_size_bytes": int,
    
    # Embedding (for semantic search)
    "indexed_at": str,                  # ISO8601
}

# Example usage
def add_video_to_catalog(
    vector_store: ChemtrailVectorStore,
    video_id: str,
    embedding: list[float],
    metadata: dict
):
    """Add video catalog entry with embedding for semantic search."""
    vector_store._collection.upsert(
        ids=[video_id],
        embeddings=[embedding],
        metadatas=[metadata],
    )

def search_videos(
    vector_store: ChemtrailVectorStore,
    query_embedding: list[float] = None,
    camera_id: str = None,
    date_from: datetime = None,
    date_to: datetime = None,
    min_quality: float = None,
    weather_condition: str = None,
    n_results: int = 10,
) -> list[dict]:
    """Search video catalog with filters."""
    where = {}
    
    if camera_id:
        where["camera_id"] = camera_id
    if weather_condition:
        where["weather_condition"] = weather_condition
    if min_quality:
        where["quality_score"] = {"$gte": min_quality}
    
    results = vector_store._collection.get(
        where=where,
        include=["metadatas"],
        limit=n_results * 3,
    )
    
    # Filter by date range in Python
    filtered = []
    for meta in results["metadatas"]:
        start_ts = meta.get("start_timestamp", 0)
        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
        
        if date_from and start_dt < date_from:
            continue
        if date_to and start_dt > date_to:
            continue
        
        filtered.append(meta)
    
    # Sort by quality score
    filtered.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    
    return filtered[:n_results]
```

---

## 4. Weather API Integration Plan

### 4.1 Open-Meteo Free API

```
Open-Meteo provides free weather data for research/hobby use.
No API key required for non-commercial use.

Base URL: https://api.open-meteo.com/v1/

Historical Weather API:
  GET /archive?latitude={lat}&longitude={lon}
      &start_date={YYYY-MM-DD}
      &end_date={YYYY-MM-DD}
      &hourly={parameters}
      &timezone=auto

Available Parameters:
  - temperature_2m
  - cloud_cover_total
  - visibility
  - wind_speed_10m
  - wind_direction_10m
  - weather_code
  - humidity_2m

Weather Codes (WMO):
  0 = Clear sky
  1-3 = Mainly clear / partly cloudy
  45-48 = Fog / depositing rime fog
  51-67 = Drizzle / rain
  71-77 = Snow
  80-82 = Rain showers
  86 = Snow showers
  95-99 = Thunderstorm
```

### 4.2 Weather Enrichment Service

```python
# sources/weather_enrichment.py
"""Weather API integration for video tagging."""

import httpx
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

@dataclass
class WeatherData:
    """Weather conditions at a specific time and location."""
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    cloud_cover_pct: float
    visibility_km: float
    wind_speed_ms: float
    wind_direction: float
    weather_code: int
    weather_description: str

WEATHER_CODE_DESCRIPTION = {
    0: "clear",
    1: "mainly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "fog_rime",
    51: "light_drizzle",
    53: "moderate_drizzle",
    55: "dense_drizzle",
    61: "light_rain",
    63: "moderate_rain",
    65: "heavy_rain",
    71: "light_snow",
    73: "moderate_snow",
    75: "heavy_snow",
    80: "light_rain_shower",
    81: "moderate_rain_shower",
    82: "violent_rain_shower",
    95: "thunderstorm",
    96: "thunderstorm_hail",
    99: "thunderstorm_heavy_hail",
}

class WeatherEnrichmentService:
    """Fetch and cache weather data for video enrichment."""
    
    ARCHIVE_API_URL = "https://api.open-meteo.com/v1/archive"
    
    def __init__(self, cache_ttl_hours: int = 24):
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = cache_ttl_hours
    
    async def get_historical_weather(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
    ) -> list[WeatherData]:
        """Fetch historical weather for a time range."""
        cache_key = f"{latitude}_{longitude}_{start_time}_{end_time}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, cached_at = self.cache[cache_key]
            if (datetime.now(timezone.utc) - cached_at).total_seconds() < self.cache_ttl * 3600:
                return cached_data
        
        # Fetch from API
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
            "hourly": "temperature_2m,relative_humidity_2m,cloud_cover,visibility,wind_speed_10m,wind_direction_10m,weather_code",
            "timezone": "auto",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.ARCHIVE_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Parse hourly data
        weather_data = self._parse_hourly_data(data)
        
        # Cache result
        self.cache[cache_key] = (weather_data, datetime.now(timezone.utc))
        
        return weather_data
    
    def _parse_hourly_data(self, api_response: dict) -> list[WeatherData]:
        """Parse Open-Meteo hourly response into WeatherData objects."""
        hourly = api_response.get("hourly", {})
        times = hourly.get("time", [])
        
        weather_data = []
        for i, time_str in enumerate(times):
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            
            weather_data.append(WeatherData(
                timestamp=timestamp,
                temperature_c=hourly.get("temperature_2m", [])[i],
                humidity_pct=hourly.get("relative_humidity_2m", [])[i],
                cloud_cover_pct=hourly.get("cloud_cover", [])[i],
                visibility_km=hourly.get("visibility", [])[i] / 1000,  # m -> km
                wind_speed_ms=hourly.get("wind_speed_10m", [])[i] / 3.6,  # km/h -> m/s
                wind_direction=hourly.get("wind_direction_10m", [])[i],
                weather_code=hourly.get("weather_code", [])[i],
                weather_description=WEATHER_CODE_DESCRIPTION.get(
                    hourly.get("weather_code", [])[i], "unknown"
                ),
            ))
        
        return weather_data
    
    def get_weather_for_video(
        self,
        weather_data: list[WeatherData],
        video_start: datetime,
        video_end: datetime,
    ) -> dict:
        """Get aggregated weather for a video's duration."""
        # Filter weather data points within video timeframe
        relevant = [
            w for w in weather_data
            if video_start <= w.timestamp <= video_end
        ]
        
        if not relevant:
            return None
        
        # Average values
        avg_cloud_cover = sum(w.cloud_cover_pct for w in relevant) / len(relevant)
        avg_temp = sum(w.temperature_c for w in relevant) / len(relevant)
        avg_humidity = sum(w.humidity_pct for w in relevant) / len(relevant)
        avg_visibility = sum(w.visibility_km for w in relevant) / len(relevant)
        
        # Dominant weather condition
        weather_codes = [w.weather_code for w in relevant]
        dominant_code = max(set(weather_codes), key=weather_codes.count)
        
        return {
            "condition": WEATHER_CODE_DESCRIPTION.get(dominant_code, "unknown"),
            "temperature_c": round(avg_temp, 1),
            "humidity_pct": round(avg_humidity, 1),
            "cloud_cover_pct": round(avg_cloud_cover, 1),
            "visibility_km": round(avg_visibility, 1),
            "weather_code": dominant_code,
        }
```

### 4.3 Weather Integration Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Video Ingest   │────▶│  Extract Time   │────▶│  Open-Meteo     │
│  (any source)   │     │  + Location     │     │  API Request    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│  Video Catalog  │◀────│  Enrich Video   │◀─────────────┘
│  (metadata +    │     │  Metadata:      │
│   weather tag)  │     │  - condition    │
│                 │     │  - cloud_cover  │
│                 │     │  - visibility   │
└─────────────────┘     └─────────────────┘
```

---

## 5. yt-dlp Integration for Archived Footage

### 5.1 YouTube Live Stream Download

```python
# sources/youtube_ingestor.py
"""YouTube stream ingestion for historical sky/airport footage."""

import yt_dlp
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class YouTubeVideoInfo:
    """Metadata for downloaded YouTube video."""
    video_id: str
    title: str
    channel: str
    duration_seconds: float
    upload_date: str
    view_count: int
    download_path: str
    resolution: str
    file_size_bytes: int

class YouTubeIngestor:
    """Download and catalog YouTube sky/airport videos."""
    
    DEFAULT_OPTIONS = {
        'format': 'best[height<=720]',  # Balance quality vs bandwidth
        'outtmpl': '%(output_dir)s/%(id)s.%(ext)s',
        'noplaylist': True,
        'extract_flat': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'writeinfojson': True,  # Save metadata JSON
        'writethumbnail': True,
    }
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def download_video(
        self,
        url: str,
        custom_options: Optional[Dict] = None,
    ) -> YouTubeVideoInfo:
        """Download a YouTube video."""
        options = {**self.DEFAULT_OPTIONS, **(custom_options or {})}
        options['outtmpl'] = options['outtmpl'].replace(
            '%(output_dir)s', str(self.output_dir)
        )
        
        with yt_dlp.YoutubeDL(options) as ydl:
            # Extract info and download
            info = ydl.extract_info(url, download=True)
            
            # Find downloaded file
            video_id = info.get('id')
            ext = info.get('ext', 'mp4')
            download_path = self.output_dir / f"{video_id}.{ext}"
            
            return YouTubeVideoInfo(
                video_id=video_id,
                title=info.get('title', 'Unknown'),
                channel=info.get('uploader', 'Unknown'),
                duration_seconds=info.get('duration', 0),
                upload_date=info.get('upload_date', ''),
                view_count=info.get('view_count', 0),
                download_path=str(download_path),
                resolution=f"{info.get('height', 'unknown')}p",
                file_size_bytes=Path(download_path).stat().st_size if download_path.exists() else 0,
            )
    
    def download_live_stream(
        self,
        channel_url: str,
        duration_minutes: int = 10,
    ) -> Optional[YouTubeVideoInfo]:
        """Download a segment from a live stream."""
        options = {
            **self.DEFAULT_OPTIONS,
            'live_from_start': True,
            'fragment_retries': 3,
            'http_chunk_size': '10M',
            'playlistend': 1,  # Only download first (current) segment
        }
        
        # Calculate end time for duration
        import time
        start_time = time.time()
        
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(channel_url, download=True)
            
            # Check if we've captured enough footage
            elapsed = time.time() - start_time
            if elapsed < duration_minutes * 60:
                # Continue recording
                time.sleep(duration_minutes * 60 - elapsed)
        
        # Process downloaded file
        return self.download_video(channel_url)
    
    def extract_channel_videos(
        self,
        channel_url: str,
        max_videos: int = 10,
    ) -> list[YouTubeVideoInfo]:
        """Extract metadata for all videos in a channel."""
        options = {
            **self.DEFAULT_OPTIONS,
            'extract_flat': True,
            'playlistend': max_videos,
        }
        
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            
            videos = []
            for entry in info.get('entries', []):
                if entry:
                    videos.append(YouTubeVideoInfo(
                        video_id=entry.get('id', ''),
                        title=entry.get('title', ''),
                        channel=entry.get('uploader', ''),
                        duration_seconds=entry.get('duration', 0),
                        upload_date=entry.get('upload_date', ''),
                        view_count=entry.get('view_count', 0),
                        download_path='',  # Not downloaded yet
                        resolution='unknown',
                        file_size_bytes=0,
                    ))
            
            return videos
```

### 5.2 Sky/Airport YouTube Channel Catalog

```python
# Known YouTube channels with sky/airport live streams
SKY_WATCH_YOUTUBE_CHANNELS = [
    # Airport live streams
    {
        "name": "Zurich Airport Live",
        "url": "https://www.youtube.com/c/ZurichAirport/live",
        "location": {"lat": 47.4647, "lon": 8.5492},
        "type": "airport",
    },
    {
        "name": "Tokyo Haneda Aircraft Spotting",
        "url": "https://www.youtube.com/c/TokyoHanedaSpotting",
        "location": {"lat": 35.5494, "lon": 139.7798},
        "type": "airport",
    },
    {
        "name": "Innsbruck Airport Runway Cam",
        "url": "https://www.youtube.com/c/InnsbruckAirport",
        "location": {"lat": 47.2602, "lon": 11.3440},
        "type": "airport",
    },
    
    # Sky watching / contrail spotting
    {
        "name": "SkyWatcher Network",
        "url": "https://www.youtube.com/c/SkyWatcherNetwork",
        "location": None,  # Multiple locations
        "type": "sky",
    },
    {
        "name": "Contrail Watch",
        "url": "https://www.youtube.com/c/ContrailWatch",
        "location": None,
        "type": "sky",
    },
]
```

---

## 6. New Module Specifications

### 6.1 sources/webcam_manager.py

```python
"""
Live Webcam Feed Acquisition Manager

Responsibilities:
1. Manage connections to RTSP/MJPEG/HLS streams
2. Monitor stream health and auto-reconnect
3. Capture continuous segments for processing
4. Handle multiple concurrent streams

Key Classes:
- WebcamManager: Central coordinator
- StreamConnection: Individual stream handler
- HealthMonitor: Stream quality monitoring
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import subprocess
from enum import Enum

class StreamType(Enum):
    RTSP = "rtsp"
    MJPEG = "mjpeg"
    HLS = "hls"
    YOUTUBE = "youtube"

class StreamStatus(Enum):
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    OFFLINE = "offline"

@dataclass
class StreamConfig:
    """Configuration for a webcam stream."""
    camera_id: str
    name: str
    url: str
    stream_type: StreamType
    location: Dict[str, float]  # lat, lon, alt
    orientation: Dict[str, float]  # azimuth, elevation
    segment_duration: int = 60  # seconds
    output_dir: str = "/tmp/chemtrail_webcam"

@dataclass
class StreamHealth:
    """Current health metrics for a stream."""
    status: StreamStatus
    uptime_seconds: float
    segment_count: int
    last_segment_time: datetime
    error_message: Optional[str] = None
    quality_score: float = 0.0

class WebcamManager:
    """
    Manages multiple live webcam streams.
    
    Usage:
        manager = WebcamManager()
        await manager.add_stream(config)
        await manager.start_all()
        
        # Or run continuously
        async with WebcamManager() as manager:
            await manager.run_forever()
    """
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.streams: Dict[str, StreamConnection] = {}
        self.health_monitor = HealthMonitor()
        self._running = False
    
    async def add_stream(self, config: StreamConfig) -> None:
        """Register a new stream."""
        connection = StreamConnection(config)
        self.streams[config.camera_id] = connection
        self.health_monitor.add_stream(config.camera_id)
    
    async def remove_stream(self, camera_id: str) -> None:
        """Remove and stop a stream."""
        if camera_id in self.streams:
            await self.streams[camera_id].stop()
            del self.streams[camera_id]
    
    async def start_all(self) -> None:
        """Start all registered streams."""
        tasks = [conn.start() for conn in self.streams.values()]
        await asyncio.gather(*tasks)
    
    async def stop_all(self) -> None:
        """Stop all streams."""
        tasks = [conn.stop() for conn in self.streams.values()]
        await asyncio.gather(*tasks)
    
    def get_health(self, camera_id: str) -> StreamHealth:
        """Get current health for a stream."""
        return self.health_monitor.get_health(camera_id)
    
    async def run_forever(self) -> None:
        """Run stream manager continuously."""
        self._running = True
        await self.start_all()
        
        while self._running:
            # Monitor health and auto-reconnect
            await self.health_monitor.check_all()
            await asyncio.sleep(30)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        await self.stop_all()


class StreamConnection:
    """Individual stream connection handler."""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.status = StreamStatus.OFFLINE
        self._process: Optional[subprocess.Popen] = None
        self._segment_count = 0
        self._start_time: Optional[datetime] = None
    
    async def start(self) -> None:
        """Start capturing stream."""
        self.status = StreamStatus.CONNECTING
        self._start_time = datetime.now(timezone.utc)
        
        # Launch ffmpeg subprocess
        output_pattern = Path(self.config.output_dir) / f"{self.config.camera_id}_%Y%m%d_%H%M%S.mp4"
        
        cmd = self._build_ffmpeg_cmd(str(output_pattern))
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        self.status = StreamStatus.STREAMING
    
    async def stop(self) -> None:
        """Stop capturing stream."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
        self.status = StreamStatus.OFFLINE
    
    def _build_ffmpeg_cmd(self, output_pattern: str) -> List[str]:
        """Build ffmpeg command for stream type."""
        base_cmd = [
            "ffmpeg",
            "-y",
            "-re",  # Read input at native frame rate
        ]
        
        # Stream-specific options
        if self.config.stream_type == StreamType.RTSP:
            base_cmd.extend(["-rtsp_transport", "tcp"])
        elif self.config.stream_type == StreamType.YOUTUBE:
            base_cmd.extend(["-user_agent", "Mozilla/5.0"])
        
        base_cmd.extend([
            "-i", self.config.url,
            "-c", "copy",
            "-segment_time", str(self.config.segment_duration),
            "-segment_format", "mp4",
            "-reset_timestamps", "1",
            output_pattern,
        ])
        
        return base_cmd


class HealthMonitor:
    """Monitor stream health and trigger reconnection."""
    
    def __init__(self):
        self.streams: Dict[str, StreamHealth] = {}
    
    def add_stream(self, camera_id: str) -> None:
        self.streams[camera_id] = StreamHealth(
            status=StreamStatus.OFFLINE,
            uptime_seconds=0,
            segment_count=0,
            last_segment_time=datetime.now(timezone.utc),
        )
    
    def get_health(self, camera_id: str) -> StreamHealth:
        return self.streams.get(camera_id)
    
    async def check_all(self) -> None:
        """Check health of all streams."""
        for camera_id, health in list(self.streams.items()):
            # Check if stream is producing segments
            time_since_segment = (
                datetime.now(timezone.utc) - health.last_segment_time
            ).total_seconds()
            
            if time_since_segment > 120:  # No segment for 2 minutes
                health.status = StreamStatus.ERROR
                health.error_message = "No recent segments"
```

### 6.2 sources/historical_ingestor.py

```python
"""
Historical Video Ingestor

Responsibilities:
1. Scan directories for video files
2. Extract metadata (duration, resolution, codec, creation date)
3. Import videos into catalog
4. Deduplicate by content hash

Key Classes:
- HistoricalIngestor: Main orchestrator
- VideoScanner: File discovery
- MetadataExtractor: ffprobe wrapper
"""

from typing import Dict, List, Optional
from pathlib import Path
import hashlib
import subprocess
import json
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class VideoMetadata:
    """Extracted video metadata."""
    file_path: str
    file_size_bytes: int
    checksum_sha256: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    codec: str
    bitrate_kbps: int
    creation_date: Optional[datetime]

class HistoricalIngestor:
    """
    Scan and import historical video files.
    
    Usage:
        ingestor = HistoricalIngestor(db_path="/path/to/db")
        results = await ingestor.scan_directory("/path/to/videos")
        
        # Import found videos
        for video in results.found:
            await ingestor.import_video(video)
    """
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
    
    def __init__(self, catalog_db_path: str):
        self.catalog_db_path = Path(catalog_db_path)
        self.scanner = VideoScanner()
        self.metadata_extractor = MetadataExtractor()
    
    async def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> 'ScanResult':
        """Scan directory for video files."""
        return await self.scanner.scan(directory, recursive)
    
    async def import_video(
        self,
        file_path: str,
        camera_id: Optional[str] = None,
        metadata_override: Optional[Dict] = None,
    ) -> str:
        """Import a video file into the catalog.
        
        Returns:
            video_id: UUID of imported video
        """
        # Check for duplicate
        checksum = await self._calculate_checksum(file_path)
        existing = await self._check_duplicate(checksum)
        
        if existing:
            return existing  # Return existing ID
        
        # Extract metadata
        metadata = await self.metadata_extractor.extract(file_path)
        metadata.checksum_sha256 = checksum
        
        # Create catalog entry
        video_id = await self._create_catalog_entry(
            metadata=metadata,
            camera_id=camera_id,
            override=metadata_override,
        )
        
        return video_id
    
    async def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum for deduplication."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    async def _check_duplicate(self, checksum: str) -> Optional[str]:
        """Check if video with same checksum exists."""
        # Query catalog database
        # Returns existing video_id if found
        pass
    
    async def _create_catalog_entry(
        self,
        metadata: VideoMetadata,
        camera_id: Optional[str],
        override: Optional[Dict],
    ) -> str:
        """Create new catalog entry."""
        import uuid
        video_id = str(uuid.uuid4())
        
        # Insert into PostgreSQL catalog
        # Implementation depends on database schema
        
        return video_id


class VideoScanner:
    """Discover video files in directories."""
    
    async def scan(
        self,
        directory: str,
        recursive: bool = True,
    ) -> 'ScanResult':
        """Scan directory for video files."""
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        found_files = []
        method = directory.rglob if recursive else directory.iterdir
        
        for path in method():
            if path.is_file() and path.suffix.lower() in HistoricalIngestor.SUPPORTED_EXTENSIONS:
                found_files.append(str(path.resolve()))
        
        return ScanResult(
            found=found_files,
            directory=str(directory),
            recursive=recursive,
            count=len(found_files),
        )


class MetadataExtractor:
    """Extract video metadata using ffprobe."""
    
    async def extract(self, file_path: str) -> VideoMetadata:
        """Extract all metadata from video file."""
        file_path = Path(file_path)
        
        # File stats
        file_size = file_path.stat().st_size
        
        # ffprobe metadata
        ffprobe_output = await self._run_ffprobe(str(file_path))
        stream_info = ffprobe_output['streams'][0]
        format_info = ffprobe_output['format']
        
        # Video stream info
        width = stream_info.get('width', 0)
        height = stream_info.get('height', 0)
        codec = stream_info.get('codec_name', 'unknown')
        
        # Frame rate (may be fraction)
        fps_str = stream_info.get('r_frame_rate', '0/1')
        fps_num, fps_den = map(int, fps_str.split('/'))
        fps = fps_num / fps_den if fps_den else 0
        
        # Duration
        duration = float(format_info.get('duration', 0))
        
        # Bitrate
        bitrate = format_info.get('bit_rate', '0')
        bitrate_kbps = int(bitrate) // 1000 if bitrate else 0
        
        # Creation date (from file mtime or metadata)
        creation_date = datetime.fromtimestamp(
            file_path.stat().st_mtime,
            tz=timezone.utc
        )
        
        return VideoMetadata(
            file_path=str(file_path),
            file_size_bytes=file_size,
            checksum_sha256='',  # Calculated separately
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            codec=codec,
            bitrate_kbps=bitrate_kbps,
            creation_date=creation_date,
        )
    
    async def _run_ffprobe(self, file_path: str) -> dict:
        """Run ffprobe and return JSON output."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, _ = await result.communicate()
        return json.loads(stdout)


@dataclass
class ScanResult:
    """Result of directory scan."""
    found: List[str]
    directory: str
    recursive: bool
    count: int
```

### 6.3 sources/video_catalog.py

```python
"""
Video Catalog - Sorting and Indexing

Responsibilities:
1. Store video metadata in PostgreSQL
2. Create ChromaDB embeddings for semantic search
3. Sort and filter by camera, date, weather, quality
4. Manage video processing queue

Key Classes:
- VideoCatalog: Database operations
- VideoSorter: Sorting and filtering logic
- ProcessingQueue: Job queue management
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
import asyncpg
import chromadb

class ProcessingStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class VideoRecord:
    """Complete video catalog record."""
    id: str
    source_type: str
    source_id: str
    source_url: str
    camera_id: Optional[str]
    camera_name: Optional[str]
    latitude: float
    longitude: float
    altitude: float
    azimuth: Optional[float]
    elevation: Optional[float]
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    quality_score: float
    resolution: str
    weather_condition: Optional[str]
    cloud_cover_pct: Optional[float]
    processing_status: ProcessingStatus
    file_path: str
    file_size_bytes: int
    checksum_sha256: str
    created_at: datetime
    updated_at: datetime

class VideoCatalog:
    """
    Video catalog database operations.
    
    Usage:
        catalog = VideoCatalog(db_url="postgresql://...")
        await catalog.initialize()
        
        # Add video
        await catalog.add_video(video_record)
        
        # Search
        videos = await catalog.search(
            camera_id="cam-001",
            date_from=datetime(2026, 4, 1),
            min_quality=0.7,
        )
    """
    
    def __init__(self, db_url: str, chroma_path: Optional[str] = None):
        self.db_url = db_url
        self.chroma_path = chroma_path
        self._conn: Optional[asyncpg.Connection] = None
        self._chroma_client: Optional[chromadb.Client] = None
        self._chroma_collection: Optional[chromadb.Collection] = None
    
    async def initialize(self) -> None:
        """Initialize database connections."""
        self._conn = await asyncpg.connect(self.db_url)
        
        # Initialize ChromaDB
        if self.chroma_path:
            self._chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="chemtrail_video_catalog",
                metadata={"hnsw:space": "cosine"},
            )
    
    async def add_video(self, video: VideoRecord) -> None:
        """Add video to catalog."""
        async with self._conn.transaction():
            await self._conn.execute("""
                INSERT INTO video_catalog (
                    id, source_type, source_id, source_url,
                    camera_id, camera_name, latitude, longitude, altitude,
                    azimuth, elevation, start_time, end_time, duration_seconds,
                    quality_score, resolution, weather_condition, cloud_cover_pct,
                    processing_status, file_path, file_size_bytes, checksum_sha256,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                        $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
                ON CONFLICT (checksum_sha256) DO NOTHING
            """, video.id, video.source_type, video.source_id, video.source_url,
                video.camera_id, video.camera_name, video.latitude, video.longitude,
                video.altitude, video.azimuth, video.elevation, video.start_time,
                video.end_time, video.duration_seconds, video.quality_score,
                video.resolution, video.weather_condition, video.cloud_cover_pct,
                video.processing_status.value, video.file_path, video.file_size_bytes,
                video.checksum_sha256, video.created_at, video.updated_at)
    
    async def search(
        self,
        camera_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_quality: Optional[float] = None,
        weather_condition: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[VideoRecord]:
        """Search catalog with filters."""
        query = "SELECT * FROM video_catalog WHERE 1=1"
        params = []
        param_count = 1
        
        if camera_id:
            query += f" AND camera_id = ${param_count}"
            params.append(camera_id)
            param_count += 1
        
        if date_from:
            query += f" AND start_time >= ${param_count}"
            params.append(date_from)
            param_count += 1
        
        if date_to:
            query += f" AND end_time <= ${param_count}"
            params.append(date_to)
            param_count += 1
        
        if min_quality:
            query += f" AND quality_score >= ${param_count}"
            params.append(min_quality)
            param_count += 1
        
        if weather_condition:
            query += f" AND weather_condition = ${param_count}"
            params.append(weather_condition)
            param_count += 1
        
        query += f" ORDER BY quality_score DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
        params.extend([limit, offset])
        
        rows = await self._conn.fetch(query, *params)
        return [self._row_to_record(row) for row in rows]
    
    async def get_pending_processing(self, limit: int = 100) -> List[VideoRecord]:
        """Get videos pending processing."""
        rows = await self._conn.fetch("""
            SELECT * FROM video_catalog
            WHERE processing_status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
        """, limit)
        return [self._row_to_record(row) for row in rows]
    
    async def update_processing_status(
        self,
        video_id: str,
        status: ProcessingStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update video processing status."""
        await self._conn.execute("""
            UPDATE video_catalog
            SET processing_status = $2,
                updated_at = NOW()
            WHERE id = $1
        """, video_id, status.value)
    
    def _row_to_record(self, row) -> VideoRecord:
        """Convert database row to VideoRecord."""
        return VideoRecord(
            id=row['id'],
            source_type=row['source_type'],
            source_id=row['source_id'],
            source_url=row['source_url'],
            camera_id=row['camera_id'],
            camera_name=row['camera_name'],
            latitude=row['latitude'],
            longitude=row['longitude'],
            altitude=row['altitude'],
            azimuth=row.get('azimuth'),
            elevation=row.get('elevation'),
            start_time=row['start_time'],
            end_time=row['end_time'],
            duration_seconds=row['duration_seconds'],
            quality_score=row['quality_score'],
            resolution=row['resolution'],
            weather_condition=row.get('weather_condition'),
            cloud_cover_pct=row.get('cloud_cover_pct'),
            processing_status=ProcessingStatus(row['processing_status']),
            file_path=row['file_path'],
            file_size_bytes=row['file_size_bytes'],
            checksum_sha256=row['checksum_sha256'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
```

### 6.4 sources/pipeline_orchestrator.py

```python
"""
Pipeline Orchestrator - End-to-End Workflow Coordination

Responsibilities:
1. Coordinate acquisition → sorting → detection → archive pipeline
2. Manage processing queues and priorities
3. Handle errors and retries
4. Track progress and generate reports

Key Classes:
- PipelineOrchestrator: Main coordinator
- WorkflowEngine: Pipeline stage execution
- ProgressTracker: Status reporting
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)

class PipelineStage(Enum):
    ACQUISITION = "acquisition"
    SORTING = "sorting"
    WEATHER_ENRICHMENT = "weather_enrichment"
    QUALITY_SCORING = "quality_scoring"
    CHUNKING = "chunking"
    DETECTION = "detection"
    ARCHIVAL = "archival"
    COMPLETE = "complete"

class PipelineStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

@dataclass
class PipelineJob:
    """Represents a video processing job."""
    job_id: str
    video_id: str
    source_path: str
    current_stage: PipelineStage
    status: PipelineStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    stage_results: Dict[str, dict] = field(default_factory=dict)

@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    max_concurrent_jobs: int = 5
    stage_timeout_seconds: Dict[PipelineStage, int] = field(default_factory=lambda: {
        PipelineStage.ACQUISITION: 300,
        PipelineStage.SORTING: 60,
        PipelineStage.WEATHER_ENRICHMENT: 120,
        PipelineStage.QUALITY_SCORING: 120,
        PipelineStage.CHUNKING: 600,
        PipelineStage.DETECTION: 1800,
        PipelineStage.ARCHIVAL: 300,
    })
    enable_weather_enrichment: bool = True
    enable_quality_scoring: bool = True
    skip_still_frames: bool = True
    apply_overlay: bool = False

class PipelineOrchestrator:
    """
    Orchestrates end-to-end video processing pipeline.
    
    Usage:
        orchestrator = PipelineOrchestrator(config)
        await orchestrator.start()
        
        # Submit job
        job_id = await orchestrator.submit_job(video_path, camera_id)
        
        # Check status
        status = await orchestrator.get_job_status(job_id)
        
        # Wait for completion
        await orchestrator.wait_for_job(job_id)
    """
    
    def __init__(
        self,
        config: PipelineConfig,
        video_catalog: 'VideoCatalog',
        webcam_manager: 'WebcamManager',
        detection_service: 'DetectionService',
        weather_service: 'WeatherEnrichmentService',
    ):
        self.config = config
        self.video_catalog = video_catalog
        self.webcam_manager = webcam_manager
        self.detection_service = detection_service
        self.weather_service = weather_service
        
        self._jobs: Dict[str, PipelineJob] = {}
        self._job_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._workers: List[asyncio.Task] = []
    
    async def start(self) -> None:
        """Start pipeline processing."""
        self._running = True
        
        # Start worker tasks
        for i in range(self.config.max_concurrent_jobs):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        logger.info(f"Pipeline started with {self.config.max_concurrent_jobs} workers")
    
    async def stop(self) -> None:
        """Stop pipeline processing."""
        self._running = False
        
        # Wait for workers to finish
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
    
    async def submit_job(
        self,
        source_path: str,
        camera_id: Optional[str] = None,
        priority: int = 0,
    ) -> str:
        """Submit a new processing job."""
        import uuid
        job_id = str(uuid.uuid4())
        
        job = PipelineJob(
            job_id=job_id,
            video_id='',  # Assigned during processing
            source_path=source_path,
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
        )
        
        self._jobs[job_id] = job
        await self._job_queue.put((priority, job_id))
        
        return job_id
    
    async def get_job_status(self, job_id: str) -> PipelineJob:
        """Get current job status."""
        return self._jobs.get(job_id)
    
    async def wait_for_job(
        self,
        job_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> PipelineJob:
        """Wait for job completion."""
        start_time = datetime.now(timezone.utc)
        
        while True:
            job = self._jobs[job_id]
            
            if job.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED):
                return job
            
            if timeout_seconds:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    raise TimeoutError(f"Job {job_id} timed out")
            
            await asyncio.sleep(1)
    
    async def _worker(self, worker_id: int) -> None:
        """Worker task that processes jobs from queue."""
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Get job from queue
                priority, job_id = await self._job_queue.get()
                job = self._jobs[job_id]
                
                # Process job through all stages
                job.status = PipelineStatus.RUNNING
                job.started_at = datetime.now(timezone.utc)
                
                await self._process_job(job)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
    
    async def _process_job(self, job: PipelineJob) -> None:
        """Process job through all pipeline stages."""
        stages = [
            PipelineStage.ACQUISITION,
            PipelineStage.SORTING,
            PipelineStage.WEATHER_ENRICHMENT,
            PipelineStage.QUALITY_SCORING,
            PipelineStage.CHUNKING,
            PipelineStage.DETECTION,
            PipelineStage.ARCHIVAL,
        ]
        
        for stage in stages:
            job.current_stage = stage
            
            try:
                timeout = self.config.stage_timeout_seconds.get(stage, 300)
                await asyncio.wait_for(
                    self._execute_stage(job, stage),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                job.error_message = f"Stage {stage.value} timed out"
                job.status = PipelineStatus.FAILED
                return
            except Exception as e:
                logger.error(f"Stage {stage.value} failed: {e}")
                
                # Retry logic
                job.retry_count += 1
                if job.retry_count < job.max_retries:
                    logger.info(f"Retrying stage {stage.value} ({job.retry_count}/{job.max_retries})")
                    job.current_stage = stage
                    continue
                else:
                    job.error_message = str(e)
                    job.status = PipelineStatus.FAILED
                    return
        
        # All stages complete
        job.status = PipelineStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        logger.info(f"Job {job.job_id} completed successfully")
    
    async def _execute_stage(
        self,
        job: PipelineJob,
        stage: PipelineStage,
    ) -> None:
        """Execute a single pipeline stage."""
        if stage == PipelineStage.ACQUISITION:
            # Import video into catalog
            video_id = await self.video_catalog.import_video(job.source_path)
            job.video_id = video_id
        
        elif stage == PipelineStage.SORTING:
            # Sort and categorize video
            # (Already done during import)
            pass
        
        elif stage == PipelineStage.WEATHER_ENRICHMENT:
            if self.config.enable_weather_enrichment:
                # Fetch weather data and update catalog
                video = await self.video_catalog.get_by_id(job.video_id)
                weather = await self.weather_service.get_weather_for_video(
                    latitude=video.latitude,
                    longitude=video.longitude,
                    video_start=video.start_time,
                    video_end=video.end_time,
                )
                await self.video_catalog.update_weather(job.video_id, weather)
        
        elif stage == PipelineStage.QUALITY_SCORING:
            if self.config.enable_quality_scoring:
                # Calculate quality score
                quality = calculate_quality_score(job.source_path)
                await self.video_catalog.update_quality(job.video_id, quality['overall_score'])
        
        elif stage == PipelineStage.CHUNKING:
            # Chunk video for processing
            from chemtrail.archive.chunker import chunk_video
            chunks = chunk_video(job.source_path, chunk_duration=30, overlap=5)
            job.stage_results['chunks'] = chunks
        
        elif stage == PipelineStage.DETECTION:
            # Run detection pipeline
            video = await self.video_catalog.get_by_id(job.video_id)
            camera_metadata = await self.video_catalog.get_camera_metadata(video.camera_id)
            
            results = await self.detection_service.process_detection_batch(
                chunks=job.stage_results['chunks'],
                camera_id=video.camera_id,
                camera_metadata=camera_metadata,
                skip_still_frames=self.config.skip_still_frames,
                apply_overlay=self.config.apply_overlay,
            )
            job.stage_results['detections'] = results
        
        elif stage == PipelineStage.ARCHIVAL:
            # Detections already archived by detection_service
            # Update job with final status
            detection_count = len(job.stage_results.get('detections', []))
            logger.info(f"Archived {detection_count} detections for job {job.job_id}")
```

---

## 7. Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2 COMPLETE DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        SOURCES                                            │   │
│  │                                                                          │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │   │
│  │  │   WEBCAM    │    │  HISTORICAL │    │   YOUTUBE   │                  │   │
│  │  │   STREAMS   │    │    FILES    │    │   ARCHIVE   │                  │   │
│  │  │             │    │             │    │             │                  │   │
│  │  │  • RTSP     │    │  • Scan     │    │  • Download │                  │   │
│  │  │  • MJPEG    │    │  • Metadata │    │  • Metadata │                  │   │
│  │  │  • HLS      │    │  • Checksum │    │  • Import   │                  │   │
│  │  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                  │   │
│  │         │                  │                  │                          │   │
│  │         └──────────────────┴──────────────────┘                          │   │
│  │                            │                                             │   │
│  │                            ▼                                             │   │
│  │               ┌─────────────────────────┐                                │   │
│  │               │    VIDEO CATALOG        │                                │   │
│  │               │    (PostgreSQL)         │                                │   │
│  │               │                         │                                │   │
│  │               │  - Metadata             │                                │   │
│  │               │  - Location             │                                │   │
│  │               │  - Quality Score        │                                │   │
│  │               │  - Processing Status    │                                │   │
│  │               └────────────┬────────────┘                                │   │
│  │                            │                                             │   │
│  │                            ▼                                             │   │
│  │               ┌─────────────────────────┐                                │   │
│  │               │   WEATHER ENRICHMENT    │                                │   │
│  │               │   (Open-Meteo API)      │                                │   │
│  │               │                         │                                │   │
│  │               │  - Condition            │                                │   │
│  │               │  - Cloud Cover          │                                │   │
│  │               │  - Visibility           │                                │   │
│  │               └────────────┬────────────┘                                │   │
│  │                            │                                             │   │
│  └────────────────────────────┼─────────────────────────────────────────────┘   │
│                               │                                                  │
│                               ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    PIPELINE ORCHESTRATOR                                  │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │  Processing Queue (Redis)                                        │    │   │
│  │  │                                                                  │    │   │
│  │  │  Job 1: [acquisition] → [sorting] → [weather] → [quality] →     │    │   │
│  │  │         [chunking] → [detection] → [archival] → COMPLETE        │    │   │
│  │  │                                                                  │    │   │
│  │  │  Job 2: [acquisition] → [sorting] → ...                         │    │   │
│  │  │  Job 3: [detection] → [archival] → ...                          │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  Features:                                                               │   │
│  │  - Concurrent job execution (configurable workers)                      │   │
│  │  - Stage timeout handling                                               │   │
│  │  - Retry logic with exponential backoff                                 │   │
│  │  - Progress tracking and reporting                                      │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                               │                                                  │
│                               ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    EXISTING DETECTION PIPELINE (Phase 1.5)                │   │
│  │                                                                          │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │   │
│  │  │   CHUNKER   │───▶│     CV      │───▶│   FLIGHT    │                  │   │
│  │  │             │    │  DETECTION  │    │  CORRELATE  │                  │   │
│  │  │  • Segments │    │  • Hough    │    │  • ICAO24   │                  │   │
│  │  │  • Still-skip│   │  • YOLOv8   │    │  • Position │                  │   │
│  │  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                  │   │
│  │         │                  │                  │                          │   │
│  │         │                  │                  │                          │   │
│  │         │                  ▼                  │                          │   │
│  │         │         ┌─────────────┐            │                          │   │
│  │         │         │    GEO      │◀───────────┘                          │   │
│  │         │         │  LOCALIZE   │                                     │   │
│  │         │         └──────┬──────┘                                     │   │
│  │         │                │                                            │   │
│  │         └────────────────┼────────────────────────────────┐           │   │
│  │                          │                                │           │   │
│  │                          ▼                                │           │   │
│  │               ┌─────────────────────┐                    │           │   │
│  │               │   VECTOR STORE      │                    │           │   │
│  │               │   (ChromaDB)        │                    │           │   │
│  │               │                     │                    │           │   │
│  │               │  - Embeddings       │◀───────────────────┘           │   │
│  │               │  - Metadata         │                                │   │
│  │               │  - Search Index     │                                │   │
│  │               └──────────┬──────────┘                                │   │
│  │                          │                                           │   │
│  └──────────────────────────┼───────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    SEARCH & VISUALIZATION                             │   │
│  │                                                                      │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │   │
│  │  │   SEMANTIC  │    │  METADATA   │    │  DETECTION  │              │   │
│  │  │   SEARCH    │    │   FILTERS   │    │   BROWSER   │              │   │
│  │  │             │    │             │    │             │              │   │
│  │  │  "contrails │    │  - Camera   │    │  - Timeline │              │   │
│  │  │  over       │    │  - Date     │    │  - Map View │              │   │
│  │  │  downtown"  │    │  - Weather  │    │  - Stats    │              │   │
│  │  └─────────────┘    │  - Quality  │    └─────────────┘              │   │
│  │                     └─────────────┘                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  DATA STORAGE LAYER                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  PostgreSQL │  │   Redis     │  │  ChromaDB   │  │   File      │        │
│  │  - Catalog  │  │  - Queue    │  │  - Archive  │  │  - Videos   │        │
│  │  - Metadata │  │  - Cache    │  │  - Vectors  │  │  - Chunks   │        │
│  │  - Flight   │  │             │  │  + FR24     │  │             │        │
│  │    Cache    │  │             │  │  metadata   │  │             │        │
│  │  +13 FR24   │  │             │  │             │  │             │        │
│  │  fields     │  │             │  │             │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Dependencies

### 8.1 New Python Packages

```python
# requirements-phase2.txt

# Video source ingestion
yt-dlp>=2024.1.0          # YouTube download

# Weather API
openmeteo-requests>=1.1.0  # Open-Meteo API client

# Async HTTP client (already in requirements.txt)
# httpx>=0.28.0           # Already present

# Video processing (already in requirements.txt)
# imageio-ffmpeg>=0.4.0   # Already present

# Database (already in requirements.txt)
# asyncpg>=0.29.0         # Already present
# chromadb>=0.5.0         # Already present
```

### 8.2 System Dependencies

```bash
# ffmpeg and ffprobe (already required for Phase 1.5)
# apt install ffmpeg        # Linux
# brew install ffmpeg       # macOS
# choco install ffmpeg      # Windows (via Chocolatey)
```

---

## 9. Database Schema Extensions

### 9.1 Video Catalog Table

```sql
-- Video catalog for Phase 2
CREATE TABLE IF NOT EXISTS video_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_type VARCHAR(50) NOT NULL,  -- 'live_webcam', 'historical_file', 'youtube'
    source_id VARCHAR(255) NOT NULL,   -- Camera ID or file path
    source_url TEXT,
    
    -- Location
    camera_id UUID REFERENCES chemtrail_cameras(id),
    camera_name VARCHAR(255),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION NOT NULL,
    azimuth DOUBLE PRECISION,
    elevation DOUBLE PRECISION,
    
    -- Temporal
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL,
    
    -- Quality scoring
    quality_score DOUBLE PRECISION DEFAULT 0.0,
    resolution VARCHAR(20),
    stability_score DOUBLE PRECISION,
    lighting_score DOUBLE PRECISION,
    sharpness_score DOUBLE PRECISION,
    
    -- Weather enrichment
    weather_condition VARCHAR(50),
    cloud_cover_pct DOUBLE PRECISION,
    visibility_km DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    
    -- Content analysis
    sky_coverage_pct DOUBLE PRECISION,
    has_contrails BOOLEAN DEFAULT FALSE,
    
    -- Processing status
    processing_status VARCHAR(20) DEFAULT 'pending',
    chunk_count INTEGER DEFAULT 0,
    detection_count INTEGER DEFAULT 0,
    error_message TEXT,
    
    -- Storage
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT,
    checksum_sha256 VARCHAR(64) UNIQUE,
    thumbnail_path TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT valid_processing_status CHECK (
        processing_status IN ('pending', 'queued', 'processing', 'completed', 'failed')
    )
);

CREATE INDEX idx_video_catalog_camera ON video_catalog(camera_id);
CREATE INDEX idx_video_catalog_time ON video_catalog(start_time, end_time);
CREATE INDEX idx_video_catalog_quality ON video_catalog(quality_score DESC);
CREATE INDEX idx_video_catalog_weather ON video_catalog(weather_condition);
CREATE INDEX idx_video_catalog_status ON video_catalog(processing_status);
CREATE INDEX idx_video_catalog_location ON video_catalog(latitude, longitude);
```

---

## 10. Summary

Phase 2 delivers a complete end-to-end footage management system that:

1. **Acquires footage** from live webcams, historical files, and YouTube archives
2. **Sorts and catalogs** videos by camera, date, weather, and quality
3. **Orchestrates processing** through acquisition → detection → archive pipeline
4. **Enables semantic search** over both video catalog and detection archive

The architecture maintains backward compatibility with Phase 1.5 while extending capabilities for comprehensive footage management.

---

*Document prepared by Dr. Sarah Kim, Technical Product Strategist & Engineering Lead*
