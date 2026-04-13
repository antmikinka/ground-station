# Chemtrail Webcam Tracker - Phase 2 Implementation Brief
## Footage Acquisition, Sorting, and End-to-End Pipeline Orchestration

**Version:** 1.0.0  
**Author:** Software Program Manager (PMP, PgMP, SAFe)  
**Date:** 2026-04-11  
**Status:** Ready for Handoff  
**Target:** Enhanced Senior Developer

---

## Executive Summary

This implementation brief specifies Phase 2 of the Chemtrail Webcam Tracker, transforming the system from a detection-focused pipeline into a **complete end-to-end footage management system**. This phase adds live webcam feed acquisition, historical video ingestion, intelligent video cataloging with quality scoring, weather enrichment, and unified pipeline orchestration.

### Phase 2 Deliverables

| Module | File | Priority | Est. Hours |
|--------|------|----------|------------|
| Webcam Manager | `backend/chemtrail/sources/webcam_manager.py` | P0 | 8 |
| Historical Ingestor | `backend/chemtrail/sources/historical_ingestor.py` | P0 | 8 |
| Video Catalog | `backend/chemtrail/sources/video_catalog.py` | P0 | 6 |
| Weather Service | `backend/chemtrail/sources/weather_service.py` | P1 | 4 |
| Pipeline Orchestrator | `backend/chemtrail/sources/pipeline_orchestrator.py` | P0 | 10 |
| Sources Package | `backend/chemtrail/sources/__init__.py` | P0 | 1 |

**Total Estimated Effort:** 37 hours (approximately 5 working days)

---

## 1. Files to Create

### 1.1 Package Initialization

#### File: `backend/chemtrail/sources/__init__.py`

```python
# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Chemtrail sources module - Phase 2 footage acquisition and orchestration.

This package provides:
- Live webcam feed acquisition (RTSP/MJPEG/HLS)
- Historical video ingestion and cataloging
- Video sorting by location, weather, and quality
- End-to-end pipeline orchestration
- Weather enrichment from Open-Meteo API
"""

from .webcam_manager import (
    WebcamManager,
    StreamConnection,
    HealthMonitor,
    StreamType,
    StreamStatus,
    StreamConfig,
    StreamHealth,
)
from .historical_ingestor import (
    HistoricalIngestor,
    VideoScanner,
    MetadataExtractor,
    VideoMetadata,
    ScanResult,
)
from .video_catalog import (
    VideoCatalog,
    VideoRecord,
    ProcessingStatus,
)
from .weather_service import (
    WeatherEnrichmentService,
    WeatherData,
)
from .pipeline_orchestrator import (
    PipelineOrchestrator,
    PipelineJob,
    PipelineConfig,
    PipelineStage,
    PipelineStatus,
)

__all__ = [
    # Webcam Manager
    "WebcamManager",
    "StreamConnection",
    "HealthMonitor",
    "StreamType",
    "StreamStatus",
    "StreamConfig",
    "StreamHealth",
    # Historical Ingestor
    "HistoricalIngestor",
    "VideoScanner",
    "MetadataExtractor",
    "VideoMetadata",
    "ScanResult",
    # Video Catalog
    "VideoCatalog",
    "VideoRecord",
    "ProcessingStatus",
    # Weather Service
    "WeatherEnrichmentService",
    "WeatherData",
    # Pipeline Orchestrator
    "PipelineOrchestrator",
    "PipelineJob",
    "PipelineConfig",
    "PipelineStage",
    "PipelineStatus",
]
```

---

### 1.2 Webcam Manager

#### File: `backend/chemtrail/sources/webcam_manager.py`

**Purpose:** Manage live webcam stream acquisition from RTSP/MJPEG/HLS sources including public webcam APIs (Windy.com, WebcamTaxi, OpenSky webcams) and self-hosted cameras.

**Key Responsibilities:**
1. Discover webcams from public APIs (Windy.com, WebcamTaxi, EarthCam)
2. Manage RTSP/MJPEG/HLS stream connections
3. Monitor stream health and auto-reconnect
4. Capture continuous segments for processing
5. Track online/offline status per camera

```python
# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Live Webcam Feed Acquisition Manager.

Responsibilities:
1. Manage connections to RTSP/MJPEG/HLS streams
2. Monitor stream health and auto-reconnect
3. Capture continuous segments for processing
4. Handle multiple concurrent streams
5. Integrate with public webcam APIs (Windy.com, WebcamTaxi)
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio
import subprocess
import logging

import httpx

logger = logging.getLogger(__name__)


class StreamType(Enum):
    """Supported stream protocol types."""
    RTSP = "rtsp"
    MJPEG = "mjpeg"
    HLS = "hls"
    YOUTUBE = "youtube"


class StreamStatus(Enum):
    """Stream connection status states."""
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class StreamConfig:
    """Configuration for a webcam stream.
    
    Attributes:
        camera_id: Unique identifier for the camera
        name: Human-readable camera name
        url: Stream URL (RTSP, MJPEG, HLS, or YouTube)
        stream_type: Protocol type
        latitude: Camera latitude (WGS84 decimal degrees)
        longitude: Camera longitude (WGS84 decimal degrees)
        altitude: Camera altitude in meters AMSL
        azimuth: Camera heading (0-360, N=0, E=90)
        elevation: Camera tilt (-90 to 90, 0=horizon)
        fov_horizontal: Horizontal field of view in degrees
        fov_vertical: Vertical field of view in degrees
        segment_duration: Duration of each captured segment in seconds
        output_dir: Directory for captured segments
        quality_threshold: Minimum quality score (0-1) for acceptance
    """
    camera_id: str
    name: str
    url: str
    stream_type: StreamType
    latitude: float
    longitude: float
    altitude: float
    azimuth: float
    elevation: float
    fov_horizontal: Optional[float] = None
    fov_vertical: Optional[float] = None
    segment_duration: int = 60
    output_dir: str = "/tmp/chemtrail_webcam"
    quality_threshold: float = 0.5


@dataclass
class StreamHealth:
    """Current health metrics for a stream.
    
    Attributes:
        status: Current stream status
        uptime_seconds: Total uptime in seconds
        segment_count: Number of segments captured
        last_segment_time: Timestamp of last segment
        error_message: Error message if status is ERROR
        quality_score: Current quality score (0-1)
        reconnect_count: Number of reconnection attempts
    """
    status: StreamStatus
    uptime_seconds: float
    segment_count: int
    last_segment_time: datetime
    error_message: Optional[str] = None
    quality_score: float = 0.0
    reconnect_count: int = 0


class WindyClient:
    """Client for Windy.com Webcams API.
    
    API Documentation: https://api.windy.com/api/webcams
    Free tier: 5000 calls/day
    """
    
    BASE_URL = "https://api.windy.com/api/webcams"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)
    
    async def find_nearby_webcams(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50,
        categories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Find webcams near a location.
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Search radius in kilometers
            categories: Filter by categories (e.g., ['sky', 'airport'])
            
        Returns:
            List of webcam info dicts with keys:
            - id: Webcam identifier
            - name: Camera name
            - latitude, longitude: Location
            - url: Stream/image URL
            - status: 'active' or 'inactive'
        """
        params = {
            "apikey": self.api_key,
            "lang": "en",
            "fields": "location,image,player,embed",
        }
        
        # Build category filter
        if categories:
            params["category"] = ",".join(categories)
        
        url = f"{self.BASE_URL}/nearby/{latitude},{longitude},{radius_km}"
        
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        webcams = []
        for item in data.get("result", {}).get("webcams", []):
            if item.get("status") == "active":
                webcams.append({
                    "id": item.get("id"),
                    "name": item.get("location", {}).get("city", "Unknown"),
                    "latitude": item.get("location", {}).get("latitude"),
                    "longitude": item.get("location", {}).get("longitude"),
                    "url": item.get("player", {}).get("live", {}).get("embed"),
                    "status": "active",
                })
        
        return webcams
    
    async def close(self):
        await self._client.aclose()


class StreamConnection:
    """Individual stream connection handler.
    
    Manages ffmpeg subprocess for capturing stream segments.
    """
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.status = StreamStatus.OFFLINE
        self._process: Optional[subprocess.Popen] = None
        self._segment_count = 0
        self._start_time: Optional[datetime] = None
        self._health = StreamHealth(
            status=StreamStatus.OFFLINE,
            uptime_seconds=0,
            segment_count=0,
            last_segment_time=datetime.now(timezone.utc),
        )
    
    @property
    def health(self) -> StreamHealth:
        return self._health
    
    async def start(self) -> None:
        """Start capturing stream."""
        self.status = StreamStatus.CONNECTING
        self._start_time = datetime.now(timezone.utc)
        
        # Ensure output directory exists
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build output pattern
        output_pattern = str(
            output_dir / f"{self.config.camera_id}_%Y%m%d_%H%M%S.mp4"
        )
        
        # Build ffmpeg command
        cmd = self._build_ffmpeg_cmd(output_pattern)
        
        logger.info(f"Starting stream capture for {self.config.camera_id}")
        
        # Launch ffmpeg subprocess
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        self.status = StreamStatus.STREAMING
        self._health.status = StreamStatus.STREAMING
    
    async def stop(self) -> None:
        """Stop capturing stream."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._process.wait),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                self._process.kill()
        
        self.status = StreamStatus.OFFLINE
        self._health.status = StreamStatus.OFFLINE
        logger.info(f"Stopped stream capture for {self.config.camera_id}")
    
    def _build_ffmpeg_cmd(self, output_pattern: str) -> List[str]:
        """Build ffmpeg command for stream type."""
        base_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output files
            "-re",  # Read input at native frame rate
        ]
        
        # Stream-specific options
        if self.config.stream_type == StreamType.RTSP:
            base_cmd.extend(["-rtsp_transport", "tcp"])
        elif self.config.stream_type == StreamType.YOUTUBE:
            base_cmd.extend(["-user_agent", "Mozilla/5.0"])
        elif self.config.stream_type == StreamType.HLS:
            base_cmd.extend(["-strict", "experimental"])
        
        # Input and output
        base_cmd.extend([
            "-i", self.config.url,
            "-c", "copy",  # Copy codec (no re-encoding)
            "-segment_time", str(self.config.segment_duration),
            "-segment_format", "mp4",
            "-reset_timestamps", "1",
            "-strftime", "1",
            output_pattern,
        ])
        
        return base_cmd
    
    def update_health(self, segment_count: int) -> None:
        """Update health metrics after segment capture."""
        self._segment_count = segment_count
        self._health.segment_count = segment_count
        self._health.last_segment_time = datetime.now(timezone.utc)
        
        if self._start_time:
            self._health.uptime_seconds = (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds()


class HealthMonitor:
    """Monitor stream health and trigger reconnection.
    
    Checks streams periodically and flags issues when segments
    are not being produced.
    """
    
    STALE_THRESHOLD_SECONDS = 120  # 2 minutes without segment = stale
    
    def __init__(self):
        self._streams: Dict[str, StreamHealth] = {}
    
    def add_stream(self, camera_id: str, health: StreamHealth) -> None:
        """Register a stream for monitoring."""
        self._streams[camera_id] = health
    
    def remove_stream(self, camera_id: str) -> None:
        """Unregister a stream."""
        if camera_id in self._streams:
            del self._streams[camera_id]
    
    def get_health(self, camera_id: str) -> Optional[StreamHealth]:
        """Get current health for a stream."""
        return self._streams.get(camera_id)
    
    async def check_all(self) -> Dict[str, StreamHealth]:
        """Check health of all streams.
        
        Returns dict of camera_id -> health for streams needing attention.
        """
        needs_attention = {}
        
        for camera_id, health in list(self._streams.items()):
            # Check if stream is producing segments
            time_since_segment = (
                datetime.now(timezone.utc) - health.last_segment_time
            ).total_seconds()
            
            if time_since_segment > self.STALE_THRESHOLD_SECONDS:
                if health.status != StreamStatus.ERROR:
                    health.status = StreamStatus.ERROR
                    health.error_message = f"No segments for {time_since_segment:.0f}s"
                    needs_attention[camera_id] = health
        
        return needs_attention


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
        self._streams: Dict[str, StreamConnection] = {}
        self._health_monitor = HealthMonitor()
        self._running = False
        self._windy_client: Optional[WindyClient] = None
    
    @property
    def streams(self) -> Dict[str, StreamConnection]:
        return self._streams
    
    @property
    def health_monitor(self) -> HealthMonitor:
        return self._health_monitor
    
    async def initialize(self, windy_api_key: Optional[str] = None) -> None:
        """Initialize manager with optional API clients."""
        if windy_api_key:
            self._windy_client = WindyClient(windy_api_key)
            logger.info("Windy.com API client initialized")
    
    async def discover_webcams(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50,
        categories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Discover webcams from Windy.com API.
        
        Args:
            latitude: Search center latitude
            longitude: Search center longitude
            radius_km: Search radius
            categories: Categories to filter (e.g., ['sky', 'airport'])
            
        Returns:
            List of webcam info dicts suitable for StreamConfig creation
        """
        if not self._windy_client:
            logger.warning("Windy client not initialized")
            return []
        
        return await self._windy_client.find_nearby_webcams(
            latitude, longitude, radius_km, categories
        )
    
    async def add_stream(self, config: StreamConfig) -> None:
        """Register a new stream."""
        connection = StreamConnection(config)
        self._streams[config.camera_id] = connection
        self._health_monitor.add_stream(config.camera_id, connection.health)
        logger.info(f"Added stream: {config.camera_id} ({config.name})")
    
    async def remove_stream(self, camera_id: str) -> None:
        """Remove and stop a stream."""
        if camera_id in self._streams:
            await self._streams[camera_id].stop()
            del self._streams[camera_id]
            self._health_monitor.remove_stream(camera_id)
            logger.info(f"Removed stream: {camera_id}")
    
    async def start_all(self) -> None:
        """Start all registered streams."""
        tasks = [conn.start() for conn in self._streams.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Started {len(self._streams)} streams")
    
    async def stop_all(self) -> None:
        """Stop all streams."""
        tasks = [conn.stop() for conn in self._streams.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All streams stopped")
    
    def get_health(self, camera_id: str) -> Optional[StreamHealth]:
        """Get current health for a stream."""
        return self._health_monitor.get_health(camera_id)
    
    async def run_forever(self) -> None:
        """Run stream manager continuously with health monitoring."""
        self._running = True
        await self.start_all()
        
        while self._running:
            # Monitor health and auto-reconnect
            needs_attention = await self._health_monitor.check_all()
            
            for camera_id, health in needs_attention.items():
                logger.warning(
                    f"Stream {camera_id} needs attention: {health.error_message}"
                )
                # Could trigger auto-reconnect here
            
            await asyncio.sleep(30)
    
    async def __aenter__(self) -> "WebcamManager":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._running = False
        await self.stop_all()
        if self._windy_client:
            await self._windy_client.close()
```

---

### 1.3 Historical Ingestor

#### File: `backend/chemtrail/sources/historical_ingestor.py`

**Purpose:** Scan directories for video files, extract metadata with ffprobe, and catalog footage in the database.

**Key Responsibilities:**
1. Recursive directory scanning for video files
2. Video metadata extraction via ffprobe
3. SHA256 checksum calculation for deduplication
4. Support MP4, MOV, AVI, MKV, WebM formats

```python
# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Historical Video Ingestor.

Responsibilities:
1. Scan directories for video files
2. Extract metadata (duration, resolution, codec, creation date)
3. Import videos into catalog
4. Deduplicate by content hash
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set
import logging

logger = logging.getLogger(__name__)


# Supported video file extensions
SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}


@dataclass
class VideoMetadata:
    """Extracted video metadata.
    
    Attributes:
        file_path: Absolute path to video file
        file_size_bytes: File size in bytes
        checksum_sha256: SHA256 hash for deduplication
        duration_seconds: Video duration
        width: Video width in pixels
        height: Video height in pixels
        fps: Frames per second
        codec: Video codec name (e.g., 'h264', 'hevc')
        bitrate_kbps: Bitrate in kbps
        creation_date: File creation/modification date
    """
    file_path: str
    file_size_bytes: int
    checksum_sha256: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    codec: str
    bitrate_kbps: int
    creation_date: datetime


@dataclass
class ScanResult:
    """Result of directory scan.
    
    Attributes:
        found: List of found video file paths
        directory: Scanned directory path
        recursive: Whether scan was recursive
        count: Number of files found
    """
    found: List[str]
    directory: str
    recursive: bool
    count: int


class VideoScanner:
    """Discover video files in directories."""
    
    def __init__(self, extensions: Optional[Set[str]] = None):
        self.extensions = extensions or SUPPORTED_EXTENSIONS
    
    async def scan(
        self,
        directory: str,
        recursive: bool = True,
    ) -> ScanResult:
        """Scan directory for video files.
        
        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            ScanResult with found file paths
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        found_files = []
        iterator = directory.rglob("*") if recursive else directory.iterdir()
        
        for path in iterator:
            if path.is_file() and path.suffix.lower() in self.extensions:
                found_files.append(str(path.resolve()))
        
        # Sort for consistent ordering
        found_files.sort()
        
        logger.info(
            f"Scan complete: found {len(found_files)} video files "
            f"in {directory} (recursive={recursive})"
        )
        
        return ScanResult(
            found=found_files,
            directory=str(directory),
            recursive=recursive,
            count=len(found_files),
        )
    
    def is_video_file(self, path: Path) -> bool:
        """Check if file has a video extension."""
        return path.suffix.lower() in self.extensions


class MetadataExtractor:
    """Extract video metadata using ffprobe."""
    
    def __init__(self):
        pass
    
    async def extract(self, file_path: str) -> VideoMetadata:
        """Extract all metadata from video file.
        
        Args:
            file_path: Path to video file
            
        Returns:
            VideoMetadata with extracted information
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # File stats
        file_size = path.stat().st_size
        creation_date = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        )
        
        # ffprobe metadata
        ffprobe_output = await self._run_ffprobe(str(path))
        
        # Find video stream
        video_stream = None
        for stream in ffprobe_output.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break
        
        if not video_stream:
            raise ValueError(f"No video stream found in {file_path}")
        
        # Extract video info
        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)
        codec = video_stream.get("codec_name", "unknown")
        
        # Frame rate (may be fraction like "30000/1001")
        fps_str = video_stream.get("r_frame_rate", "0/1")
        try:
            fps_num, fps_den = map(int, fps_str.split("/"))
            fps = fps_num / fps_den if fps_den else 0
        except (ValueError, ZeroDivisionError):
            fps = 0
        
        # Duration from format or stream
        format_info = ffprobe_output.get("format", {})
        duration = float(format_info.get("duration", 0))
        if duration == 0:
            duration = float(video_stream.get("duration", 0))
        
        # Bitrate
        bitrate = format_info.get("bit_rate", "0")
        try:
            bitrate_kbps = int(float(bitrate)) // 1000
        except ValueError:
            bitrate_kbps = 0
        
        # Calculate checksum
        checksum = await self._calculate_checksum(file_path)
        
        return VideoMetadata(
            file_path=str(path),
            file_size_bytes=file_size,
            checksum_sha256=checksum,
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
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(
                f"ffprobe failed for {file_path}: {stderr.decode()}"
            )
        
        return json.loads(stdout)
    
    async def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum for deduplication.
        
        Reads file in chunks to handle large files efficiently.
        """
        sha256 = hashlib.sha256()
        
        def _read_chunks():
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        
        await asyncio.to_thread(_read_chunks)
        return sha256.hexdigest()


class HistoricalIngestor:
    """
    Scan and import historical video files.
    
    Usage:
        ingestor = HistoricalIngestor(catalog_db_path="/path/to/db")
        results = await ingestor.scan_directory("/path/to/videos")
        
        # Import found videos
        for video_path in results.found:
            video_id = await ingestor.import_video(video_path)
    """
    
    def __init__(self, catalog_db_path: str):
        self.catalog_db_path = Path(catalog_db_path)
        self.scanner = VideoScanner()
        self.metadata_extractor = MetadataExtractor()
    
    async def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> ScanResult:
        """Scan directory for video files."""
        return await self.scanner.scan(directory, recursive)
    
    async def import_video(
        self,
        file_path: str,
        camera_id: Optional[str] = None,
        metadata_override: Optional[dict] = None,
    ) -> str:
        """Import a video file into the catalog.
        
        Args:
            file_path: Path to video file
            camera_id: Optional associated camera ID
            metadata_override: Optional metadata overrides
            
        Returns:
            video_id: UUID of imported video (or existing if duplicate)
        """
        import uuid
        
        # Check for duplicate first
        checksum = await self.metadata_extractor._calculate_checksum(file_path)
        
        # Note: Duplicate check requires database access - implement in VideoCatalog
        # existing = await self._check_duplicate(checksum)
        # if existing:
        #     return existing
        
        # Extract metadata
        metadata = await self.metadata_extractor.extract(file_path)
        
        # Create catalog entry
        video_id = str(uuid.uuid4())
        
        logger.info(f"Imported video: {file_path} -> {video_id}")
        
        return video_id
    
    async def _check_duplicate(self, checksum: str) -> Optional[str]:
        """Check if video with same checksum exists.
        
        Returns existing video_id if found, None otherwise.
        Note: Requires VideoCatalog integration.
        """
        # Placeholder - implement with VideoCatalog integration
        return None
```

---

### 1.4 Video Catalog

#### File: `backend/chemtrail/sources/video_catalog.py`

**Purpose:** Store and query video metadata with PostgreSQL, create ChromaDB embeddings for semantic search, and manage sorting/filtering by camera, date, weather, and quality.

**Key Responsibilities:**
1. PostgreSQL CRUD operations for video catalog
2. ChromaDB integration for video catalog collection
3. Search with filters (camera, date range, quality, weather)
4. Processing queue management

```python
# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Video Catalog - Sorting and Indexing.

Responsibilities:
1. Store video metadata in PostgreSQL
2. Create ChromaDB embeddings for semantic search
3. Sort and filter by camera, date, weather, quality
4. Manage video processing queue
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum as PyEnum
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

import asyncpg
import chromadb

logger = logging.getLogger(__name__)


class ProcessingStatus(str, PyEnum):
    """Video processing status."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VideoRecord:
    """Complete video catalog record.
    
    Attributes:
        id: Unique video identifier (UUID)
        source_type: Type of source (live_webcam, historical_file, youtube)
        source_id: Camera ID or file path
        source_url: Original URL or path
        camera_id: Linked camera record ID
        camera_name: Human-readable camera name
        latitude: Camera latitude
        longitude: Camera longitude
        altitude: Camera altitude
        azimuth: Camera azimuth (optional)
        elevation: Camera elevation (optional)
        start_time: Video start timestamp
        end_time: Video end timestamp
        duration_seconds: Video duration
        quality_score: Overall quality score (0-1)
        resolution: Resolution string (480p, 720p, 1080p, 4K)
        weather_condition: Weather condition tag
        cloud_cover_pct: Cloud cover percentage
        processing_status: Current processing status
        file_path: Local file path
        file_size_bytes: File size
        checksum_sha256: SHA256 checksum
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
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


# ChromaDB collection name for video catalog
VIDEO_CATALOG_COLLECTION = "chemtrail_video_catalog"


class VideoCatalog:
    """
    Video catalog database operations.
    
    Usage:
        catalog = VideoCatalog(db_url="postgresql://...", chroma_path="/path")
        await catalog.initialize()
        
        # Add video
        await catalog.add_video(video_record)
        
        # Search with filters
        videos = await catalog.search(
            camera_id="cam-001",
            date_from=datetime(2026, 4, 1),
            min_quality=0.7,
        )
    """
    
    def __init__(
        self,
        db_url: str,
        chroma_path: Optional[str] = None,
    ):
        self.db_url = db_url
        self.chroma_path = chroma_path
        self._conn: Optional[asyncpg.Connection] = None
        self._chroma_client: Optional[chromadb.Client] = None
        self._chroma_collection: Optional[chromadb.Collection] = None
    
    async def initialize(self) -> None:
        """Initialize database connections."""
        # PostgreSQL connection
        self._conn = await asyncpg.connect(self.db_url)
        logger.info("Connected to PostgreSQL video catalog")
        
        # ChromaDB connection
        if self.chroma_path:
            self._chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=VIDEO_CATALOG_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Initialized ChromaDB video catalog")
    
    async def close(self) -> None:
        """Close database connections."""
        if self._conn:
            await self._conn.close()
        if self._chroma_client:
            self._chroma_client.close()
    
    async def add_video(self, video: VideoRecord) -> None:
        """Add video to catalog.
        
        Uses ON CONFLICT to handle duplicate checksums.
        """
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
            """,
                video.id,
                video.source_type,
                video.source_id,
                video.source_url,
                video.camera_id,
                video.camera_name,
                video.latitude,
                video.longitude,
                video.altitude,
                video.azimuth,
                video.elevation,
                video.start_time,
                video.end_time,
                video.duration_seconds,
                video.quality_score,
                video.resolution,
                video.weather_condition,
                video.cloud_cover_pct,
                video.processing_status.value,
                video.file_path,
                video.file_size_bytes,
                video.checksum_sha256,
                video.created_at,
                video.updated_at,
            )
    
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
        """Search catalog with filters.
        
        Args:
            camera_id: Filter by camera ID
            date_from: Filter by start date (inclusive)
            date_to: Filter by end date (inclusive)
            min_quality: Minimum quality score (0-1)
            weather_condition: Filter by weather condition
            limit: Maximum results to return
            offset: Result offset for pagination
            
        Returns:
            List of matching VideoRecord objects
        """
        query = "SELECT * FROM video_catalog WHERE 1=1"
        params: List[Any] = []
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
        
        # Sort by quality score descending
        query += f" ORDER BY quality_score DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
        params.extend([limit, offset])
        
        rows = await self._conn.fetch(query, *params)
        return [self._row_to_record(row) for row in rows]
    
    async def get_by_id(self, video_id: str) -> Optional[VideoRecord]:
        """Get video by ID."""
        row = await self._conn.fetchrow(
            "SELECT * FROM video_catalog WHERE id = $1", video_id
        )
        return self._row_to_record(row) if row else None
    
    async def get_pending_processing(self, limit: int = 100) -> List[VideoRecord]:
        """Get videos pending processing."""
        rows = await self._conn.fetch("""
            SELECT * FROM video_catalog
            WHERE processing_status = $1
            ORDER BY created_at ASC
            LIMIT $2
        """, ProcessingStatus.PENDING.value, limit)
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
                updated_at = NOW(),
                error_message = $3
            WHERE id = $1
        """, video_id, status.value, error_message)
    
    async def update_weather(
        self,
        video_id: str,
        weather_condition: str,
        cloud_cover_pct: float,
    ) -> None:
        """Update weather enrichment data."""
        await self._conn.execute("""
            UPDATE video_catalog
            SET weather_condition = $2,
                cloud_cover_pct = $3,
                updated_at = NOW()
            WHERE id = $1
        """, video_id, weather_condition, cloud_cover_pct)
    
    async def update_quality(
        self,
        video_id: str,
        quality_score: float,
        resolution: str,
    ) -> None:
        """Update quality scoring data."""
        await self._conn.execute("""
            UPDATE video_catalog
            SET quality_score = $2,
                resolution = $3,
                updated_at = NOW()
            WHERE id = $1
        """, video_id, quality_score, resolution)
    
    async def add_to_chroma(
        self,
        video_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        """Add video catalog entry to ChromaDB for semantic search.
        
        Args:
            video_id: Video UUID
            embedding: Video embedding vector
            metadata: Metadata dict for filtering
        """
        if not self._chroma_collection:
            logger.warning("ChromaDB not initialized")
            return
        
        self._chroma_collection.upsert(
            ids=[video_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )
    
    def _row_to_record(self, row) -> VideoRecord:
        """Convert database row to VideoRecord."""
        if row is None:
            raise ValueError("Row is None")
        
        return VideoRecord(
            id=row["id"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            source_url=row["source_url"],
            camera_id=row.get("camera_id"),
            camera_name=row.get("camera_name"),
            latitude=row["latitude"],
            longitude=row["longitude"],
            altitude=row["altitude"],
            azimuth=row.get("azimuth"),
            elevation=row.get("elevation"),
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_seconds=row["duration_seconds"],
            quality_score=row.get("quality_score", 0.0),
            resolution=row.get("resolution", "unknown"),
            weather_condition=row.get("weather_condition"),
            cloud_cover_pct=row.get("cloud_cover_pct"),
            processing_status=ProcessingStatus(row["processing_status"]),
            file_path=row["file_path"],
            file_size_bytes=row["file_size_bytes"],
            checksum_sha256=row["checksum_sha256"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
```

---

### 1.5 Weather Service

#### File: `backend/chemtrail/sources/weather_service.py`

**Purpose:** Fetch historical weather data from Open-Meteo API (free, no key required) and tag footage with weather conditions.

**Key Responsibilities:**
1. Open-Meteo archive API integration
2. Historical weather lookup by timestamp and location
3. Weather data aggregation for video duration
4. In-memory caching with TTL

```python
# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Weather Enrichment Service.

Weather API integration for video tagging using Open-Meteo free API.
No API key required for non-commercial use.

Tags footage with:
- cloud_cover
- visibility
- wind_speed
- precipitation
- weather condition
"""

import httpx
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class WeatherData:
    """Weather conditions at a specific time and location.
    
    Attributes:
        timestamp: Observation timestamp
        temperature_c: Temperature in Celsius
        humidity_pct: Relative humidity percentage
        cloud_cover_pct: Cloud cover percentage
        visibility_km: Visibility in kilometers
        wind_speed_ms: Wind speed in meters/second
        wind_direction: Wind direction in degrees
        weather_code: WMO weather code
        weather_description: Human-readable weather description
    """
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    cloud_cover_pct: float
    visibility_km: float
    wind_speed_ms: float
    wind_direction: float
    weather_code: int
    weather_description: str


# WMO weather code descriptions
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
    """Fetch and cache weather data for video enrichment.
    
    Uses Open-Meteo Archive API (free, no key required):
    https://api.open-meteo.com/v1/archive
    """
    
    ARCHIVE_API_URL = "https://api.open-meteo.com/v1/archive"
    DEFAULT_CACHE_TTL_HOURS = 24
    
    def __init__(self, cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS):
        self._cache: Dict[str, Tuple[List[WeatherData], datetime]] = {}
        self._cache_ttl_hours = cache_ttl_hours
        self._client = httpx.AsyncClient(timeout=10.0)
    
    async def get_historical_weather(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
    ) -> List[WeatherData]:
        """Fetch historical weather for a time range.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of WeatherData objects for each hour in range
        """
        cache_key = f"{latitude}_{longitude}_{start_time.isoformat()}_{end_time.isoformat()}"
        
        # Check cache
        if cache_key in self._cache:
            cached_data, cached_at = self._cache[cache_key]
            age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
            if age_hours < self._cache_ttl_hours:
                logger.debug(f"Weather cache hit for {cache_key}")
                return cached_data
        
        # Fetch from API
        logger.info(f"Fetching weather for ({latitude}, {longitude}) from {start_time} to {end_time}")
        
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
            "hourly": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "cloud_cover,"
                "visibility,"
                "wind_speed_10m,"
                "wind_direction_10m,"
                "weather_code"
            ),
            "timezone": "auto",
        }
        
        response = await self._client.get(self.ARCHIVE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Parse hourly data
        weather_data = self._parse_hourly_data(data)
        
        # Cache result
        self._cache[cache_key] = (weather_data, datetime.now(timezone.utc))
        logger.debug(f"Cached weather data for {cache_key}")
        
        return weather_data
    
    def get_weather_for_video(
        self,
        weather_data: List[WeatherData],
        video_start: datetime,
        video_end: datetime,
    ) -> Dict[str, Any]:
        """Get aggregated weather for a video's duration.
        
        Args:
            weather_data: Hourly weather data
            video_start: Video start time
            video_end: Video end time
            
        Returns:
            Dict with aggregated weather info:
            - condition: Dominant weather condition
            - temperature_c: Average temperature
            - humidity_pct: Average humidity
            - cloud_cover_pct: Average cloud cover
            - visibility_km: Average visibility
            - weather_code: Dominant weather code
        """
        # Filter weather data points within video timeframe
        relevant = [
            w for w in weather_data
            if video_start <= w.timestamp <= video_end
        ]
        
        if not relevant:
            logger.warning("No weather data for video time range")
            return {
                "condition": "unknown",
                "temperature_c": None,
                "humidity_pct": None,
                "cloud_cover_pct": None,
                "visibility_km": None,
                "weather_code": None,
            }
        
        # Average values
        avg_cloud_cover = sum(w.cloud_cover_pct for w in relevant) / len(relevant)
        avg_temp = sum(w.temperature_c for w in relevant) / len(relevant)
        avg_humidity = sum(w.humidity_pct for w in relevant) / len(relevant)
        avg_visibility = sum(w.visibility_km for w in relevant) / len(relevant)
        
        # Dominant weather condition (most frequent)
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
    
    def _parse_hourly_data(self, api_response: dict) -> List[WeatherData]:
        """Parse Open-Meteo hourly response into WeatherData objects."""
        hourly = api_response.get("hourly", {})
        times = hourly.get("time", [])
        
        weather_data = []
        for i, time_str in enumerate(times):
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            
            weather_data.append(WeatherData(
                timestamp=timestamp,
                temperature_c=_safe_get(hourly, "temperature_2m", i),
                humidity_pct=_safe_get(hourly, "relative_humidity_2m", i),
                cloud_cover_pct=_safe_get(hourly, "cloud_cover", i),
                visibility_km=_safe_get(hourly, "visibility", i, default=10.0) / 1000,  # m -> km
                wind_speed_ms=_safe_get(hourly, "wind_speed_10m", i, default=0) / 3.6,  # km/h -> m/s
                wind_direction=_safe_get(hourly, "wind_direction_10m", i, default=0),
                weather_code=_safe_get(hourly, "weather_code", i, default=0),
                weather_description=WEATHER_CODE_DESCRIPTION.get(
                    _safe_get(hourly, "weather_code", i, 0), "unknown"
                ),
            ))
        
        return weather_data
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


def _safe_get(d: dict, key: str, index: int, default: Any = 0) -> Any:
    """Safely get value from list at index with default."""
    lst = d.get(key, [])
    if index < len(lst):
        return lst[index]
    return default
```

---

### 1.6 Pipeline Orchestrator

#### File: `backend/chemtrail/sources/pipeline_orchestrator.py`

**Purpose:** Orchestrate end-to-end video processing pipeline from acquisition through detection to archive.

**Key Responsibilities:**
1. Manage processing job queue
2. Execute pipeline stages in sequence
3. Handle errors and retries
4. Track progress and status
5. Integrate with existing detection_service.py

```python
# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Pipeline Orchestrator - End-to-End Workflow Coordination.

Responsibilities:
1. Coordinate acquisition -> sorting -> detection -> archive pipeline
2. Manage processing queues and priorities
3. Handle errors and retries
4. Track progress and generate reports
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import logging

logger = logging.getLogger(__name__)

# Type hints for optional dependencies
if TYPE_CHECKING:
    from .video_catalog import VideoCatalog, VideoRecord
    from .webcam_manager import WebcamManager
    from .weather_service import WeatherEnrichmentService
    from chemtrail.archive.detection_service import DetectionService


class PipelineStage(str, PyEnum):
    """Pipeline processing stages."""
    ACQUISITION = "acquisition"
    SORTING = "sorting"
    WEATHER_ENRICHMENT = "weather_enrichment"
    QUALITY_SCORING = "quality_scoring"
    CHUNKING = "chunking"
    DETECTION = "detection"
    ARCHIVAL = "archival"
    COMPLETE = "complete"


class PipelineStatus(str, PyEnum):
    """Pipeline job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class PipelineJob:
    """Represents a video processing job.
    
    Attributes:
        job_id: Unique job identifier
        video_id: Associated video ID
        source_path: Source video file path
        current_stage: Current pipeline stage
        status: Job status
        created_at: Job creation timestamp
        started_at: Job start timestamp
        completed_at: Job completion timestamp
        error_message: Error message if failed
        retry_count: Number of retry attempts
        max_retries: Maximum retry attempts
        stage_results: Results from each stage
    """
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
    """Pipeline configuration.
    
    Attributes:
        max_concurrent_jobs: Maximum concurrent processing jobs
        stage_timeout_seconds: Timeout per stage (default 300s)
        enable_weather_enrichment: Enable weather tagging
        enable_quality_scoring: Enable quality scoring
        skip_still_frames: Skip static frames during detection
        apply_overlay: Apply flight telemetry overlay
    """
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
        orchestrator = PipelineOrchestrator(config, catalog, detection_service, weather_service)
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
        video_catalog: "VideoCatalog",
        webcam_manager: Optional["WebcamManager"] = None,
        detection_service: Optional["DetectionService"] = None,
        weather_service: Optional["WeatherEnrichmentService"] = None,
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
        """Start pipeline processing with worker pool."""
        self._running = True
        
        # Start worker tasks
        for i in range(self.config.max_concurrent_jobs):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        logger.info(f"Pipeline started with {self.config.max_concurrent_jobs} workers")
    
    async def stop(self) -> None:
        """Stop pipeline processing."""
        self._running = False
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Pipeline stopped")
    
    async def submit_job(
        self,
        source_path: str,
        camera_id: Optional[str] = None,
        priority: int = 0,
    ) -> str:
        """Submit a new processing job.
        
        Args:
            source_path: Path to source video
            camera_id: Optional associated camera ID
            priority: Job priority (lower = higher priority)
            
        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())
        
        job = PipelineJob(
            job_id=job_id,
            video_id="",  # Assigned during ACQUISITION stage
            source_path=source_path,
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
        )
        
        self._jobs[job_id] = job
        await self._job_queue.put((priority, job_id))
        logger.info(f"Submitted job {job_id} for {source_path}")
        
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[PipelineJob]:
        """Get current job status."""
        return self._jobs.get(job_id)
    
    async def wait_for_job(
        self,
        job_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> PipelineJob:
        """Wait for job completion.
        
        Args:
            job_id: Job identifier
            timeout_seconds: Optional timeout
            
        Raises:
            TimeoutError: If timeout expires before completion
        """
        start_time = datetime.now(timezone.utc)
        
        while True:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            if job.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED):
                return job
            
            if timeout_seconds:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    raise TimeoutError(f"Job {job_id} timed out after {timeout_seconds}s")
            
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
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
    
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
                job.error_message = f"Stage {stage.value} timed out after {timeout}s"
                job.status = PipelineStatus.FAILED
                logger.error(f"Job {job.job_id} failed at {stage.value}: timeout")
                return
            except Exception as e:
                logger.error(f"Stage {stage.value} failed: {e}", exc_info=True)
                
                # Retry logic
                job.retry_count += 1
                if job.retry_count < job.max_retries:
                    logger.info(
                        f"Retrying stage {stage.value} ({job.retry_count}/{job.max_retries})"
                    )
                    job.current_stage = stage
                    continue
                else:
                    job.error_message = str(e)
                    job.status = PipelineStatus.FAILED
                    logger.error(f"Job {job.job_id} failed after {job.retry_count} retries")
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
            video_id = await self._acquire_video(job.source_path)
            job.video_id = video_id
            logger.info(f"Acquired video {video_id}")
        
        elif stage == PipelineStage.SORTING:
            # Sort and categorize video (metadata already set during acquisition)
            logger.debug(f"Sorting complete for job {job.job_id}")
        
        elif stage == PipelineStage.WEATHER_ENRICHMENT:
            if self.config.enable_weather_enrichment and self.weather_service:
                video = await self.video_catalog.get_by_id(job.video_id)
                if video:
                    weather_data = await self.weather_service.get_historical_weather(
                        latitude=video.latitude,
                        longitude=video.longitude,
                        start_time=video.start_time,
                        end_time=video.end_time,
                    )
                    weather_info = self.weather_service.get_weather_for_video(
                        weather_data, video.start_time, video.end_time
                    )
                    await self.video_catalog.update_weather(
                        job.video_id,
                        weather_info["condition"],
                        weather_info["cloud_cover_pct"],
                    )
                    logger.info(f"Weather enrichment complete for {job.video_id}")
        
        elif stage == PipelineStage.QUALITY_SCORING:
            if self.config.enable_quality_scoring:
                quality = self._calculate_quality_score(job.source_path)
                await self.video_catalog.update_quality(
                    job.video_id,
                    quality["overall_score"],
                    quality["resolution"],
                )
                logger.info(f"Quality scoring complete for {job.video_id}")
        
        elif stage == PipelineStage.CHUNKING:
            # Chunk video for processing using existing archive/chunker.py
            from chemtrail.archive.chunker import chunk_video
            
            chunks = chunk_video(
                job.source_path,
                chunk_duration=30,
                overlap=5,
            )
            job.stage_results["chunks"] = chunks
            logger.info(f"Chunked {job.source_path} into {len(chunks)} segments")
        
        elif stage == PipelineStage.DETECTION:
            # Run detection pipeline using existing detection_service
            if self.detection_service:
                video = await self.video_catalog.get_by_id(job.video_id)
                if video and video.camera_id:
                    # Get camera metadata from database
                    camera_metadata = await self._get_camera_metadata(video.camera_id)
                    
                    results = await self.detection_service.process_detection_batch(
                        chunks=job.stage_results["chunks"],
                        camera_id=video.camera_id,
                        camera_metadata=camera_metadata,
                        skip_still_frames=self.config.skip_still_frames,
                        apply_overlay=self.config.apply_overlay,
                    )
                    job.stage_results["detections"] = results
                    logger.info(f"Detection complete: {len(results)} detections")
        
        elif stage == PipelineStage.ARCHIVAL:
            # Detections already archived by detection_service
            # Just update job with final status
            detection_count = len(job.stage_results.get("detections", []))
            logger.info(f"Archived {detection_count} detections for job {job.job_id}")
    
    async def _acquire_video(self, source_path: str) -> str:
        """Acquire/import video into catalog."""
        import uuid
        from pathlib import Path
        from .video_catalog import VideoRecord, ProcessingStatus
        
        video_id = str(uuid.uuid4())
        path = Path(source_path)
        
        # Get basic metadata
        stat = path.stat()
        
        # Create catalog entry
        video = VideoRecord(
            id=video_id,
            source_type="historical_file",
            source_id=str(path),
            source_url="",
            camera_id=None,  # Set if known
            camera_name=None,
            latitude=0.0,  # Should be extracted from metadata
            longitude=0.0,
            altitude=0.0,
            azimuth=None,
            elevation=None,
            start_time=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            end_time=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            duration_seconds=0,  # Extract via ffprobe
            quality_score=0.0,
            resolution="unknown",
            weather_condition=None,
            cloud_cover_pct=None,
            processing_status=ProcessingStatus.PENDING,
            file_path=str(path),
            file_size_bytes=stat.st_size,
            checksum_sha256="",  # Calculate via HistoricalIngestor
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        await self.video_catalog.add_video(video)
        return video_id
    
    async def _get_camera_metadata(self, camera_id: str) -> dict:
        """Get camera metadata from database."""
        # Query chemtrail_cameras table
        row = await self.video_catalog._conn.fetchrow("""
            SELECT * FROM chemtrail_cameras WHERE id = $1
        """, camera_id)
        
        if not row:
            return {}
        
        return {
            "name": row["name"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "altitude": row["altitude"],
            "azimuth": row["azimuth"],
            "elevation": row["elevation"],
            "fov_horizontal": row.get("fov_horizontal"),
            "fov_vertical": row.get("fov_vertical"),
        }
    
    def _calculate_quality_score(self, video_path: str) -> dict:
        """Calculate video quality metrics.
        
        Uses OpenCV for analysis:
        - Resolution score (normalized to 1080p = 1.0)
        - Stability score (optical flow variance)
        - Lighting score (histogram analysis)
        - Sharpness score (Laplacian variance)
        
        Returns dict with overall_score (0-1) and component scores.
        """
        import cv2
        import numpy as np
        
        # Get video properties via cv2
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            return {
                "overall_score": 0.0,
                "resolution": "unknown",
                "resolution_score": 0.0,
                "stability_score": 0.0,
                "lighting_score": 0.0,
                "sharpness_score": 0.0,
            }
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Resolution score (normalized to 1080p = 1.0)
        target_pixels = 1920 * 1080
        actual_pixels = width * height
        resolution_score = min(1.0, actual_pixels / target_pixels)
        
        # Determine resolution string
        if height >= 2160:
            resolution = "4K"
        elif height >= 1080:
            resolution = "1080p"
        elif height >= 720:
            resolution = "720p"
        else:
            resolution = "480p"
        
        # Sample frames for analysis
        frame_indices = np.linspace(0, total_frames - 1, min(5, total_frames), dtype=int)
        
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
            
            # Stability: Compare with previous frame
            if prev_frame is not None:
                try:
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_frame, gray, None,
                        pyr_scale=0.5, levels=3, winsize=15,
                        iterations=3, poly_n=5, poly_sigma=1.2,
                        flags=0,
                    )
                    motion_magnitude = np.mean(np.linalg.norm(flow, axis=2))
                    stability = max(0, 1.0 - (motion_magnitude / 50))
                    stability_scores.append(stability)
                except cv2.error:
                    stability_scores.append(0.5)
            
            # Lighting: Histogram analysis
            mean_brightness = np.mean(gray)
            lighting = 1.0 - abs(mean_brightness - 128) / 128
            lighting_scores.append(lighting)
            
            # Sharpness: Variance of Laplacian
            try:
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                sharpness = np.var(laplacian)
                sharpness_score = min(1.0, max(0, sharpness / 500))
                sharpness_scores.append(sharpness_score)
            except cv2.error:
                sharpness_scores.append(0.5)
            
            prev_frame = gray
        
        cap.release()
        
        # Calculate averages
        stability_avg = np.mean(stability_scores) if stability_scores else 0.5
        lighting_avg = np.mean(lighting_scores) if lighting_scores else 0.5
        sharpness_avg = np.mean(sharpness_scores) if sharpness_scores else 0.5
        
        # Weighted average for overall score
        weights = {
            "resolution": 0.25,
            "stability": 0.25,
            "lighting": 0.25,
            "sharpness": 0.25,
        }
        
        overall_score = (
            weights["resolution"] * resolution_score +
            weights["stability"] * stability_avg +
            weights["lighting"] * lighting_avg +
            weights["sharpness"] * sharpness_avg
        )
        
        return {
            "overall_score": round(overall_score, 3),
            "resolution": resolution,
            "resolution_score": round(resolution_score, 3),
            "stability_score": round(stability_avg, 3),
            "lighting_score": round(lighting_avg, 3),
            "sharpness_score": round(sharpness_avg, 3),
        }
```

---

## 2. Files to Modify

### 2.1 pyproject.toml

Add yt-dlp dependency for YouTube stream ingestion:

```toml
# Add to dependencies array in backend/pyproject.toml

# Video source ingestion
yt-dlp>=2024.1.0,
```

### 2.2 db/models.py

Add VideoCatalog model to the database schema:

```python
# Add to backend/db/models.py after existing Chemtrail models

class VideoCatalog(Base):
    """
    Video catalog for Phase 2 footage management.
    
    Stores metadata for all video sources (live webcams, historical files,
    YouTube archives) with weather enrichment and quality scoring.
    """
    __tablename__ = "video_catalog"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source identification
    source_type = Column(String, nullable=False, index=True)  # live_webcam, historical_file, youtube
    source_id = Column(String, nullable=False)  # Camera ID or file path
    source_url = Column(String, nullable=True)
    
    # Location
    camera_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chemtrail_cameras.id"),
        nullable=True,
        index=True,
    )
    camera_name = Column(String, nullable=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    altitude = Column(Float, nullable=False)
    azimuth = Column(Float, nullable=True)
    elevation = Column(Float, nullable=True)
    
    # Temporal
    start_time = Column(AwareDateTime, nullable=False, index=True)
    end_time = Column(AwareDateTime, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    
    # Quality scoring
    quality_score = Column(Float, nullable=False, default=0.0, index=True)
    resolution = Column(String, nullable=False, default="unknown")
    stability_score = Column(Float, nullable=True)
    lighting_score = Column(Float, nullable=True)
    sharpness_score = Column(Float, nullable=True)
    
    # Weather enrichment
    weather_condition = Column(String, nullable=True, index=True)
    cloud_cover_pct = Column(Float, nullable=True)
    visibility_km = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    
    # Content analysis
    sky_coverage_pct = Column(Float, nullable=True)
    has_contrails = Column(Boolean, nullable=True, default=False)
    
    # Processing status
    processing_status = Column(String, nullable=False, default="pending", index=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    detection_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String, nullable=True)
    
    # Storage
    file_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    checksum_sha256 = Column(String, nullable=True, unique=True, index=True)
    thumbnail_path = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    
    __table_args__ = (
        # Composite index for common queries
        Index("idx_video_catalog_camera_time", "camera_id", "start_time"),
        Index("idx_video_catalog_quality", "quality_score", postgresql_using="btree"),
        Index("idx_video_catalog_weather", "weather_condition"),
    )
```

### 2.3 chemtrail/archive/vector_store.py

Add video catalog collection support:

```python
# Add to backend/chemtrail/archive/vector_store.py after existing collection handling

# Add to _collection_name function
def _collection_name(backend: str, model: str | None = None, collection_type: str = "detections") -> str:
    """Return ChromaDB collection name.
    
    Args:
        backend: Embedding backend (gemini, local)
        model: Model name for local backend
        collection_type: Type of collection (detections, video_catalog)
    """
    if collection_type == "video_catalog":
        return "chemtrail_video_catalog"
    
    if backend == "gemini":
        return "chemtrail_detections"
    if model:
        return f"chemtrail_detections_local_{model}"
    return "chemtrail_detections_local"
```

### 2.4 chemtrail/archive/__init__.py

Export new source modules for integration:

```python
# Add to backend/chemtrail/archive/__init__.py

# Phase 2 Sources integration
from chemtrail.sources import (
    WebcamManager,
    HistoricalIngestor,
    VideoCatalog,
    WeatherEnrichmentService,
    PipelineOrchestrator,
)

__all__ = [
    # ... existing exports ...
    
    # Phase 2 Sources
    "WebcamManager",
    "HistoricalIngestor",
    "VideoCatalog",
    "WeatherEnrichmentService",
    "PipelineOrchestrator",
]
```

---

## 3. Integration Points

### 3.1 Pipeline Orchestrator -> Detection Service

The `pipeline_orchestrator.py` calls the existing `archive/detection_service.py` for the DETECTION stage:

```python
# In PipelineOrchestrator._execute_stage() for DETECTION stage
from chemtrail.archive.detection_service import DetectionService

results = await self.detection_service.process_detection_batch(
    chunks=job.stage_results["chunks"],
    camera_id=video.camera_id,
    camera_metadata=camera_metadata,
    skip_still_frames=self.config.skip_still_frames,
    apply_overlay=self.config.apply_overlay,
)
```

### 3.2 Video Catalog -> Vector Store

The `video_catalog.py` feeds into `archive/vector_store.py` for indexing:

```python
# In VideoCatalog.add_to_chroma()
self._chroma_collection.upsert(
    ids=[video_id],
    embeddings=[embedding],
    metadatas=[metadata],
)
```

### 3.3 Webcam Manager -> Chunker

The `webcam_manager.py` captured segments feed into `archive/chunker.py` for video segmentation:

```python
# Webcam segments are captured to output_dir
# Then processed by chunker:
from chemtrail.archive.chunker import chunk_video

chunks = chunk_video(webcam_segment_path, chunk_duration=30, overlap=5)
```

---

## 4. Database Migration

Create SQL migration file at `backend/db/migrations/phase2_video_catalog.sql`:

```sql
-- Phase 2: Video Catalog Schema
-- Migration for video_catalog table

-- Create video_catalog table
CREATE TABLE IF NOT EXISTS video_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
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
    resolution VARCHAR(20) DEFAULT 'unknown',
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
    
    -- Constraints
    CONSTRAINT valid_processing_status CHECK (
        processing_status IN ('pending', 'queued', 'processing', 'completed', 'failed')
    ),
    CONSTRAINT valid_quality_score CHECK (
        quality_score >= 0.0 AND quality_score <= 1.0
    )
);

-- Indexes for common queries
CREATE INDEX idx_video_catalog_camera ON video_catalog(camera_id);
CREATE INDEX idx_video_catalog_time ON video_catalog(start_time, end_time);
CREATE INDEX idx_video_catalog_quality ON video_catalog(quality_score DESC);
CREATE INDEX idx_video_catalog_weather ON video_catalog(weather_condition);
CREATE INDEX idx_video_catalog_status ON video_catalog(processing_status);
CREATE INDEX idx_video_catalog_location ON video_catalog(latitude, longitude);
CREATE INDEX idx_video_catalog_camera_time ON video_catalog(camera_id, start_time);

-- Rollback: DROP TABLE IF EXISTS video_catalog;
```

---

## 5. Test Strategy

### 5.1 Unit Tests

Create test files in `tests/chemtrail/sources/`:

```
tests/chemtrail/sources/
├── __init__.py
├── test_webcam_manager.py
├── test_historical_ingestor.py
├── test_video_catalog.py
├── test_weather_service.py
├── test_pipeline_orchestrator.py
└── test_video_quality.py
```

#### Example: test_historical_ingestor.py

```python
"""Tests for Historical Ingestor module."""

import pytest
from pathlib import Path

from chemtrail.sources.historical_ingestor import (
    VideoScanner,
    MetadataExtractor,
    HistoricalIngestor,
    SUPPORTED_EXTENSIONS,
)


class TestVideoScanner:
    """Test video file discovery."""
    
    @pytest.mark.asyncio
    async def test_scan_directory_recursive(self, test_videos_dir):
        """Test recursive directory scanning."""
        scanner = VideoScanner()
        result = await scanner.scan(str(test_videos_dir), recursive=True)
        
        assert result.count > 0
        assert len(result.found) == result.count
        assert all(Path(p).exists() for p in result.found)
    
    @pytest.mark.asyncio
    async def test_scan_empty_directory(self, tmp_path):
        """Test scanning empty directory."""
        scanner = VideoScanner()
        result = await scanner.scan(str(tmp_path), recursive=True)
        
        assert result.count == 0
        assert result.found == []
    
    @pytest.mark.asyncio
    async def test_scan_nonexistent_directory(self):
        """Test scanning non-existent directory."""
        scanner = VideoScanner()
        
        with pytest.raises(FileNotFoundError):
            await scanner.scan("/nonexistent/path", recursive=True)
    
    def test_is_video_file(self):
        """Test video file extension check."""
        scanner = VideoScanner()
        
        assert scanner.is_video_file(Path("test.mp4"))
        assert scanner.is_video_file(Path("test.MKV"))
        assert not scanner.is_video_file(Path("test.txt"))
        assert not scanner.is_video_file(Path("test.jpg"))


class TestMetadataExtractor:
    """Test video metadata extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_metadata(self, test_video_path):
        """Test metadata extraction from video file."""
        extractor = MetadataExtractor()
        metadata = await extractor.extract(test_video_path)
        
        assert metadata.duration_seconds > 0
        assert metadata.width > 0
        assert metadata.height > 0
        assert metadata.fps > 0
        assert metadata.codec in ["h264", "hevc", "vp9", "av1", "mpeg4", "unknown"]
        assert len(metadata.checksum_sha256) == 64
    
    @pytest.mark.asyncio
    async def test_extract_nonexistent_file(self):
        """Test extraction from non-existent file."""
        extractor = MetadataExtractor()
        
        with pytest.raises(FileNotFoundError):
            await extractor.extract("/nonexistent/video.mp4")


class TestHistoricalIngestor:
    """Test historical video ingestion."""
    
    @pytest.mark.asyncio
    async def test_scan_and_import(self, test_videos_dir, temp_db_path):
        """Test full scan and import flow."""
        ingestor = HistoricalIngestor(catalog_db_path=str(temp_db_path))
        
        # Scan directory
        scan_result = await ingestor.scan_directory(str(test_videos_dir))
        assert scan_result.count > 0
        
        # Import first video
        if scan_result.found:
            video_id = await ingestor.import_video(scan_result.found[0])
            assert video_id is not None
```

### 5.2 Integration Tests

Test full pipeline flow:

```python
"""Integration tests for Phase 2 pipeline."""

import pytest
from datetime import datetime, timezone

from chemtrail.sources import (
    HistoricalIngestor,
    VideoCatalog,
    WeatherEnrichmentService,
    PipelineOrchestrator,
    PipelineConfig,
)
from chemtrail.archive.detection_service import DetectionService


class TestPhase2Integration:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline(
        self,
        test_video_path,
        db_url,
        chroma_path,
    ):
        """Test complete flow from ingestion to archive."""
        
        # Initialize catalog
        catalog = VideoCatalog(db_url=db_url, chroma_path=str(chroma_path))
        await catalog.initialize()
        
        # Ingest video
        ingestor = HistoricalIngestor(catalog_db_path=str(chroma_path))
        video_id = await ingestor.import_video(test_video_path)
        
        # Initialize services
        weather_service = WeatherEnrichmentService()
        detection_service = DetectionService()
        
        # Initialize orchestrator
        config = PipelineConfig(
            max_concurrent_jobs=2,
            enable_weather_enrichment=True,
            enable_quality_scoring=True,
        )
        orchestrator = PipelineOrchestrator(
            config=config,
            video_catalog=catalog,
            detection_service=detection_service,
            weather_service=weather_service,
        )
        
        # Start and submit job
        await orchestrator.start()
        job_id = await orchestrator.submit_job(test_video_path)
        
        # Wait for completion
        try:
            job = await orchestrator.wait_for_job(job_id, timeout_seconds=300)
            
            # Verify results
            assert job.status.value == "completed"
            assert "chunks" in job.stage_results
            assert "detections" in job.stage_results
            
        except TimeoutError:
            pytest.fail("Pipeline job timed out")
        
        finally:
            await orchestrator.stop()
            await catalog.close()
            await weather_service.close()
```

### 5.3 Mock External APIs

Mock Windy.com and Open-Meteo APIs:

```python
"""Mock external API clients for testing."""

import pytest
from unittest.mock import AsyncMock, patch

from chemtrail.sources.webcam_manager import WindyClient
from chemtrail.sources.weather_service import WeatherEnrichmentService


class MockWindyClient:
    """Mock Windy.com API client."""
    
    async def find_nearby_webcams(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50,
        categories: list = None,
    ):
        return [
            {
                "id": "test-webcam-1",
                "name": "Test Sky Cam",
                "latitude": latitude,
                "longitude": longitude,
                "url": "http://test.example.com/stream.mjpeg",
                "status": "active",
            }
        ]


class TestWeatherServiceWithMock:
    """Test weather service with mocked API."""
    
    @pytest.mark.asyncio
    async def test_get_historical_weather_cached(self):
        """Test weather fetch with caching."""
        service = WeatherEnrichmentService()
        
        # Mock HTTP client
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "hourly": {
                "time": ["2026-04-11T00:00Z", "2026-04-11T01:00Z"],
                "temperature_2m": [15.2, 14.8],
                "cloud_cover": [20, 25],
                "visibility": [10000, 10000],
                "wind_speed_10m": [5.4, 4.8],
                "weather_code": [1, 2],
            }
        }
        
        with patch.object(service._client, 'get', return_value=mock_response):
            weather = await service.get_historical_weather(
                latitude=47.6062,
                longitude=-122.3321,
                start_time=datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 11, 2, 0, tzinfo=timezone.utc),
            )
            
            assert len(weather) > 0
            assert weather[0].temperature_c == 15.2
```

### 5.4 Test Commands

```bash
# Run Phase 2 unit tests
pytest tests/chemtrail/sources/ -v

# Run with coverage
pytest tests/chemtrail/sources/ --cov=chemtrail/sources --cov-report=html

# Run integration tests
pytest tests/chemtrail/test_phase2_integration.py -v

# Run all chemtrail tests
pytest tests/chemtrail/ -v
```

---

## 6. Acceptance Criteria

### 6.1 Functional Requirements

| Requirement | Verification |
|-------------|--------------|
| Historical video import working end-to-end | Import test video, verify catalog entry |
| Webcam stream capture producing segments | Start stream, verify segment files created |
| Video catalog searchable by all filters | Test search with camera, date, quality, weather filters |
| Weather enrichment completing successfully | Import video, verify weather tags populated |
| Quality scoring returning valid scores | Score test video, verify 0-1 range |
| Pipeline orchestrator processing jobs | Submit job, verify all stages complete |

### 6.2 Quality Requirements

| Metric | Target |
|--------|--------|
| Existing tests passing | 136+ tests |
| New Phase 2 tests | 30+ tests |
| Code coverage (new modules) | >80% |
| Critical bugs | 0 |
| Documentation | Complete |

### 6.3 Performance Requirements

| Operation | Target |
|-----------|--------|
| Video metadata extraction | <10s for 1GB file |
| Quality scoring | <5s per minute of video |
| Weather enrichment | <2s per video |
| Pipeline throughput | 5+ concurrent jobs |

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ffmpeg compatibility issues | Medium | Medium | Test on all platforms, use imageio-ffmpeg fallback |
| Open-Meteo API rate limits | Low | Low | Implement caching (24h TTL) |
| RTSP stream reliability | High | Medium | Robust error handling, auto-reconnect logic |
| Quality scoring performance | Medium | Low | Optimize OpenCV operations, async processing |
| ChromaDB schema conflicts | Low | Medium | Separate collection for video catalog |

---

## 8. Handoff Checklist

- [ ] All source files created per specifications
- [ ] Database migration file created and tested
- [ ] Unit tests written and passing (30+ tests)
- [ ] Integration tests written and passing
- [ ] Mock external APIs for testing
- [ ] Code review completed
- [ ] Documentation updated in README.md
- [ ] API reference updated
- [ ] Performance validated against targets

---

*Document prepared by Software Program Manager (PMP, PgMP, SAFe)*  
*For questions or clarifications, refer to PHASE2_ARCHITECTURE.md and PHASE2_PLAN.md*
