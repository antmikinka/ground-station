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

"""Tests for HistoricalIngestor module."""

import pytest
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from chemtrail.sources.historical_ingestor import (
    VideoScanner,
    MetadataExtractor,
    HistoricalIngestor,
    VideoMetadata,
    ScanResult,
    SUPPORTED_FORMATS,
)


class TestVideoScanner:
    """Test VideoScanner class."""

    @pytest.fixture
    def scanner(self):
        """Create VideoScanner instance."""
        return VideoScanner()

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory with test files."""
        # Create test video files
        (tmp_path / "video1.mp4").touch()
        (tmp_path / "video2.mov").touch()
        (tmp_path / "video3.avi").touch()
        # Create non-video files
        (tmp_path / "document.txt").touch()
        (tmp_path / "image.jpg").touch()
        # Create subdirectory with video
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "video4.mkv").touch()
        return tmp_path

    def test_scan_directory_recursive(self, scanner, temp_dir):
        """Test recursive directory scanning."""
        result = scanner.scan_directory(str(temp_dir), recursive=True)

        assert isinstance(result, ScanResult)
        assert result.count == 4
        assert result.recursive is True
        assert str(temp_dir) in result.directory

        # Check all video files found
        paths = [Path(p) for p in result.found]
        assert any(p.name == "video1.mp4" for p in paths)
        assert any(p.name == "video2.mov" for p in paths)
        assert any(p.name == "video3.avi" for p in paths)
        assert any(p.name == "video4.mkv" for p in paths)

    def test_scan_directory_non_recursive(self, scanner, temp_dir):
        """Test non-recursive directory scanning."""
        result = scanner.scan_directory(str(temp_dir), recursive=False)

        assert result.count == 3
        assert result.recursive is False

        # Should not include subdirectory video
        paths = [Path(p) for p in result.found]
        assert not any(p.name == "video4.mkv" for p in paths)

    def test_scan_directory_not_found(self, scanner):
        """Test scanning non-existent directory."""
        with pytest.raises(FileNotFoundError):
            scanner.scan_directory("/nonexistent/path")

    def test_scan_directory_not_a_directory(self, scanner, tmp_path):
        """Test scanning a file instead of directory."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with pytest.raises(NotADirectoryError):
            scanner.scan_directory(str(test_file))

    def test_is_video_file(self, scanner):
        """Test video file extension check."""
        assert scanner.is_video_file(Path("video.mp4")) is True
        assert scanner.is_video_file(Path("video.MOV")) is True
        assert scanner.is_video_file(Path("document.txt")) is False
        assert scanner.is_video_file(Path("image.jpg")) is False

    def test_is_video_file_unsupported_format(self, scanner):
        """Test unsupported video formats."""
        assert scanner.is_video_file(Path("video.wmv")) is False
        assert scanner.is_video_file(Path("video.flv")) is False

    def test_get_supported_formats(self, scanner):
        """Test getting supported formats list."""
        formats = scanner.get_supported_formats()
        assert ".mp4" in formats
        assert ".mov" in formats
        assert ".avi" in formats
        assert ".mkv" in formats
        assert ".webm" in formats
        assert ".m4v" in formats

    def test_custom_extensions(self):
        """Test scanner with custom extensions."""
        custom_extensions = {".mp4", ".mov"}
        scanner = VideoScanner(extensions=custom_extensions)

        assert scanner.is_video_file(Path("video.mp4")) is True
        assert scanner.is_video_file(Path("video.avi")) is False

    def test_scan_result_sorting(self, scanner, temp_dir):
        """Test that scan results are sorted."""
        result = scanner.scan_directory(str(temp_dir), recursive=True)

        # Results should be sorted alphabetically
        assert result.found == sorted(result.found)


class TestMetadataExtractor:
    """Test MetadataExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create MetadataExtractor instance."""
        return MetadataExtractor()

    @pytest.fixture
    def test_video(self, tmp_path):
        """Create a test video file with mocked ffprobe output."""
        video_path = tmp_path / "test.mp4"
        video_path.touch()
        return str(video_path)

    def test_extract_metadata_file_not_found(self, extractor):
        """Test extracting metadata from non-existent file."""
        with pytest.raises(FileNotFoundError):
            extractor.extract_metadata("/nonexistent/video.mp4")

    @patch("subprocess.run")
    def test_extract_metadata_success(self, mock_run, extractor, test_video):
        """Test successful metadata extraction."""
        # Mock ffprobe output
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30000/1001",
                    "duration": "10.5",
                }
            ],
            "format": {
                "duration": "10.5",
                "bit_rate": "5000000",
            },
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        metadata = extractor.extract_metadata(test_video)

        assert isinstance(metadata, VideoMetadata)
        assert metadata.file_path == test_video
        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.codec == "h264"
        assert metadata.duration_seconds == 10.5
        assert metadata.fps == pytest.approx(30.0, rel=0.1)
        assert metadata.bitrate_kbps == 5000

    @patch("subprocess.run")
    def test_extract_metadata_no_video_stream(self, mock_run, extractor, test_video):
        """Test extraction when no video stream found."""
        ffprobe_output = {
            "streams": [
                {"codec_type": "audio"}
            ],
            "format": {},
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_run.return_value = mock_result

        with pytest.raises(ValueError, match="No video stream"):
            extractor.extract_metadata(test_video)

    @patch("subprocess.run")
    def test_extract_metadata_ffprobe_failure(self, mock_run, extractor, test_video):
        """Test ffprobe command failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ffprobe error"
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError):
            extractor.extract_metadata(test_video)

    @patch("subprocess.run")
    def test_extract_metadata_fractional_fps(self, mock_run, extractor, test_video):
        """Test FPS parsing from fractional string."""
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "24000/1001",
                }
            ],
            "format": {},
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_run.return_value = mock_result

        metadata = extractor.extract_metadata(test_video)
        assert metadata.fps == pytest.approx(23.976, rel=0.01)

    @patch("subprocess.run")
    def test_extract_metadata_invalid_fps(self, mock_run, extractor, test_video):
        """Test invalid FPS string handling."""
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "invalid",
                }
            ],
            "format": {},
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_run.return_value = mock_result

        metadata = extractor.extract_metadata(test_video)
        assert metadata.fps == 0

    @patch("builtins.open", new_callable=mock_open, read_data=b"test video data")
    def test_compute_file_hash(self, mock_file, extractor, test_video):
        """Test SHA256 hash computation."""
        hash1 = extractor.compute_file_hash(test_video)

        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex length

        # Same content should produce same hash
        hash2 = extractor.compute_file_hash(test_video)
        assert hash1 == hash2

    def test_ffprobe_command_structure(self, extractor, test_video):
        """Test ffprobe command structure."""
        # Verify the command is constructed with required elements
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(test_video),
        ]
        # Verify command structure
        assert cmd[0] == "ffprobe"
        assert "-v" in cmd
        assert "quiet" in cmd
        assert "-print_format" in cmd
        assert "json" in cmd
        assert "-show_format" in cmd
        assert "-show_streams" in cmd


class TestHistoricalIngestor:
    """Test HistoricalIngestor class."""

    @pytest.fixture
    def ingestor(self):
        """Create HistoricalIngestor instance."""
        return HistoricalIngestor()

    @pytest.fixture
    def temp_video_dir(self, tmp_path):
        """Create directory with test videos."""
        (tmp_path / "video1.mp4").touch()
        (tmp_path / "video2.mov").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "video3.mkv").touch()
        return tmp_path

    def test_scan_directory(self, ingestor, temp_video_dir):
        """Test directory scanning."""
        result = ingestor.scan_directory(str(temp_video_dir), recursive=True)

        assert result.count == 3
        assert len(result.found) == 3

    @patch.object(HistoricalIngestor, "is_duplicate", return_value=False)
    @patch.object(MetadataExtractor, "extract_metadata")
    @patch.object(MetadataExtractor, "compute_file_hash", return_value="abc123")
    def test_ingest_video_success(
        self,
        mock_hash,
        mock_extract,
        mock_duplicate,
        ingestor,
        temp_video_dir,
    ):
        """Test successful video ingestion."""
        # Mock metadata
        mock_metadata = VideoMetadata(
            file_path=str(temp_video_dir / "video1.mp4"),
            file_size_bytes=1000000,
            checksum_sha256="abc123",
            duration_seconds=10.5,
            width=1920,
            height=1080,
            fps=30.0,
            codec="h264",
            bitrate_kbps=5000,
            creation_date=datetime.now(timezone.utc),
        )
        mock_extract.return_value = mock_metadata

        result = ingestor.ingest_video(str(temp_video_dir / "video1.mp4"))

        assert result["success"] is True
        assert result["data"] is not None
        assert result["error"] is None
        assert result["data"]["source_type"] == "local"
        assert result["data"]["processing_status"] == "pending"

    @patch.object(HistoricalIngestor, "is_duplicate", return_value=True)
    def test_ingest_video_duplicate(
        self,
        mock_duplicate,
        ingestor,
        temp_video_dir,
    ):
        """Test ingestion of duplicate video."""
        result = ingestor.ingest_video(str(temp_video_dir / "video1.mp4"))

        assert result["success"] is False
        assert result["error"] == "Duplicate file"
        assert result["data"] is None

    @patch.object(MetadataExtractor, "extract_metadata")
    def test_ingest_video_error(
        self,
        mock_extract,
        ingestor,
        temp_video_dir,
    ):
        """Test ingestion error handling."""
        mock_extract.side_effect = RuntimeError("Extraction failed")

        result = ingestor.ingest_video(str(temp_video_dir / "video1.mp4"))

        assert result["success"] is False
        assert "Extraction failed" in result["error"]
        assert result["data"] is None

    def test_ingest_video_custom_source_type(
        self,
        ingestor,
        temp_video_dir,
    ):
        """Test ingestion with custom source type."""
        with patch.object(HistoricalIngestor, "is_duplicate", return_value=False):
            with patch.object(MetadataExtractor, "extract_metadata") as mock_extract:
                mock_metadata = VideoMetadata(
                    file_path=str(temp_video_dir / "video1.mp4"),
                    file_size_bytes=1000000,
                    checksum_sha256="abc123",
                    duration_seconds=10.5,
                    width=1920,
                    height=1080,
                    fps=30.0,
                    codec="h264",
                    bitrate_kbps=5000,
                    creation_date=datetime.now(timezone.utc),
                )
                mock_extract.return_value = mock_metadata

                result = ingestor.ingest_video(
                    str(temp_video_dir / "video1.mp4"),
                    source_type="youtube",
                )

                assert result["success"] is True
                assert result["data"]["source_type"] == "youtube"

    def test_ingest_video_with_camera_id(
        self,
        ingestor,
        temp_video_dir,
    ):
        """Test ingestion with camera ID."""
        with patch.object(HistoricalIngestor, "is_duplicate", return_value=False):
            with patch.object(MetadataExtractor, "extract_metadata") as mock_extract:
                mock_metadata = VideoMetadata(
                    file_path=str(temp_video_dir / "video1.mp4"),
                    file_size_bytes=1000000,
                    checksum_sha256="abc123",
                    duration_seconds=10.5,
                    width=1920,
                    height=1080,
                    fps=30.0,
                    codec="h264",
                    bitrate_kbps=5000,
                    creation_date=datetime.now(timezone.utc),
                )
                mock_extract.return_value = mock_metadata

                result = ingestor.ingest_video(
                    str(temp_video_dir / "video1.mp4"),
                    camera_id="camera-001",
                )

                assert result["success"] is True
                assert result["data"]["camera_id"] == "camera-001"

    def test_ingest_video_with_override(
        self,
        ingestor,
        temp_video_dir,
    ):
        """Test ingestion with metadata override."""
        with patch.object(HistoricalIngestor, "is_duplicate", return_value=False):
            with patch.object(MetadataExtractor, "extract_metadata") as mock_extract:
                mock_metadata = VideoMetadata(
                    file_path=str(temp_video_dir / "video1.mp4"),
                    file_size_bytes=1000000,
                    checksum_sha256="abc123",
                    duration_seconds=10.5,
                    width=1920,
                    height=1080,
                    fps=30.0,
                    codec="h264",
                    bitrate_kbps=5000,
                    creation_date=datetime.now(timezone.utc),
                )
                mock_extract.return_value = mock_metadata

                override = {
                    "latitude": 47.6062,
                    "longitude": -122.3321,
                    "tags": ["test", "historical"],
                }

                result = ingestor.ingest_video(
                    str(temp_video_dir / "video1.mp4"),
                    metadata_override=override,
                )

                assert result["success"] is True
                assert result["data"]["latitude"] == 47.6062
                assert result["data"]["longitude"] == -122.3321
                assert "test" in result["data"]["tags"]

    @patch.object(HistoricalIngestor, "scan_directory")
    @patch.object(HistoricalIngestor, "ingest_video")
    def test_ingest_batch(
        self,
        mock_ingest,
        mock_scan,
        ingestor,
    ):
        """Test batch ingestion."""
        # Mock scan results - return 1 video per directory
        mock_scan.return_value = ScanResult(
            found=["/path/video1.mp4"],
            directory="/path",
            recursive=True,
            count=1,
        )

        # Mock ingest results
        mock_ingest.side_effect = [
            {"success": True, "data": {"id": "1"}, "error": None},
            {"success": False, "data": None, "error": "Error"},
        ]

        results = ingestor.ingest_batch(
            directory_paths=["/path1", "/path2"],
            recursive=True,
            source_type="local",
        )

        # Should have 2 results (one per directory)
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False

    @patch.object(HistoricalIngestor, "scan_directory")
    def test_ingest_batch_scan_error(
        self,
        mock_scan,
        ingestor,
    ):
        """Test batch ingestion with scan error."""
        mock_scan.side_effect = RuntimeError("Scan failed")

        results = ingestor.ingest_batch(
            directory_paths=["/nonexistent"],
            recursive=True,
        )

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "Scan failed" in results[0]["error"]

    def test_is_duplicate(self, ingestor):
        """Test duplicate checking."""
        # Initially not a duplicate
        assert ingestor.is_duplicate("new-hash") is False

        # Add to processed set
        ingestor._processed_hashes.add("existing-hash")

        # Now it's a duplicate
        assert ingestor.is_duplicate("existing-hash") is True
        assert ingestor.is_duplicate("new-hash") is False

    def test_resolution_string_4k(self, ingestor):
        """Test 4K resolution string."""
        result = ingestor._resolution_string(3840, 2160)
        assert result == "4K"

    def test_resolution_string_1080p(self, ingestor):
        """Test 1080p resolution string."""
        result = ingestor._resolution_string(1920, 1080)
        assert result == "1080p"

    def test_resolution_string_720p(self, ingestor):
        """Test 720p resolution string."""
        result = ingestor._resolution_string(1280, 720)
        assert result == "720p"

    def test_resolution_string_480p(self, ingestor):
        """Test 480p resolution string."""
        result = ingestor._resolution_string(640, 480)
        assert result == "480p"

    def test_resolution_string_unknown(self, ingestor):
        """Test unknown resolution string."""
        result = ingestor._resolution_string(320, 240)
        assert result == "480p"

    def test_get_supported_formats(self, ingestor):
        """Test getting supported formats from ingestor."""
        formats = ingestor.get_supported_formats()
        assert ".mp4" in formats
        assert ".mov" in formats

    def test_build_catalog_record_structure(self, ingestor, temp_video_dir):
        """Test catalog record structure."""
        with patch.object(MetadataExtractor, "extract_metadata") as mock_extract:
            mock_metadata = VideoMetadata(
                file_path=str(temp_video_dir / "video1.mp4"),
                file_size_bytes=1000000,
                checksum_sha256="abc123",
                duration_seconds=10.5,
                width=1920,
                height=1080,
                fps=30.0,
                codec="h264",
                bitrate_kbps=5000,
                creation_date=datetime.now(timezone.utc),
            )
            mock_extract.return_value = mock_metadata

            record = ingestor._build_catalog_record(
                metadata=mock_metadata,
                source_type="local",
                camera_id=None,
                override=None,
            )

            # Check required fields
            assert "id" in record
            assert record["source_type"] == "local"
            assert record["local_path"] == str(temp_video_dir / "video1.mp4")
            assert record["resolution"] == "1080p"
            assert record["codec"] == "h264"
            assert record["processing_status"] == "pending"
            assert record["weather_data"] == {}
            assert record["tags"] == []
