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

"""Tests for VideoCatalog module."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from chemtrail.sources.video_catalog import (
    VideoCatalog,
    VIDEO_CATALOG_COLLECTION,
)


class TestVideoCatalogConstants:
    """Test module constants."""

    def test_collection_name(self):
        """Test collection name constant."""
        assert VIDEO_CATALOG_COLLECTION == "chemtrail_video_catalog"


class TestVideoCatalogInitialization:
    """Test VideoCatalog initialization."""

    def test_init(self):
        """Test basic initialization."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()

        catalog = VideoCatalog(mock_session, mock_vector_store)

        assert catalog.session is mock_session
        assert catalog.vector_store is mock_vector_store
        assert catalog._chroma_client is None
        assert catalog._chroma_collection is None

    @pytest.mark.asyncio
    @patch("chromadb.PersistentClient")
    async def test_initialize_with_db_path(self, mock_client_class):
        """Test initialization with ChromaDB path."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()
        mock_vector_store._db_path = "/tmp/chromadb"

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_class.return_value = mock_client

        catalog = VideoCatalog(mock_session, mock_vector_store)
        await catalog.initialize()

        assert catalog._chroma_client is not None
        assert catalog._chroma_collection is not None

    @pytest.mark.asyncio
    async def test_initialize_without_db_path(self):
        """Test initialization when vector store has no db_path."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()
        mock_vector_store._db_path = None

        catalog = VideoCatalog(mock_session, mock_vector_store)
        await catalog.initialize()

        assert catalog._chroma_client is None
        assert catalog._chroma_collection is None


class TestVideoCatalogQualityScoring:
    """Test quality scoring functionality."""

    @pytest.fixture
    def catalog(self):
        """Create VideoCatalog instance for testing."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()
        return VideoCatalog(mock_session, mock_vector_store)

    def test_calculate_quality_score_4k(self, catalog):
        """Test quality score for 4K video."""
        score = catalog.calculate_quality_score(
            resolution="4K",
            duration=300,
            file_size=500000000,
            metrics={"stability_score": 0.8, "lighting_score": 0.8},
        )
        # 4K should get max resolution score (40)
        assert score >= 40

    def test_calculate_quality_score_1080p(self, catalog):
        """Test quality score for 1080p video."""
        score = catalog.calculate_quality_score(
            resolution="1080p",
            duration=300,
            file_size=100000000,
        )
        # Should be in reasonable range
        assert 35 <= score <= 90

    def test_calculate_quality_score_720p(self, catalog):
        """Test quality score for 720p video."""
        score = catalog.calculate_quality_score(
            resolution="720p",
            duration=300,
            file_size=50000000,
        )
        assert score >= 20

    def test_calculate_quality_score_480p(self, catalog):
        """Test quality score for 480p video."""
        score = catalog.calculate_quality_score(
            resolution="480p",
            duration=300,
            file_size=20000000,
        )
        # Lower resolution should get lower score
        assert score < 60

    def test_calculate_quality_score_short_video(self, catalog):
        """Test quality score for very short video."""
        score = catalog.calculate_quality_score(
            resolution="1080p",
            duration=5,
            file_size=5000000,
        )
        # Very short videos should be penalized
        assert score < 75

    def test_calculate_quality_score_long_video(self, catalog):
        """Test quality score for very long video."""
        score = catalog.calculate_quality_score(
            resolution="1080p",
            duration=7200,
            file_size=5000000000,
        )
        # Very long videos should be penalized (lower than optimal)
        assert score < 80

    def test_calculate_quality_score_clamped(self, catalog):
        """Test that quality score is clamped to 0-100."""
        score = catalog.calculate_quality_score(
            resolution="4K",
            duration=300,
            file_size=1000000000,
            metrics={"stability_score": 1.0, "lighting_score": 1.0},
        )
        assert 0 <= score <= 100

    def test_calculate_quality_score_unknown_resolution(self, catalog):
        """Test quality score with unknown resolution."""
        score = catalog.calculate_quality_score(
            resolution="unknown",
            duration=300,
            file_size=50000000,
        )
        # Unknown resolution gets low base score
        assert score < 60

    def test_resolution_score_ordering(self, catalog):
        """Test that higher resolutions get higher scores."""
        score_4k = catalog.calculate_quality_score("4K", 300, 100000000)
        score_1080p = catalog.calculate_quality_score("1080p", 300, 100000000)
        score_720p = catalog.calculate_quality_score("720p", 300, 100000000)
        score_480p = catalog.calculate_quality_score("480p", 300, 100000000)

        assert score_4k > score_1080p > score_720p > score_480p


class TestVideoCatalogMetadataEmbedding:
    """Test metadata embedding creation."""

    @pytest.fixture
    def catalog(self):
        """Create VideoCatalog instance."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()
        return VideoCatalog(mock_session, mock_vector_store)

    def test_create_metadata_embedding(self, catalog):
        """Test embedding creation from metadata."""
        metadata = {
            "latitude": 45.0,
            "longitude": -120.0,
            "altitude": 500.0,
            "duration_seconds": 3600,
            "quality_score": 80.0,
            "resolution": "1080p",
        }

        embedding = catalog._create_metadata_embedding(metadata)

        assert isinstance(embedding, list)
        assert len(embedding) == 768

    def test_create_metadata_embedding_missing_fields(self, catalog):
        """Test embedding with missing metadata fields."""
        metadata = {"latitude": 45.0}

        embedding = catalog._create_metadata_embedding(metadata)

        assert isinstance(embedding, list)
        assert len(embedding) == 768

    def test_create_metadata_embedding_all_fields(self, catalog):
        """Test embedding with all fields."""
        metadata = {
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
            "duration_seconds": 0.0,
            "quality_score": 0.0,
            "resolution": "4K",
        }

        embedding = catalog._create_metadata_embedding(metadata)

        assert isinstance(embedding, list)
        assert len(embedding) == 768


class TestVideoCatalogRecordConversion:
    """Test record to dict conversion."""

    @pytest.fixture
    def catalog(self):
        """Create VideoCatalog instance."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()
        return VideoCatalog(mock_session, mock_vector_store)

    def test_record_to_dict(self, catalog):
        """Test converting record to dictionary."""
        mock_record = MagicMock()
        mock_record.id = "test-uuid"
        mock_record.source_type = "local"
        mock_record.source_url = None
        mock_record.local_path = "/videos/test.mp4"
        mock_record.camera_id = "camera-001"
        mock_record.camera_name = "Test Camera"
        mock_record.latitude = 47.6062
        mock_record.longitude = -122.3321
        mock_record.altitude = 100.0
        mock_record.title = "Test Video"
        mock_record.description = "Description"
        mock_record.duration_seconds = 120.5
        mock_record.resolution = "1080p"
        mock_record.codec = "h264"
        mock_record.file_size_bytes = 50000000
        mock_record.quality_score = 75.0
        mock_record.quality_metrics = {"stability": 0.8}
        mock_record.recorded_at = datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
        mock_record.ingested_at = datetime(2026, 4, 11, 13, 0, tzinfo=timezone.utc)
        mock_record.weather_data = {"temperature_c": 20.0}
        mock_record.tags = ["test"]
        mock_record.checksum_sha256 = "abc123"
        mock_record.processing_status = "pending"

        result = catalog._record_to_dict(mock_record)

        assert result["id"] == "test-uuid"
        assert result["source_type"] == "local"
        assert result["camera_id"] == "camera-001"
        assert result["quality_score"] == 75.0
        assert "test" in result["tags"]
        assert result["processing_status"] == "pending"


class TestVideoCatalogWeatherEnrichment:
    """Test weather enrichment functionality."""

    @pytest.fixture
    def catalog(self):
        """Create VideoCatalog instance."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()
        return VideoCatalog(mock_session, mock_vector_store)

    @patch("chemtrail.sources.weather_service.WeatherService")
    def test_enrich_weather_success(self, mock_weather_class, catalog):
        """Test successful weather enrichment."""
        mock_weather_service = MagicMock()
        mock_weather_service.get_historical_weather.return_value = {
            "temperature_c": 20.0,
            "weather_code": 1,
        }
        mock_weather_class.return_value = mock_weather_service

        result = catalog.enrich_weather(
            video_path="/videos/test.mp4",
            lat=47.6062,
            lon=-122.3321,
            timestamp=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
        )

        assert result["temperature_c"] == 20.0
        mock_weather_service.get_historical_weather.assert_called_once()

    @patch("chemtrail.sources.weather_service.WeatherService")
    def test_enrich_weather_error(self, mock_weather_class, catalog):
        """Test weather enrichment error handling."""
        mock_weather_service = MagicMock()
        mock_weather_service.get_historical_weather.side_effect = Exception("API error")
        mock_weather_class.return_value = mock_weather_service

        result = catalog.enrich_weather(
            video_path="/videos/test.mp4",
            lat=47.6062,
            lon=-122.3321,
            timestamp=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
        )

        assert result == {}


class TestVideoCatalogChromaDB:
    """Test ChromaDB integration."""

    @pytest.fixture
    def catalog(self):
        """Create VideoCatalog instance."""
        mock_session = MagicMock()
        mock_vector_store = MagicMock()
        return VideoCatalog(mock_session, mock_vector_store)

    def test_index_in_chromadb_not_initialized(self, catalog):
        """Test indexing when ChromaDB not initialized."""
        catalog._chroma_collection = None

        mock_record = MagicMock()

        # Should not raise, just log warning
        catalog.index_in_chromadb(mock_record)

    def test_index_in_chromadb(self, catalog):
        """Test ChromaDB indexing."""
        catalog._chroma_collection = MagicMock()

        mock_record = MagicMock()
        mock_record.id = "test-id"
        mock_record.source_type = "local"
        mock_record.camera_id = "camera-001"
        mock_record.camera_name = "Test Camera"
        mock_record.latitude = 47.6062
        mock_record.longitude = -122.3321
        mock_record.altitude = 100.0
        mock_record.duration_seconds = 120.5
        mock_record.resolution = "1080p"
        mock_record.quality_score = 75.0
        mock_record.recorded_at = datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
        mock_record.source_url = None
        mock_record.local_path = "/videos/test.mp4"

        catalog.index_in_chromadb(mock_record)

        catalog._chroma_collection.upsert.assert_called_once()
