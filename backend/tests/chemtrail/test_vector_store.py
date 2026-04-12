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

"""Tests for chemtrail archive vector store module."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from chemtrail.archive.vector_store import (
    ChemtrailVectorStore,
    _collection_name,
    _make_chunk_id,
    BackendMismatchError,
)


class TestCollectionName:
    """Test collection name generation."""

    def test_gemini_backend(self):
        """Test collection name for gemini backend."""
        assert _collection_name("gemini") == "chemtrail_detections"

    def test_local_backend_with_model(self):
        """Test collection name for local backend with model."""
        assert _collection_name("local", "qwen8b") == "chemtrail_detections_local_qwen8b"

    def test_local_backend_no_model(self):
        """Test collection name for local backend without model."""
        assert _collection_name("local") == "chemtrail_detections_local"


class TestMakeChunkId:
    """Test chunk ID generation."""

    def test_deterministic_id(self):
        """Test chunk ID is deterministic."""
        id1 = _make_chunk_id("test.mp4", 10.0)
        id2 = _make_chunk_id("test.mp4", 10.0)
        assert id1 == id2

    def test_different_files_different_ids(self):
        """Test different files produce different IDs."""
        id1 = _make_chunk_id("file1.mp4", 10.0)
        id2 = _make_chunk_id("file2.mp4", 10.0)
        assert id1 != id2

    def test_different_times_different_ids(self):
        """Test different times produce different IDs."""
        id1 = _make_chunk_id("test.mp4", 10.0)
        id2 = _make_chunk_id("test.mp4", 20.0)
        assert id1 != id2

    def test_id_length(self):
        """Test chunk ID is 16 characters."""
        chunk_id = _make_chunk_id("test.mp4", 10.0)
        assert len(chunk_id) == 16


class TestChemtrailVectorStore:
    """Test ChemtrailVectorStore functionality."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a test vector store."""
        store = ChemtrailVectorStore(db_path=tmp_path / "test_db", backend="gemini")
        yield store
        # Cleanup - delete all documents by getting all IDs first
        all_docs = store.collection.get(include=[])
        if all_docs["ids"]:
            store.collection.delete(ids=all_docs["ids"])

    @pytest.fixture
    def sample_embedding(self):
        """Create a sample embedding vector."""
        return [0.1] * 768

    @pytest.fixture
    def sample_detection_metadata(self):
        """Create sample detection metadata."""
        return {
            "source_file": "/path/to/video.mp4",
            "start_time": 0.0,
            "end_time": 10.0,
            "camera_id": "cam-123",
            "camera_name": "Test Camera",
            "camera_lat": 47.6062,
            "camera_lon": -122.3321,
            "camera_alt": 100.0,
            "detection_type": "contrail",
            "pixel_x": 320.0,
            "pixel_y": 240.0,
            "azimuth": 180.0,
            "elevation": 45.0,
            "confidence": 0.85,
        }

    def test_add_detection(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test adding a detection to the store."""
        chunk_id = "test_chunk_001"

        vector_store.add_detection(chunk_id, sample_embedding, sample_detection_metadata)

        # Verify retrieval
        results = vector_store.search(sample_embedding, n_results=1)
        assert len(results) == 1
        assert results[0]["source_file"] == "/path/to/video.mp4"

    def test_add_detection_missing_required_key(self, vector_store, sample_embedding):
        """Test adding detection with missing required key raises error."""
        metadata = {"source_file": "test.mp4"}  # Missing required keys

        with pytest.raises(ValueError, match="Missing required metadata"):
            vector_store.add_detection("test_id", sample_embedding, metadata)

    def test_add_detection_auto_indexed_at(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test that indexed_at is auto-added."""
        chunk_id = "test_chunk_002"

        vector_store.add_detection(chunk_id, sample_embedding, sample_detection_metadata)

        # Get the document and check indexed_at exists
        results = vector_store.collection.get(ids=[chunk_id], include=["metadatas"])
        assert "indexed_at" in results["metadatas"][0]

    def test_add_detection_with_optional_fields(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test adding detection with optional flight data."""
        sample_detection_metadata["icao24"] = "4b1a02"
        sample_detection_metadata["callsign"] = "BA2490"
        sample_detection_metadata["estimated_lat"] = 47.61
        sample_detection_metadata["estimated_lon"] = -122.34
        sample_detection_metadata["contrail_vector"] = {"angle": 45, "length_px": 100}

        chunk_id = "test_chunk_003"
        vector_store.add_detection(chunk_id, sample_embedding, sample_detection_metadata)

        results = vector_store.search(sample_embedding, n_results=1)
        assert len(results) == 1

        # Verify contrail_vector is stored (as JSON string, parsed back on read)
        # The _format_results method parses JSON back to dict
        full_results = vector_store.collection.get(ids=[chunk_id], include=["metadatas"])
        meta = full_results["metadatas"][0]
        # contrail_vector is stored as JSON string
        import json
        contrail = json.loads(meta.get("contrail_vector"))
        assert contrail["angle"] == 45

    def test_search_by_flight(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test filtering detections by flight ICAO24."""
        # Add multiple detections with different flights
        for i, icao24 in enumerate(["4b1a02", "4b1a03", "4b1a02"]):
            metadata = sample_detection_metadata.copy()
            metadata["icao24"] = icao24
            metadata["source_file"] = f"video_{i}.mp4"
            metadata["start_time"] = float(i * 10)

            vector_store.add_detection(f"chunk_{i}", sample_embedding, metadata)

        # Search by flight
        results = vector_store.search_by_flight(icao24="4b1a02", n_results=10)

        assert len(results) == 2
        for result in results:
            assert result.get("icao24") == "4b1a02"

    def test_search_by_camera(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test filtering detections by camera ID."""
        # Add detections for different cameras
        for i, camera_id in enumerate(["cam-123", "cam-456", "cam-123"]):
            metadata = sample_detection_metadata.copy()
            metadata["camera_id"] = camera_id
            metadata["source_file"] = f"video_{i}.mp4"

            vector_store.add_detection(f"chunk_{i}", sample_embedding, metadata)

        # Search by camera
        results = vector_store.search_by_camera(camera_id="cam-123", n_results=10)

        assert len(results) == 2
        for result in results:
            assert result["camera_id"] == "cam-123"

    def test_search_by_camera_with_date_range(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test filtering detections by camera and date range."""
        now = datetime.now(timezone.utc)

        # Add detections with different timestamps
        for i in range(3):
            metadata = sample_detection_metadata.copy()
            metadata["source_file"] = f"video_{i}.mp4"
            # Manually set indexed_at by modifying the metadata before add
            vector_store.add_detection(f"chunk_{i}", sample_embedding, metadata)

        # This test verifies the method exists and runs without error
        # Date filtering depends on indexed_at timestamps
        results = vector_store.search_by_camera(
            camera_id="cam-123",
            date_from=now - timedelta(days=1),
            date_to=now + timedelta(days=1),
            n_results=10,
        )

        assert isinstance(results, list)

    def test_search_by_location(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test filtering detections by geographic bounding box."""
        # Add detections with different estimated positions
        positions = [
            (47.60, -122.35),  # Inside box
            (47.61, -122.34),  # Inside box
            (48.00, -123.00),  # Outside box
        ]

        for i, (lat, lon) in enumerate(positions):
            metadata = sample_detection_metadata.copy()
            metadata["source_file"] = f"video_{i}.mp4"
            metadata["estimated_lat"] = lat
            metadata["estimated_lon"] = lon

            vector_store.add_detection(f"chunk_{i}", sample_embedding, metadata)

        # Search by location (Seattle downtown bounding box)
        results = vector_store.search_by_location(
            lat_min=47.59,
            lat_max=47.62,
            lon_min=-122.36,
            lon_max=-122.33,
            n_results=10,
        )

        # Should find the two detections inside the box
        assert len(results) >= 2

    def test_search_by_date_range(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test filtering detections by date range."""
        # Add multiple detections
        for i in range(3):
            metadata = sample_detection_metadata.copy()
            metadata["source_file"] = f"video_{i}.mp4"
            vector_store.add_detection(f"chunk_{i}", sample_embedding, metadata)

        now = datetime.now(timezone.utc)

        results = vector_store.search_by_date_range(
            date_from=now - timedelta(days=1),
            date_to=now + timedelta(days=1),
            n_results=10,
        )

        assert isinstance(results, list)

    def test_is_indexed(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test checking if a file is indexed."""
        vector_store.add_detection("chunk_001", sample_embedding, sample_detection_metadata)

        assert vector_store.is_indexed("/path/to/video.mp4") is True
        assert vector_store.is_indexed("/nonexistent/video.mp4") is False

    def test_remove_file(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test removing detections by source file."""
        # Add multiple detections for same file
        vector_store.add_detection("chunk_001", sample_embedding, sample_detection_metadata)

        metadata2 = sample_detection_metadata.copy()
        metadata2["start_time"] = 10.0
        metadata2["end_time"] = 20.0
        vector_store.add_detection("chunk_002", sample_embedding, metadata2)

        # Remove file
        removed = vector_store.remove_file("/path/to/video.mp4")

        assert removed == 2
        assert vector_store.is_indexed("/path/to/video.mp4") is False

    def test_get_stats_empty(self, vector_store):
        """Test getting stats from empty store."""
        stats = vector_store.get_stats()

        assert stats["total_chunks"] == 0
        assert stats["unique_source_files"] == 0
        assert stats["source_files"] == []

    def test_get_stats_with_data(self, vector_store, sample_embedding, sample_detection_metadata):
        """Test getting stats with data in store."""
        # Add detections
        for i in range(3):
            metadata = sample_detection_metadata.copy()
            metadata["source_file"] = f"video_{i}.mp4"
            vector_store.add_detection(f"chunk_{i}", sample_embedding, metadata)

        stats = vector_store.get_stats()

        assert stats["total_chunks"] == 3
        assert stats["unique_source_files"] == 3

    def test_get_backend(self, vector_store):
        """Test getting backend info."""
        backend = vector_store.get_backend()
        assert backend == "gemini"

    def test_check_backend_mismatch(self, vector_store):
        """Test backend mismatch detection."""
        # Store was created with "gemini" backend
        with pytest.raises(BackendMismatchError):
            vector_store.check_backend("local")

        # Should not raise for matching backend
        vector_store.check_backend("gemini")
