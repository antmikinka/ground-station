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

import os
import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
import subprocess

from common.common import logger


# Supported video file extensions
SUPPORTED_FORMATS = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"]


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
    creation_date: datetime


@dataclass
class ScanResult:
    """Result of directory scan."""
    found: List[str]
    directory: str
    recursive: bool
    count: int


class VideoScanner:
    """Discover video files in directories."""

    def __init__(self, extensions: Optional[Set[str]] = None):
        self.extensions = extensions or set(SUPPORTED_FORMATS)

    def scan_directory(
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

        Raises:
            ValueError: If directory path contains traversal sequences
            FileNotFoundError: If directory doesn't exist
            NotADirectoryError: If path is not a directory
        """
        directory = Path(directory)

        # Validate path to prevent directory traversal
        resolved = directory.resolve()
        if ".." in str(resolved):
            raise ValueError(f"Invalid directory path (contains traversal): {directory}")

        if not resolved.exists():
            raise FileNotFoundError(f"Directory not found: {resolved}")

        if not resolved.is_dir():
            raise NotADirectoryError(f"Not a directory: {resolved}")

        found_files = []
        iterator = resolved.rglob("*") if recursive else resolved.iterdir()

        for path in iterator:
            if path.is_file() and path.suffix.lower() in self.extensions:
                # Verify file is within the scanned directory
                file_resolved = path.resolve()
                if str(file_resolved).startswith(str(resolved)):
                    found_files.append(str(file_resolved))

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

    def get_supported_formats(self) -> List[str]:
        """Return list of supported video formats."""
        return list(self.extensions)


class MetadataExtractor:
    """Extract video metadata using ffprobe."""

    def __init__(self):
        pass

    def extract_metadata(self, video_path: str) -> VideoMetadata:
        """Extract all metadata from video file.

        Args:
            video_path: Path to video file

        Returns:
            VideoMetadata with extracted information
        """
        path = Path(video_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {video_path}")

        # File stats
        file_size = path.stat().st_size
        creation_date = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        )

        # ffprobe metadata
        ffprobe_output = self._run_ffprobe(str(path))

        # Find video stream
        video_stream = None
        for stream in ffprobe_output.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise ValueError(f"No video stream found in {video_path}")

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
        checksum = self.compute_file_hash(video_path)

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

    def _run_ffprobe(self, file_path: str) -> dict:
        """Run ffprobe and return JSON output."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]

        result = subprocess.run(
            *cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffprobe failed for {file_path}: {result.stderr}"
            )

        return json.loads(result.stdout)

    def compute_file_hash(self, video_path: str) -> str:
        """Calculate SHA256 checksum for deduplication.

        Reads file in chunks to handle large files efficiently.
        """
        sha256 = hashlib.sha256()

        with open(video_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        return sha256.hexdigest()


class HistoricalIngestor:
    """
    Scan and import historical video files.

    Usage:
        ingestor = HistoricalIngestor(db_path="/path/to/db")
        results = await ingestor.scan_directory("/path/to/videos")

        # Import found videos
        for video_path in results.found:
            record = await ingestor.ingest_video(video_path)
    """

    def __init__(self, db_session=None, vector_store=None):
        """Initialize ingestor.

        Args:
            db_session: SQLAlchemy async session for catalog operations
            vector_store: ChromaDB vector store for indexing
        """
        self.scanner = VideoScanner()
        self.metadata_extractor = MetadataExtractor()
        self._db_session = db_session
        self._vector_store = vector_store
        self._processed_hashes: Set[str] = set()

    def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> ScanResult:
        """Scan directory for video files."""
        return self.scanner.scan_directory(directory, recursive)

    def ingest_video(
        self,
        video_path: str,
        source_type: str = "local",
        camera_id: Optional[str] = None,
        metadata_override: Optional[Dict] = None,
    ) -> Dict:
        """Ingest a video file into the catalog.

        Args:
            video_path: Path to video file
            source_type: Type of source (local, youtube, etc.)
            camera_id: Optional associated camera ID
            metadata_override: Optional metadata overrides

        Returns:
            Dict with success, data (record dict), error
        """
        try:
            # Check for duplicate first
            file_hash = self.metadata_extractor.compute_file_hash(video_path)

            if self.is_duplicate(file_hash):
                logger.info(f"Skipping duplicate video: {video_path}")
                return {
                    "success": False,
                    "error": "Duplicate file",
                    "data": None,
                }

            # Extract metadata
            metadata = self.metadata_extractor.extract_metadata(video_path)

            # Build catalog record
            record = self._build_catalog_record(
                metadata=metadata,
                source_type=source_type,
                camera_id=camera_id,
                override=metadata_override,
            )

            # Mark as processed
            self._processed_hashes.add(file_hash)

            logger.info(f"Ingested video: {video_path}")

            return {
                "success": True,
                "data": record,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error ingesting {video_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }

    def ingest_batch(
        self,
        directory_paths: List[str],
        recursive: bool = True,
        source_type: str = "local",
    ) -> List[Dict]:
        """Ingest all videos from directories.

        Args:
            directory_paths: List of directories to scan
            recursive: Whether to scan recursively
            source_type: Source type for all videos

        Returns:
            List of ingest results
        """
        results = []

        for directory in directory_paths:
            try:
                scan_result = self.scan_directory(directory, recursive)

                for video_path in scan_result.found:
                    result = self.ingest_video(video_path, source_type)
                    results.append(result)

            except Exception as e:
                logger.error(f"Error scanning {directory}: {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "data": None,
                })

        return results

    def is_duplicate(self, file_hash: str) -> bool:
        """Check if file hash has been processed."""
        return file_hash in self._processed_hashes

    def _build_catalog_record(
        self,
        metadata: VideoMetadata,
        source_type: str,
        camera_id: Optional[str],
        override: Optional[Dict],
    ) -> Dict:
        """Build catalog record from metadata."""
        import uuid

        record = {
            "id": str(uuid.uuid4()),
            "source_type": source_type,
            "local_path": metadata.file_path,
            "camera_id": camera_id,
            "latitude": 0.0,  # Should be provided or extracted
            "longitude": 0.0,
            "altitude": 0.0,
            "duration_seconds": metadata.duration_seconds,
            "resolution": self._resolution_string(metadata.width, metadata.height),
            "codec": metadata.codec,
            "file_size_bytes": metadata.file_size_bytes,
            "quality_score": 0.0,  # Calculated later
            "quality_metrics": {},
            "recorded_at": metadata.creation_date,
            "ingested_at": datetime.now(timezone.utc),
            "weather_data": {},
            "tags": [],
            "checksum_sha256": metadata.checksum_sha256,
            "processing_status": "pending",
        }

        # Apply overrides
        if override:
            record.update(override)

        return record

    def _resolution_string(self, width: int, height: int) -> str:
        """Convert dimensions to resolution string."""
        if height >= 2160:
            return "4K"
        elif height >= 1080:
            return "1080p"
        elif height >= 720:
            return "720p"
        else:
            return "480p"

    def get_supported_formats(self) -> List[str]:
        """Return list of supported video formats."""
        return self.scanner.get_supported_formats()
