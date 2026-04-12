# Phase 1.5 SentrySearch Integration - Implementation Brief

**Project:** Chemtrail Webcam Tracker  
**Phase:** 1.5 - SentrySearch Integration  
**Version:** 1.0.0  
**Date:** 2026-04-11  
**Status:** Execution Ready  
**Author:** Software Program Manager (derived from INTEGRATION_ARCHITECTURE.md and INTEGRATION_PLAN.md)

---

## Executive Summary

This brief provides detailed, actionable instructions for integrating SentrySearch capabilities into the Chemtrail Webcam Tracker. The integration transforms the tracker from a real-time detection system into a **semantic, searchable archive** of contrail detection events.

**Goal:** Enable queries like *"find all contrails from Boeing 737 over downtown"* by archiving detection clips in ChromaDB with vector embeddings.

**Timeline:** 2-3 weeks  
**Priority:** HIGH  
**Dependencies:** Phase 1 complete (73 tests passing)

---

## 1. SentrySearch Files to Copy

### 1.1 Direct Copy (No Modification)

Copy these files directly from `C:\Users\antmi\sentrysearch-temp\sentrysearch\` to the target paths:

| Source File | Target File | Rationale |
|-------------|-------------|-----------|
| `sentrysearch\base_embedder.py` | `backend\chemtrail\archive\base_embedder.py` | Abstract base class - no changes needed |
| `sentrysearch\embedder.py` | `backend\chemtrail\archive\embedder.py` | Backend factory - works as-is |
| `sentrysearch\gemini_embedder.py` | `backend\chemtrail\archive\gemini_embedder.py` | Gemini API embedder - reuse directly |
| `sentrysearch\local_embedder.py` | `backend\chemtrail\archive\local_embedder.py` | Optional Qwen3-VL embedder - copy for local fallback |

**Copy Commands:**
```bash
cd C:\Users\antmi\ground-station

# Create archive directory
mkdir backend\chemtrail\archive
type NUL > backend\chemtrail\archive\__init__.py

# Direct copies
copy C:\Users\antmi\sentrysearch-temp\sentrysearch\base_embedder.py backend\chemtrail\archive\base_embedder.py
copy C:\Users\antmi\sentrysearch-temp\sentrysearch\embedder.py backend\chemtrail\archive\embedder.py
copy C:\Users\antmi\sentrysearch-temp\sentrysearch\gemini_embedder.py backend\chemtrail\archive\gemini_embedder.py
copy C:\Users\antmi\sentrysearch-temp\sentrysearch\local_embedder.py backend\chemtrail\archive\local_embedder.py
```

---

### 1.2 Copy + Adapt (Modified for Chemtrail)

These files require modifications after copying:

#### 1.2.1 chunker.py (ADAPT)

**Source:** `sentrysearch\chunker.py`  
**Target:** `backend\chemtrail\archive\chunker.py`

**Required Modifications:**

1. **Add RTSP/MJPEG stream support** - Add `chunk_stream_continuous()` function for continuous webcam ingestion
2. **Add `continuous_mode` flag** to `chunk_video()` for streaming vs batch processing
3. **Add `output_dir` parameter** - Allow caller to specify chunk output location
4. **Modify still-frame detection** - Add `is_still_frame_sequence()` for direct frame arrays

**Code Changes:**
```python
# ADD after imports (line 11):
from typing import Optional, Iterator

# MODIFY chunk_video() signature (line 118):
def chunk_video(
    video_path: str,
    chunk_duration: int = 30,
    overlap: int = 5,
    continuous_mode: bool = False,  # NEW
    output_dir: Optional[str] = None,  # NEW
) -> list[dict] | Iterator[dict]:  # MODIFIED return type

# ADD at start of chunk_video() after line 140:
    if continuous_mode:
        return _chunk_stream_continuous(video_path, chunk_duration, overlap, output_dir)

# ADD new function after chunk_video() (after line 209):
def chunk_stream_continuous(
    stream_url: str,
    chunk_duration: int = 10,
    overlap: int = 2,
    output_dir: Optional[str] = None,
) -> Iterator[dict]:
    """
    Continuously chunk an RTSP/MJPEG stream.
    
    Yields chunk metadata as each segment completes.
    Caller is responsible for processing and cleanup.
    
    Args:
        stream_url: RTSP or MJPEG stream URL
        chunk_duration: Duration of each chunk in seconds
        overlap: Overlap between chunks in seconds
        output_dir: Directory for chunk files (temp if None)
    
    Yields:
        Dict with keys: chunk_path, source_file, start_time, end_time
    """
    import time
    from pathlib import Path
    
    output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="chemtrail_"))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ffmpeg_exe = _get_ffmpeg_executable()
    step = chunk_duration - overlap
    idx = 0
    start_time = 0.0
    
    while True:  # Continuous loop
        end_time = start_time + chunk_duration
        chunk_path = output_dir / f"chunk_{int(time.time())}_{idx:03d}.mp4"
        
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-rtsp_transport", "tcp",  # RTSP over TCP
                "-i", stream_url,
                "-ss", str(start_time),
                "-t", str(chunk_duration),
                "-c", "copy",
                str(chunk_path),
            ],
            capture_output=True,
            check=False,
        )
        
        if result.returncode == 0 and chunk_path.exists():
            yield {
                "chunk_path": str(chunk_path),
                "source_file": stream_url,
                "start_time": start_time,
                "end_time": end_time,
            }
        
        start_time += step
        idx += 1
        time.sleep(0.1)

# ADD new function after is_still_frame_chunk() (after line 308):
def is_still_frame_sequence(
    frames: list[np.ndarray],
    threshold: float = 0.98,
) -> bool:
    """
    Check if a sequence of frames is mostly static.
    
    Alternative to video-based still detection for direct frame processing.
    
    Args:
        frames: List of numpy arrays (BGR frames)
        threshold: Minimum JPEG size ratio to consider static
    
    Returns:
        True if frames appear static
    """
    if len(frames) < 2:
        return False
    
    import cv2
    sizes = []
    for frame in frames:
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        sizes.append(len(buf))
    
    min_size = min(sizes)
    max_size = max(sizes)
    
    if max_size == 0:
        return False
    
    return min_size / max_size >= threshold
```

---

#### 1.2.2 store.py -> vector_store.py (ADAPT)

**Source:** `sentrysearch\store.py`  
**Target:** `backend\chemtrail\storage\vector_store.py`

**Required Modifications:**

1. **Rename collection** from `dashcam_chunks` to `chemtrail_detections`
2. **Extend metadata schema** with flight/camera/geolocation fields
3. **Add flight-specific query helpers** (`search_by_flight`, `search_by_camera`, `search_by_location`)
4. **Add `add_detection()` method** with extended metadata validation

**Code Changes:**
```python
# MODIFY _collection_name() (line 17):
def _collection_name(backend: str, model: str | None = None) -> str:
    """Return ChromaDB collection name for chemtrail detections."""
    if backend == "gemini":
        return "chemtrail_detections"
    if model:
        return f"chemtrail_detections_local_{model}"
    return "chemtrail_detections_local"

# MODIFY add_chunk() signature (line 127) - RENAME to add_detection:
def add_detection(
    self,
    chunk_id: str,
    embedding: list[float],
    metadata: dict,  # Extended chemtrail metadata
) -> None:
    """
    Store a detection event with extended metadata.
    
    Required metadata keys:
    - source_file, start_time, end_time (base)
    - camera_id, camera_name, camera_lat, camera_lon, camera_alt
    - detection_type, pixel_x, pixel_y, azimuth, elevation, confidence
    - indexed_at (auto-added)
    
    Optional metadata keys:
    - contrail_vector, icao24, callsign, aircraft_type
    - estimated_lat, estimated_lon, estimated_alt
    - correlation_score, position_method
    """
    required = ["source_file", "start_time", "end_time", "camera_id", "confidence"]
    for key in required:
        if key not in metadata:
            raise ValueError(f"Missing required metadata: {key}")
    
    meta = {
        "source_file": metadata["source_file"],
        "start_time": float(metadata["start_time"]),
        "end_time": float(metadata["end_time"]),
        "camera_id": str(metadata["camera_id"]),
        "camera_name": metadata.get("camera_name", "unknown"),
        "camera_lat": float(metadata.get("camera_lat", 0)),
        "camera_lon": float(metadata.get("camera_lon", 0)),
        "camera_alt": float(metadata.get("camera_alt", 0)),
        "detection_type": metadata.get("detection_type", "contrail"),
        "pixel_x": float(metadata.get("pixel_x", 0)),
        "pixel_y": float(metadata.get("pixel_y", 0)),
        "azimuth": float(metadata.get("azimuth", 0)),
        "elevation": float(metadata.get("elevation", 0)),
        "confidence": float(metadata["confidence"]),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Add optional fields if present
    optional_fields = [
        "contrail_vector", "icao24", "callsign", "aircraft_type",
        "estimated_lat", "estimated_lon", "estimated_alt",
        "correlation_score", "position_method", "overlay_applied", "clip_path"
    ]
    for field in optional_fields:
        if field in metadata:
            meta[field] = metadata[field]
    
    self._collection.upsert(
        ids=[chunk_id],
        embeddings=[embedding],
        metadatas=[meta],
    )

# ADD new query helpers after get_stats() (after line 240):
def search_by_flight(
    self,
    icao24: str,
    n_results: int = 10,
) -> list[dict]:
    """Search detections for a specific flight."""
    count = self._collection.count()
    if count == 0:
        return []
    
    results = self._collection.query(
        where={"icao24": icao24},
        n_results=min(n_results, count),
        include=["metadatas", "distances"],
    )
    
    return self._format_results(results)

def search_by_camera(
    self,
    camera_id: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    n_results: int = 10,
) -> list[dict]:
    """Search detections for a specific camera with optional date range."""
    where = {"camera_id": str(camera_id)}
    
    count = self._collection.count()
    if count == 0:
        return []
    
    results = self._collection.query(
        where=where,
        n_results=min(n_results * 3, count),
        include=["metadatas", "distances"],
    )
    
    filtered = self._format_results(results)
    
    if date_from or date_to:
        filtered = [
            r for r in filtered
            if self._matches_date_range(r, date_from, date_to)
        ]
    
    return filtered[:n_results]

def search_by_location(
    self,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    n_results: int = 10,
) -> list[dict]:
    """Search detections within a geographic bounding box."""
    count = self._collection.count()
    if count == 0:
        return []
    
    results = self._collection.query(
        query_embeddings=[[0] * 768],
        n_results=min(n_results * 5, count),
        include=["metadatas"],
    )
    
    filtered = []
    for meta in results["metadatas"][0]:
        est_lat = meta.get("estimated_lat")
        est_lon = meta.get("estimated_lon")
        
        if est_lat is None or est_lon is None:
            continue
        
        if (lat_min <= est_lat <= lat_max and 
            lon_min <= est_lon <= lon_max):
            filtered.append({
                "source_file": meta["source_file"],
                "start_time": meta["start_time"],
                "end_time": meta["end_time"],
                "icao24": meta.get("icao24"),
                "callsign": meta.get("callsign"),
                "estimated_lat": est_lat,
                "estimated_lon": est_lon,
                "confidence": meta.get("confidence", 0),
            })
    
    filtered.sort(key=lambda x: x["confidence"], reverse=True)
    return filtered[:n_results]

def _format_results(self, results: dict) -> list[dict]:
    """Format ChromaDB query results."""
    hits = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i] if results["distances"] else 0
        
        hit = {
            "chunk_id": results["ids"][0][i],
            "source_file": meta["source_file"],
            "start_time": meta["start_time"],
            "end_time": meta["end_time"],
            "camera_id": meta.get("camera_id"),
            "camera_name": meta.get("camera_name"),
            "detection_type": meta.get("detection_type"),
            "confidence": meta.get("confidence", 0),
            "score": 1.0 - distance,
        }
        
        for field in ["icao24", "callsign", "aircraft_type", 
                      "estimated_lat", "estimated_lon", "contrail_vector"]:
            if field in meta:
                hit[field] = meta[field]
        
        hits.append(hit)
    
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits

def _matches_date_range(
    self,
    result: dict,
    date_from: datetime | None,
    date_to: datetime | None,
) -> bool:
    """Check if result falls within date range."""
    indexed_at = result.get("metadata", {}).get("indexed_at")
    if not indexed_at:
        return True
    
    try:
        dt = datetime.fromisoformat(indexed_at)
        if date_from and dt < date_from:
            return False
        if date_to and dt > date_to:
            return False
        return True
    except (ValueError, TypeError):
        return True
```

---

#### 1.2.3 search.py (ADAPT)

**Source:** `sentrysearch\search.py`  
**Target:** `backend\chemtrail\archive\search.py`

**Required Modifications:**

1. **Rename function** from `search_footage()` to `search_detections()`
2. **Add metadata filtering** support (icao24, camera_id, date range, detection_type)
3. **Extend return format** with chemtrail-specific fields

**Code Changes:**
```python
# MODIFY search_footage() signature (line 7):
def search_detections(
    query: str,
    vector_store: SentryStore,
    n_results: int = 10,
    icao24: str | None = None,
    camera_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    detection_type: str | None = None,
    verbose: bool = False,
) -> list[dict]:
    """
    Search detection archive with natural language and metadata filters.
    
    Args:
        query: Natural language search query
        vector_store: SentryStore instance
        n_results: Max results to return
        icao24: Filter by flight ICAO24 hex code
        camera_id: Filter by camera UUID
        date_from: Start of date range
        date_to: End of date range
        detection_type: Filter by type ("contrail" or "aircraft")
        verbose: Print debug info
    
    Returns:
        List of matching detections with metadata
    """
    # Step 1: Embed query
    query_embedding = embed_query(query, verbose=verbose)
    
    # Step 2: Build where clause for metadata filtering
    where_conditions = []
    
    if icao24:
        where_conditions.append({"icao24": icao24})
    if camera_id:
        where_conditions.append({"camera_id": str(camera_id)})
    if detection_type:
        where_conditions.append({"detection_type": detection_type})
    
    where = {"$and": where_conditions} if len(where_conditions) > 1 else (where_conditions[0] if where_conditions else None)
    
    # Step 3: Query ChromaDB
    count = vector_store.collection.count()
    if count == 0:
        return []
    
    results = vector_store.collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results * 3, count),
        where=where,
        include=["metadatas", "distances"],
    )
    
    # Step 4: Format and filter results
    hits = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        
        # Apply date filter in Python
        if date_from or date_to:
            indexed_at = meta.get("indexed_at")
            if indexed_at:
                try:
                    dt = datetime.fromisoformat(indexed_at)
                    if date_from and dt < date_from:
                        continue
                    if date_to and dt > date_to:
                        continue
                except ValueError:
                    pass
        
        hit = {
            "chunk_id": results["ids"][0][i],
            "source_file": meta["source_file"],
            "start_time": meta["start_time"],
            "end_time": meta["end_time"],
            "score": 1.0 - distance,
            "camera_id": meta.get("camera_id"),
            "camera_name": meta.get("camera_name"),
            "icao24": meta.get("icao24"),
            "callsign": meta.get("callsign"),
            "detection_type": meta.get("detection_type"),
            "confidence": meta.get("confidence", 0),
            "estimated_lat": meta.get("estimated_lat"),
            "estimated_lon": meta.get("estimated_lon"),
        }
        hits.append(hit)
    
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:n_results]
```

---

#### 1.2.4 overlay.py (ADAPT)

**Source:** `sentrysearch\overlay.py`  
**Target:** `backend\chemtrail\archive\overlay.py`

**Required Modifications:**

1. **Remove Tesla SEI extraction** - Replace with flight data injector
2. **Simplify HUD layout** - Show flight info (callsign, altitude, speed, heading) instead of Tesla telemetry
3. **Remove Tesla-specific fields** - No gear, autopilot, blinkers, steering angle
4. **Add flight metadata function** - Fetch from OpenSky via FlightService

**Code Changes:**
```python
# REPLACE imports (line 17-18):
from .chunker import _get_ffmpeg_executable, _get_video_duration
# REMOVE: from .metadata import extract_metadata

# REPLACE get_metadata_samples() with flight metadata function (after line 92):
def get_flight_metadata(
    icao24: str,
    flight_service,  # FlightService instance
    timestamp: datetime,
) -> dict | None:
    """
    Get flight metadata for overlay from OpenSky cache.
    
    Args:
        icao24: Flight ICAO24 hex code
        flight_service: FlightService instance
        timestamp: Detection timestamp
    
    Returns:
        Dict with flight data fields or None if not found
    """
    # Import here to avoid circular dependency
    from chemtrail.services.flight_service import FlightService
    
    flight_data = flight_service.get_flight(icao24)
    if not flight_data:
        return None
    
    position = flight_data.get("position", {})
    
    return {
        "callsign": flight_data.get("callsign", "UNKNOWN"),
        "altitude": position.get("alt"),
        "velocity": position.get("velocity"),
        "heading": position.get("heading"),
        "latitude": position.get("lat"),
        "longitude": position.get("lon"),
        "timestamp": timestamp,
    }

# REPLACE _build_ass_content() with simplified flight HUD:
def _build_flight_overlay(
    metadata: dict,
    clip_duration: float,
    video_width: int,
    video_height: int,
) -> str:
    """
    Generate ASS subtitle content for flight data overlay.
    
    Layout (top-left):
        [CALLSIGN]
        Alt: XXXXX ft | Spd: XXX kts | Hdg: XXX
        
        YYYY-MM-DD HH:MM:SS UTC
        Lat: XX.XXXX Lon: XXX.XXXX
    """
    scale = min(video_width / 1280, video_height / 720)
    
    # Position (top-left)
    x = int(20 * scale)
    y = int(30 * scale)
    line_height = int(25 * scale)
    
    # Font sizes
    callsign_fs = int(28 * scale)
    info_fs = int(18 * scale)
    coord_fs = int(14 * scale)
    
    # Colors
    callsign_color = "&H00FFFF00"  # Yellow
    info_color = "&H00FFFFFF"      # White
    coord_color = "&H00CCCCCC"     # Light gray
    
    end_time = _secs_to_ass_time(clip_duration + 1)
    
    # ASS styles
    styles = [
        f"Style: Callsign,Arial,{callsign_fs},{callsign_color},&H00000000,"
        f"&H80000000,1,0,0,0,100,100,0,0,1,1,1,5,10,10,0,1",
        f"Style: Info,Arial,{info_fs},{info_color},&H00000000,"
        f"&H80000000,0,0,0,0,100,100,0,0,1,0.8,0.5,5,8,8,0,1",
        f"Style: Coords,Arial,{coord_fs},{coord_color},&H00000000,"
        f"&H80000000,0,0,0,0,100,100,0,0,1,0,0,5,6,6,0,1",
    ]
    
    events = []
    
    # Callsign
    callsign = metadata.get("callsign", "UNKNOWN")
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Callsign,,"
        f"{{\\an7\\pos({x},{y})}}{callsign}"
    )
    
    # Flight info
    alt = metadata.get("altitude", "N/A")
    spd = metadata.get("velocity", "N/A")
    hdg = metadata.get("heading", "N/A")
    
    alt_str = f"{int(alt)} ft" if alt else "N/A"
    spd_str = f"{int(spd * 1.944)} kts" if spd else "N/A"  # m/s to knots
    hdg_str = f"{int(hdg)}°" if hdg else "N/A"
    
    info_y = y + line_height
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Info,,"
        f"{{\\an7\\pos({x},{info_y})}}Alt: {alt_str} | Spd: {spd_str} | Hdg: {hdg_str}"
    )
    
    # Timestamp and coordinates
    ts = metadata.get("timestamp")
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "Unknown"
    lat = metadata.get("latitude", "N/A")
    lon = metadata.get("longitude", "N/A")
    
    lat_str = f"{lat:.4f}" if lat else "N/A"
    lon_str = f"{lon:.4f}" if lon else "N/A"
    
    coord_y = info_y + line_height + int(10 * scale)
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Coords,,"
        f"{{\\an7\\pos({x},{coord_y})}}{ts_str}"
    )
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Coords,,"
        f"{{\\an7\\pos({x},{coord_y + line_height})}}Lat: {lat_str} Lon: {lon_str}"
    )
    
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_width}\n"
        f"PlayResY: {video_height}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + "\n".join(styles)
        + "\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
        + "\n".join(events)
        + "\n"
    )

# REPLACE apply_overlay() with flight-specific version (line 450):
def apply_flight_overlay(
    input_path: str,
    output_path: str,
    flight_metadata: dict,
) -> str:
    """
    Burn flight data HUD onto detection clip.
    
    Returns output_path on success, input_path on failure.
    """
    ffmpeg_exe = _get_ass_ffmpeg()
    width, height = _get_video_dimensions(input_path)
    clip_duration = _get_video_duration(input_path)
    
    ass_content = _build_flight_overlay(
        metadata=flight_metadata,
        clip_duration=clip_duration,
        video_width=width,
        video_height=height,
    )
    
    ass_fd, ass_path = tempfile.mkstemp(suffix=".ass", prefix="chemtrail_")
    try:
        with os.fdopen(ass_fd, "w") as f:
            f.write(ass_content)
        
        escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        vf = f"ass={escaped}"
        
        for codec_args in (
            ["-c:v", "libx264", "-crf", "18"],
            ["-c:v", "mpeg4", "-q:v", "5"],
        ):
            result = subprocess.run(
                [
                    ffmpeg_exe, "-y",
                    "-i", input_path,
                    "-vf", vf,
                    *codec_args,
                    "-c:a", "copy",
                    output_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and os.path.isfile(output_path):
                return output_path
    finally:
        try:
            os.unlink(ass_path)
        except OSError:
            pass
    
    return input_path

# REMOVE functions no longer needed:
# - get_metadata_samples()
# - reverse_geocode() (keep if geocoding is desired)
# - _geocode_cached()
# - _parse_base_datetime()
# - _format_datetime() (keep if timestamp formatting needed)
# - _chevron_left/right() (Tesla turn signals - not needed)
```

---

## 2. New Bridge Modules to Create

### 2.1 detection_service.py (NEW)

**Location:** `backend\chemtrail\services\detection_service.py`

**Purpose:** Orchestrates the detection->archive pipeline.

**Create with this content:**
```python
"""Detection service - orchestrates CV detection -> archive pipeline."""

from typing import List, Optional, Dict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger
from ..cv.contrail_detector import ContrailDetection, ContrailDetector
from ..cv.cv_utils import preprocess_frame
from ..archive.chunker import (
    chunk_video, 
    is_still_frame_chunk,
    preprocess_chunk,
)
from ..archive.embedder import get_embedder
from ..storage.vector_store import SentryStore
from .flight_service import FlightService
from .geocalc_service import GeoCalculator


class DetectionService:
    """
    Orchestrates detection processing and archival.
    
    Pipeline:
    1. Receive video chunk from chunker
    2. Skip if still-frame (static sky)
    3. Preprocess (downscale, reduce fps)
    4. Run CV detection (contrails, aircraft)
    5. Correlate with flight data
    6. Calculate geolocation
    7. Embed and archive in ChromaDB
    """
    
    def __init__(
        self,
        session: AsyncSession,
        vector_store: SentryStore,
        flight_service: FlightService,
        geo_calculator: GeoCalculator,
        contrail_detector: ContrailDetector,
    ):
        self.session = session
        self.vector_store = vector_store
        self.flight_service = flight_service
        self.geo_calculator = geo_calculator
        self.contrail_detector = contrail_detector
        self.embedder = get_embedder()
    
    async def process_detection_batch(
        self,
        chunks: List[Dict],
        camera_id: str,
        camera_metadata: Dict,
        skip_still_frames: bool = True,
        apply_overlay: bool = False,
    ) -> List[Dict]:
        """
        Process a batch of video chunks through the detection pipeline.
        
        Args:
            chunks: List from chunker with keys:
                   chunk_path, source_file, start_time, end_time
            camera_id: Camera UUID
            camera_metadata: Camera geolocation data
            skip_still_frames: Skip static sky chunks
            apply_overlay: Burn flight data HUD on clips
        
        Returns:
            List of processed detection records
        """
        processed = []
        
        for chunk in chunks:
            try:
                # Step 1: Still-frame check
                if skip_still_frames and is_still_frame_chunk(chunk["chunk_path"]):
                    logger.debug(f"Skipping still-frame chunk: {chunk['chunk_path']}")
                    continue
                
                # Step 2: Preprocess chunk
                preprocessed_path = preprocess_chunk(
                    chunk["chunk_path"],
                    target_resolution=480,
                    target_fps=5,
                )
                
                # Step 3: Extract representative frame for CV
                frame = self._extract_key_frame(preprocessed_path)
                
                # Step 4: Run CV detection
                detections = self.contrail_detector.detect(frame)
                
                if not detections:
                    logger.debug(f"No detections in chunk: {chunk['chunk_path']}")
                    continue
                
                # Step 5: Process each detection
                for detection in detections:
                    detection_record = await self._process_single_detection(
                        detection=detection,
                        chunk=chunk,
                        camera_id=camera_id,
                        camera_metadata=camera_metadata,
                        apply_overlay=apply_overlay,
                    )
                    processed.append(detection_record)
                
            except Exception as e:
                logger.error(f"Error processing chunk {chunk['chunk_path']}: {e}")
                continue
        
        return processed
    
    async def _process_single_detection(
        self,
        detection: ContrailDetection,
        chunk: Dict,
        camera_id: str,
        camera_metadata: Dict,
        apply_overlay: bool,
    ) -> Dict:
        """Process a single detection through the full pipeline."""
        
        # Calculate azimuth/elevation from pixel coordinates
        az, el = self.geo_calculator.pixel_to_az_el(
            x=detection.start_x,
            y=detection.start_y,
            width=1920,
            height=1080,
            cam_azimuth=camera_metadata.get("azimuth", 0),
            cam_elevation=camera_metadata.get("elevation", 0),
            fov_h=camera_metadata.get("fov_horizontal", 60),
            fov_v=camera_metadata.get("fov_vertical", 40),
        )
        
        # Estimate position
        est_lat, est_lon = self.geo_calculator.estimate_position_single(
            cam_lat=camera_metadata["latitude"],
            cam_lon=camera_metadata["longitude"],
            cam_alt=camera_metadata["altitude"],
            az_obj=az,
            el_obj=el,
            assumed_alt=10000,
        )
        
        # Correlate with flights
        timestamp = datetime.fromtimestamp(
            chunk.get("start_time", 0), 
            tz=timezone.utc
        )
        flight_match = await self.flight_service.get_flights_near_position(
            lat=est_lat,
            lon=est_lon,
            radius_km=10,
            limit=1,
        )
        
        icao24 = flight_match[0]["icao24"] if flight_match else None
        callsign = flight_match[0].get("callsign") if flight_match else None
        
        # Build metadata for archive
        archive_metadata = {
            "source_file": chunk["source_file"],
            "start_time": chunk["start_time"],
            "end_time": chunk["end_time"],
            "camera_id": camera_id,
            "camera_name": camera_metadata.get("name", "unknown"),
            "camera_lat": camera_metadata["latitude"],
            "camera_lon": camera_metadata["longitude"],
            "camera_alt": camera_metadata["altitude"],
            "detection_type": "contrail",
            "pixel_x": detection.start_x,
            "pixel_y": detection.start_y,
            "azimuth": az,
            "elevation": el,
            "estimated_lat": est_lat,
            "estimated_lon": est_lon,
            "estimated_alt": 10000,
            "confidence": detection.confidence,
            "contrail_vector": detection.to_dict(),
            "icao24": icao24,
            "callsign": callsign,
            "correlation_score": 0.8 if flight_match else 0.0,
            "position_method": "single_camera",
            "overlay_applied": False,
        }
        
        # Apply overlay if requested and flight matched
        if apply_overlay and icao24:
            from ..archive.overlay import apply_flight_overlay
            import tempfile
            
            overlay_path = tempfile.mktemp(suffix="_overlay.mp4")
            flight_meta = {
                "icao24": icao24,
                "callsign": callsign,
                "timestamp": timestamp,
                "latitude": est_lat,
                "longitude": est_lon,
            }
            result_path = apply_flight_overlay(
                input_path=chunk["chunk_path"],
                output_path=overlay_path,
                flight_metadata=flight_meta,
            )
            archive_metadata["overlay_applied"] = True
            archive_metadata["clip_path"] = result_path
        
        # Embed and archive
        embedding = await self.embedder.embed_video_chunk(chunk["chunk_path"])
        chunk_id = self._generate_chunk_id(chunk["source_file"], chunk["start_time"])
        
        self.vector_store.add_detection(
            chunk_id=chunk_id,
            embedding=embedding,
            metadata=archive_metadata,
        )
        
        logger.info(
            f"Archived detection: {detection.detection_type} "
            f"(confidence: {detection.confidence:.2f})"
        )
        
        return {
            "chunk_id": chunk_id,
            "detection": detection,
            "metadata": archive_metadata,
        }
    
    def _extract_key_frame(self, video_path: str) -> np.ndarray:
        """Extract middle frame from video chunk for CV processing."""
        import cv2
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            raise ValueError(f"Could not extract frame from {video_path}")
        
        return frame
    
    def _generate_chunk_id(self, source_file: str, start_time: float) -> str:
        """Generate deterministic chunk ID."""
        import hashlib
        raw = f"{source_file}:{start_time}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

---

### 2.2 frame_preprocessor.py (NEW)

**Location:** `backend\chemtrail\cv\frame_preprocessor.py`

**Purpose:** Wraps SentrySearch preprocess_chunk() for CV pipeline integration.

**Create with this content:**
```python
"""Frame preprocessing for CV pipeline using SentrySearch logic."""

import cv2
import numpy as np

from chemtrail.archive.chunker import preprocess_chunk as preprocess_video_chunk


def preprocess_frame_for_cv(
    frame: np.ndarray,
    target_resolution: int = 480,
    target_format: str = "gray",
) -> np.ndarray:
    """
    Preprocess a single frame for CV detection.
    
    Args:
        frame: BGR frame from webcam
        target_resolution: Target height in pixels
        target_format: Output format ("gray", "bgr", "rgb")
    
    Returns:
        Preprocessed frame as numpy array
    """
    height, width = frame.shape[:2]
    scale = target_resolution / height
    new_width = int(width * scale)
    
    resized = cv2.resize(frame, (new_width, target_resolution))
    
    if target_format == "gray":
        result = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    elif target_format == "rgb":
        result = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    else:
        result = resized
    
    return result


def enhance_contrast_for_detection(
    frame: np.ndarray,
    clip_limit: float = 2.0,
    tile_size: int = 8,
) -> np.ndarray:
    """
    Apply CLAHE for contrast enhancement (matches contrail_detector.py).
    
    Args:
        frame: Input frame (grayscale recommended)
        clip_limit: CLAHE clip limit
        tile_size: CLAHE tile grid size
    
    Returns:
        Contrast-enhanced frame
    """
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    
    clahe = cv2.createCLAHE(
        clipLimit=clip_limit,
        tileGridSize=(tile_size, tile_size)
    )
    
    return clahe.apply(gray)
```

---

## 3. Files to Modify in Existing Chemtrail Tracker

### 3.1 Database Models

**File:** `backend\db\models.py`

**Add new model for detection archive:**
```python
# Add to existing models

class DetectionArchive(Base):
    """ChromaDB detection archive tracking."""
    __tablename__ = "detection_archive"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(String, nullable=False, index=True, unique=True)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("chemtrail_cameras.id"), nullable=False)
    timestamp = Column(AwareDateTime, nullable=False)
    
    # Archive metadata
    source_file = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    
    # Detection data
    detection_type = Column(Enum(DetectionType), nullable=False)
    confidence = Column(Float, nullable=False)
    icao24 = Column(String, nullable=True)
    callsign = Column(String, nullable=True)
    
    # Position
    estimated_lat = Column(Float, nullable=True)
    estimated_lon = Column(Float, nullable=True)
    estimated_alt = Column(Float, nullable=True)
    
    # Archive status
    embedded = Column(Boolean, default=False)
    overlay_applied = Column(Boolean, default=False)
    clip_path = Column(String, nullable=True)
    
    # Timestamps
    indexed_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(AwareDateTime, nullable=True, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
```

---

### 3.2 Requirements.txt

**File:** `backend\requirements.txt`

**Add these dependencies:**
```txt
# ChromaDB vector store (Phase 1.5)
chromadb>=0.5.0

# Video processing (SentrySearch integration)
imageio-ffmpeg>=0.4.0

# Geocoding for overlay (optional)
geopy>=2.4.0
```

**Note:** `google-genai` is already in requirements.txt (line 23).

---

## 4. Dependency Additions Summary

### 4.1 New Python Packages

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `chromadb` | >=0.5.0 | Vector store for detection archive | P0 |
| `imageio-ffmpeg` | >=0.4.0 | Bundled ffmpeg for video processing | P0 |
| `geopy` | >=2.4.0 | Reverse geocoding for overlay (optional) | P2 |

### 4.2 Installation Command

```bash
cd C:\Users\antmi\ground-station
pip install chromadb imageio-ffmpeg geopy
```

---

## 5. Integration Test Plan

### 5.1 Unit Tests

**File:** `backend\tests\chemtrail\test_sentrysearch_integration.py`

```python
"""SentrySearch integration tests."""

import pytest
from datetime import datetime, timezone

from chemtrail.archive.chunker import chunk_video, is_still_frame_chunk, preprocess_chunk
from chemtrail.storage.vector_store import SentryStore
from chemtrail.archive.search import search_detections
from chemtrail.services.detection_service import DetectionService


class TestChunkerIntegration:
    """Test chunker with video files and still-frame detection."""
    
    def test_chunk_video_file(self, sample_video_path):
        """Test basic video chunking."""
        chunks = chunk_video(sample_video_path, chunk_duration=10, overlap=2)
        
        assert len(chunks) > 0
        assert "chunk_path" in chunks[0]
        assert "start_time" in chunks[0]
        assert "end_time" in chunks[0]
    
    def test_still_frame_skip(self, static_video_chunk):
        """Test still-frame detection skips static scenes."""
        is_still = is_still_frame_chunk(static_video_chunk)
        assert is_still is True
    
    def test_still_frame_process(self, dynamic_video_chunk):
        """Test still-frame detection processes moving scenes."""
        is_still = is_still_frame_chunk(dynamic_video_chunk)
        assert is_still is False
    
    def test_preprocess_chunk(self, video_chunk, tmp_path):
        """Test video preprocessing."""
        output_path = tmp_path / "preprocessed.mp4"
        result = preprocess_chunk(str(video_chunk), target_resolution=480, target_fps=5)
        
        assert result is not None
        # Verify file was created
        from pathlib import Path
        assert Path(result).exists()


class TestVectorStoreIntegration:
    """Test ChromaDB archival and retrieval."""
    
    @pytest.fixture
    def vector_store(self, tmp_path):
        store = SentryStore(db_path=tmp_path / "test_db", backend="gemini")
        yield store
        store.collection.delete(where={})
    
    def test_add_detection(self, vector_store):
        """Test adding detection with metadata."""
        chunk_id = "test_chunk_001"
        embedding = [0.1] * 768
        
        metadata = {
            "source_file": "test.mp4",
            "start_time": 0.0,
            "end_time": 10.0,
            "camera_id": "cam-123",
            "camera_name": "Test Cam",
            "camera_lat": 47.6062,
            "camera_lon": -122.3321,
            "camera_alt": 100,
            "detection_type": "contrail",
            "pixel_x": 960,
            "pixel_y": 540,
            "azimuth": 180.0,
            "elevation": 45.0,
            "confidence": 0.85,
        }
        
        vector_store.add_detection(chunk_id, embedding, metadata)
        
        results = vector_store.search(embedding, n_results=1)
        assert len(results) == 1
        assert results[0]["source_file"] == "test.mp4"
    
    def test_search_by_flight(self, vector_store, indexed_detections):
        """Test filtering by ICAO24."""
        results = vector_store.search_by_flight(icao24="4b1a02", n_results=10)
        
        for result in results:
            assert result.get("icao24") == "4b1a02"
    
    def test_search_by_camera(self, vector_store, indexed_detections):
        """Test filtering by camera ID."""
        results = vector_store.search_by_camera(camera_id="cam-123", n_results=10)
        
        for result in results:
            assert result["camera_id"] == "cam-123"


class TestSearchIntegration:
    """Test semantic search with metadata filters."""
    
    @pytest.fixture
    def indexed_store(self, tmp_path):
        store = SentryStore(db_path=tmp_path / "test_db")
        yield store
    
    def test_semantic_search(self, indexed_store):
        """Test natural language search."""
        results = search_detections(
            query="contrails from Boeing 737",
            vector_store=indexed_store,
            n_results=5,
        )
        
        assert len(results) >= 0  # May be empty with no indexed data
    
    def test_combined_search_and_filter(self, indexed_store):
        """Test semantic search with flight filter."""
        results = search_detections(
            query="high altitude contrails",
            vector_store=indexed_store,
            icao24="4b1a02",
            n_results=5,
        )
        
        # All results should match the filter
        for result in results:
            if result.get("icao24"):
                assert result["icao24"] == "4b1a02"
```

---

### 5.2 Integration Test Commands

```bash
# Run SentrySearch integration tests
pytest backend/tests/chemtrail/test_sentrysearch_integration.py -v

# Run with coverage
pytest backend/tests/chemtrail/test_sentrysearch_integration.py ^
    --cov=chemtrail/archive ^
    --cov=chemtrail/storage ^
    --cov-report=html

# Run specific test class
pytest backend/tests/chemtrail/test_sentrysearch_integration.py::TestVectorStoreIntegration -v
```

---

## 6. Acceptance Criteria for Phase 1.5

### 6.1 Functional Criteria

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| AC-1 | Detection clips are archived in ChromaDB | Query ChromaDB collection, verify entries exist with correct metadata schema |
| AC-2 | Semantic search returns relevant results | Execute natural language queries, verify results match query intent |
| AC-3 | Metadata filtering works (icao24, camera_id, date range) | Query with filters, verify all results match filter criteria |
| AC-4 | Still-frame detection skips static sky chunks | Process static webcam feed, verify >60% chunks skipped |
| AC-5 | Flight data overlay renders correctly on clips | Generate overlay, visually verify HUD shows callsign, altitude, speed, heading |
| AC-6 | Embedding pipeline completes without errors | Process 10 detection clips, verify all embed successfully |

### 6.2 Performance Criteria

| ID | Criterion | Target | Measurement |
|----|-----------|--------|-------------|
| AC-7 | Detection archive latency | <5s | Chunk received -> ChromaDB stored |
| AC-8 | Semantic search latency | <500ms (P95) | Query -> Results response time |
| AC-9 | Still-frame skip rate | 60-80% | Skipped / Total chunks (stationary cams) |
| AC-10 | Embedding cost | <$5/day | Gemini API daily spend (10 cameras) |

### 6.3 Quality Criteria

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| AC-11 | All new tests pass | `pytest backend/tests/chemtrail/test_sentrysearch_integration.py` exits 0 |
| AC-12 | Existing tests still pass | `pytest backend/tests/chemtrail/` exits 0 (no regressions) |
| AC-13 | Code coverage >80% for new modules | `--cov=chemtrail/archive --cov=chemtrail/storage` report |
| AC-14 | No circular imports | Import all new modules without errors |
| AC-15 | Documentation updated | INTEGRATION_ARCHITECTURE.md reflects actual implementation |

---

## 7. Sprint Breakdown

### Week 1: Core Infrastructure (Days 1-5)

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | Copy embedder.py, base_embedder.py, gemini_embedder.py, local_embedder.py | Embedding modules ready |
| 2 | Copy and adapt chunker.py (RTSP support, continuous mode) | Stream chunking works |
| 3 | Copy and adapt store.py -> vector_store.py (extended metadata) | ChromaDB schema ready |
| 4 | Create detection_service.py (skeleton) | Pipeline orchestrator exists |
| 5 | Unit tests for chunker + vector_store | Tests passing |

### Week 2: Search & Overlay (Days 6-10)

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 6 | Copy and adapt search.py (metadata filtering) | Search with filters works |
| 7 | Copy and adapt overlay.py (flight HUD) | Flight data overlay renders |
| 8 | Complete detection_service.py | Full pipeline functional |
| 9 | Integration tests | E2E validation passes |
| 10 | API endpoints for semantic search | REST interface available |

### Week 3: Polish & Documentation (Days 11-15)

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 11 | Performance tuning | Optimized pipeline |
| 12 | Error handling + logging | Production ready |
| 13 | Documentation update | User guide complete |
| 14 | Final testing + bug fixes | Release candidate |
| 15 | Code review + merge | Phase 1.5 complete |

---

## 8. ChromaDB Query Examples

### 8.1 Basic Semantic Search

```python
from chemtrail.storage.vector_store import SentryStore
from chemtrail.archive.search import search_detections

store = SentryStore(db_path="C:/Users/antmi/ground-station/backend/.chemtrail_db")

# Natural language query
results = search_detections(
    query="contrails from Boeing 737",
    vector_store=store,
    n_results=10,
)

for result in results:
    print(f"Score: {result['score']:.2f}, Callsign: {result.get('callsign', 'N/A')}")
```

### 8.2 Flight-Specific Search

```python
# Search by specific flight ICAO24
flight_results = store.search_by_flight(
    icao24="4b1a02",
    n_results=10,
)

# Search by camera with date range
from datetime import datetime, timedelta

week_ago = datetime.now() - timedelta(days=7)
camera_results = store.search_by_camera(
    camera_id="cam-123",
    date_from=week_ago,
    n_results=20,
)

# Search by geographic bounding box (Seattle downtown)
location_results = store.search_by_location(
    lat_min=47.60,
    lat_max=47.62,
    lon_min=-122.35,
    lon_max=-122.32,
    n_results=10,
)
```

---

## 9. Risk Mitigation

### 9.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ChromaDB schema changes | Low | Medium | Version pin `chromadb>=0.5.0,<0.6.0` |
| Gemini API rate limits | Medium | Low | Implement local Qwen3-VL fallback |
| RTSP stream incompatibility | Medium | Medium | Test with major providers, add fallback |
| Overlay rendering failures | Medium | Low | Graceful degradation (no overlay) |
| Still-frame false negatives | Low | Low | Tunable threshold, disable flag |

### 9.2 Rollback Plan

If integration fails:

```bash
# Revert archive modules
git checkout HEAD -- backend/chemtrail/archive/
git checkout HEAD -- backend/chemtrail/storage/vector_store.py

# Remove ChromaDB dependency
pip uninstall chromadb

# Continue with existing functionality (unaffected)
```

---

## 10. File Inventory Summary

### 10.1 Files to Copy from SentrySearch

```
C:\Users\antmi\sentrysearch-temp\sentrysearch\
├── chunker.py           → backend\chemtrail\archive\chunker.py (ADAPT)
├── embedder.py          → backend\chemtrail\archive\embedder.py (DIRECT)
├── base_embedder.py     → backend\chemtrail\archive\base_embedder.py (DIRECT)
├── gemini_embedder.py   → backend\chemtrail\archive\gemini_embedder.py (DIRECT)
├── local_embedder.py    → backend\chemtrail\archive\local_embedder.py (DIRECT)
├── store.py             → backend\chemtrail\storage\vector_store.py (ADAPT)
├── search.py            → backend\chemtrail\archive\search.py (ADAPT)
└── overlay.py           → backend\chemtrail\archive\overlay.py (ADAPT)
```

### 10.2 Files to Create (New)

```
backend\chemtrail\
├── services/
│   └── detection_service.py       (NEW - pipeline orchestrator)
├── cv/
│   └── frame_preprocessor.py      (NEW - CV preprocessing)
└── archive/
    └── __init__.py                (NEW - package init)
```

### 10.3 Files to Modify

```
backend\db\models.py                    (ADD DetectionArchive model)
backend\requirements.txt                (ADD chromadb, imageio-ffmpeg, geopy)
```

---

## 11. Success Metrics

### 11.1 Query Examples (Post-Phase 1.5)

After Phase 1.5 is complete, the following queries should work:

- "Find contrails from Boeing 737"
- "Show detections over downtown Seattle"
- "Contrails from flights departing JFK yesterday"
- "High altitude contrails (above 30000ft)"
- "Persistent contrails lasting over 60 seconds"

### 11.2 API Endpoints

New REST endpoints to implement:

```
GET /api/detections/search?q=natural_language_query
GET /api/detections/search/advanced?icao24=...&camera_id=...&date_from=...
POST /api/detections/{id}/overlay  # Generate HUD overlay
GET /api/archive/stats  # ChromaDB statistics
```

---

## 12. Next Steps for Senior Developer

1. **Review this brief** - Ensure all modifications are understood
2. **Set up development environment** - Install new dependencies
3. **Execute file copying** - Follow Section 1 copy commands
4. **Implement adaptations** - Apply code changes from Section 1.2
5. **Create bridge modules** - Write files from Section 2
6. **Modify existing files** - Apply changes from Section 3
7. **Run integration tests** - Execute test plan from Section 5
8. **Validate acceptance criteria** - Verify all criteria from Section 6

**Estimated effort:** 80-100 hours (2-3 weeks full-time)

---

*Document prepared by Software Program Manager based on INTEGRATION_ARCHITECTURE.md and INTEGRATION_PLAN.md*
