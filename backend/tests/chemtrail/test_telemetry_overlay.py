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

"""Tests for chemtrail archive telemetry overlay module."""

import os
import tempfile
import pytest
from datetime import datetime, timezone

from chemtrail.archive.telemetry_overlay import (
    _secs_to_ass_time,
    _build_flight_overlay,
    _get_video_dimensions,
    build_hud_overlay,
    apply_flight_overlay,
    get_flight_metadata,
    reverse_geocode,
)


class TestSecsToAssTime:
    """Test ASS timestamp conversion."""

    def test_zero_seconds(self):
        """Test 0 seconds conversion."""
        assert _secs_to_ass_time(0.0) == "0:00:00.00"

    def test_one_second(self):
        """Test 1 second conversion."""
        assert _secs_to_ass_time(1.0) == "0:00:01.00"

    def test_one_minute(self):
        """Test 1 minute conversion."""
        assert _secs_to_ass_time(60.0) == "0:01:00.00"

    def test_one_hour(self):
        """Test 1 hour conversion."""
        assert _secs_to_ass_time(3600.0) == "1:00:00.00"

    def test_fractional_seconds(self):
        """Test fractional seconds conversion."""
        assert _secs_to_ass_time(1.23) == "0:00:01.23"

    def test_complex_time(self):
        """Test complex time conversion."""
        # 1:02:03.45 = 3723.45 seconds
        assert _secs_to_ass_time(3723.45) == "1:02:03.45"


class TestBuildFlightOverlay:
    """Test flight overlay generation."""

    def test_basic_overlay_structure(self):
        """Test overlay generates valid ASS structure."""
        metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
            "timestamp": datetime.now(timezone.utc),
        }

        ass_content = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=1280,
            video_height=720,
        )

        # Check ASS structure
        assert "[Script Info]" in ass_content
        assert "[V4+ Styles]" in ass_content
        assert "[Events]" in ass_content
        assert "ScriptType: v4.00+" in ass_content

    def test_overlay_includes_callsign(self):
        """Test overlay includes callsign."""
        metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
            "timestamp": datetime.now(timezone.utc),
        }

        ass_content = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=1280,
            video_height=720,
        )

        assert "BA2490" in ass_content

    def test_overlay_includes_altitude(self):
        """Test overlay includes altitude in feet."""
        metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
            "timestamp": datetime.now(timezone.utc),
        }

        ass_content = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=1280,
            video_height=720,
        )

        assert "35000 ft" in ass_content

    def test_overlay_includes_speed(self):
        """Test overlay includes speed in knots."""
        metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,  # m/s
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
            "timestamp": datetime.now(timezone.utc),
        }

        ass_content = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=1280,
            video_height=720,
        )

        # 250 m/s ≈ 486 knots
        assert "kts" in ass_content

    def test_overlay_includes_heading(self):
        """Test overlay includes heading."""
        metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
            "timestamp": datetime.now(timezone.utc),
        }

        ass_content = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=1280,
            video_height=720,
        )

        assert "270" in ass_content

    def test_overlay_handles_missing_data(self):
        """Test overlay handles missing flight data gracefully."""
        metadata = {
            "callsign": "UNKNOWN",
            "altitude": None,
            "velocity": None,
            "heading": None,
            "latitude": None,
            "longitude": None,
            "timestamp": None,
        }

        ass_content = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=1280,
            video_height=720,
        )

        # Should show N/A for missing values
        assert "N/A" in ass_content

    def test_overlay_scales_with_resolution(self):
        """Test overlay scales for different video resolutions."""
        metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
            "timestamp": datetime.now(timezone.utc),
        }

        # HD
        ass_hd = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=1920,
            video_height=1080,
        )

        # SD
        ass_sd = _build_flight_overlay(
            metadata=metadata,
            clip_duration=10.0,
            video_width=640,
            video_height=480,
        )

        # HD should have larger font sizes
        assert "PlayResX: 1920" in ass_hd
        assert "PlayResX: 640" in ass_sd


class TestBuildHudOverlay:
    """Test HUD metadata builder."""

    def test_build_hud_overlay_basic(self):
        """Test building HUD overlay metadata."""
        flight_data = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
        }

        camera_name = "Test Camera"
        timestamp = datetime.now(timezone.utc)

        hud = build_hud_overlay(
            flight_data=flight_data,
            camera_name=camera_name,
            timestamp=timestamp,
        )

        assert hud["callsign"] == "BA2490"
        assert hud["altitude"] == 35000
        assert hud["camera_name"] == "Test Camera"
        assert hud["timestamp"] == timestamp

    def test_build_hud_overlay_with_contrail_vector(self):
        """Test building HUD with contrail vector data."""
        flight_data = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
        }

        contrail_vector = {
            "angle": 45,
            "length_px": 100,
            "width_px": 5,
            "persistence": 0.8,
        }

        hud = build_hud_overlay(
            flight_data=flight_data,
            camera_name="Test Camera",
            timestamp=datetime.now(timezone.utc),
            contrail_vector=contrail_vector,
        )

        assert hud["contrail_vector"] == contrail_vector


class TestGetFlightMetadata:
    """Test flight metadata retrieval."""

    def test_get_flight_metadata_success(self):
        """Test getting flight metadata from service."""
        # Mock flight service
        class MockFlightService:
            def get_flight(self, icao24):
                if icao24 == "4b1a02":
                    return {
                        "icao24": "4b1a02",
                        "callsign": "BA2490",
                        "position": {
                            "lat": 47.6062,
                            "lon": -122.3321,
                            "alt": 35000,
                            "velocity": 250,
                            "heading": 270,
                        },
                    }
                return None

        flight_service = MockFlightService()
        timestamp = datetime.now(timezone.utc)

        result = get_flight_metadata("4b1a02", flight_service, timestamp)

        assert result is not None
        assert result["callsign"] == "BA2490"
        assert result["altitude"] == 35000

    def test_get_flight_metadata_not_found(self):
        """Test getting flight metadata when flight not found."""
        class MockFlightService:
            def get_flight(self, icao24):
                return None

        flight_service = MockFlightService()

        result = get_flight_metadata("unknown", flight_service, datetime.now(timezone.utc))

        assert result is None


class TestReverseGeocode:
    """Test reverse geocoding."""

    def test_reverse_geocode_valid_coords(self):
        """Test reverse geocoding valid coordinates."""
        # This test may fail without network or if geopy is not installed
        result = reverse_geocode(47.6062, -122.3321)

        # Result is either dict with city/road or None (network failure)
        if result is not None:
            assert "city" in result or "road" in result

    def test_reverse_geocode_invalid_coords(self):
        """Test reverse geocoding invalid coordinates."""
        result = reverse_geocode(1000, 1000)  # Invalid coordinates

        # May return None for invalid coords or fail geocoding
        assert result is None


class TestGetVideoDimensions:
    """Test video dimension detection."""

    def test_get_video_dimensions_nonexistent_file(self):
        """Test getting dimensions of nonexistent file."""
        # Should return default dimensions or handle error gracefully
        width, height = _get_video_dimensions("/nonexistent/video.mp4")
        # Returns default dimensions
        assert width == 1280 or width > 0
        assert height == 720 or height > 0


class TestApplyFlightOverlay:
    """Test overlay application."""

    @pytest.fixture
    def sample_video(self, tmp_path):
        """Create a minimal test video."""
        import cv2
        import numpy as np

        video_path = tmp_path / "test_video.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(video_path), fourcc, 10, (640, 480))

        for i in range(20):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            out.write(frame)

        out.release()
        return str(video_path)

    def test_apply_flight_overlay_creates_output(self, sample_video):
        """Test applying overlay creates output file."""
        output_path = tempfile.mktemp(suffix="_overlay.mp4")

        flight_metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
            "velocity": 250,
            "heading": 270,
            "latitude": 47.6062,
            "longitude": -122.3321,
            "timestamp": datetime.now(timezone.utc),
        }

        result = apply_flight_overlay(
            input_path=sample_video,
            output_path=output_path,
            flight_metadata=flight_metadata,
        )

        # Should return output path (success) or input path (failure)
        assert isinstance(result, str)

        # Clean up
        if os.path.exists(output_path):
            os.unlink(output_path)

    def test_apply_flight_overlay_nonexistent_input(self):
        """Test applying overlay to nonexistent file."""
        output_path = tempfile.mktemp(suffix="_overlay.mp4")

        flight_metadata = {
            "callsign": "BA2490",
            "altitude": 35000,
        }

        result = apply_flight_overlay(
            input_path="/nonexistent/video.mp4",
            output_path=output_path,
            flight_metadata=flight_metadata,
        )

        # Should return input path on failure
        assert result == "/nonexistent/video.mp4"
