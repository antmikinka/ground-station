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

"""Tests for FR24 client and service integration."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
from dataclasses import asdict

from chemtrail.api.fr24_client import (
    FR24Client,
    FR24FlightPosition,
    FR24FlightSummary,
    FR24FlightTrack,
)
from chemtrail.services.fr24_flight_service import FR24FlightService


# ============================================================================
# FR24Client Tests
# ============================================================================


class TestFR24ClientInitialization:
    """Test FR24Client initialization and context management."""

    def test_init_with_token(self):
        client = FR24Client(api_token="test_token")
        assert client._api_token == "test_token"
        assert client._client is None

    def test_init_without_token(self):
        client = FR24Client()
        assert client._api_token is None
        assert client._client is None

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_context_manager(self, mock_base_client):
        mock_instance = MagicMock()
        mock_base_client.return_value = mock_instance

        with FR24Client(api_token="test") as client:
            assert client._client == mock_instance

        mock_instance.close.assert_called_once()

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_context_manager_exit_on_error(self, mock_base_client):
        mock_instance = MagicMock()
        mock_base_client.return_value = mock_instance

        with pytest.raises(ValueError):
            with FR24Client(api_token="test") as client:
                raise ValueError("test error")

        mock_instance.close.assert_called_once()


class TestFR24ClientMapping:
    """Test dataclass mapping methods."""

    def test_map_position_full(self):
        mock_pos = MagicMock()
        mock_pos.fr24_id = "fr24_123"
        mock_pos.hex = "4b1a02"
        mock_pos.callsign = "UAL123"
        mock_pos.lat = 40.7128
        mock_pos.lon = -74.0060
        mock_pos.alt = 35000
        mock_pos.gspeed = 450
        mock_pos.vspeed = 0
        mock_pos.track = 270
        mock_pos.squawk = "1200"
        mock_pos.timestamp = "2026-04-11T10:30:00Z"
        mock_pos.type = "B738"
        mock_pos.reg = "N12345"
        mock_pos.orig_icao = "KJFK"
        mock_pos.orig_iata = "JFK"
        mock_pos.dest_icao = "KLAX"
        mock_pos.dest_iata = "LAX"
        mock_pos.eta = "2026-04-11T14:00:00Z"
        mock_pos.painted_as = "UAL"
        mock_pos.operating_as = "UAL"

        result = FR24Client._map_position(mock_pos)

        assert isinstance(result, FR24FlightPosition)
        assert result.fr24_id == "fr24_123"
        assert result.hex == "4b1a02"
        assert result.callsign == "UAL123"
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert result.altitude == 35000
        assert result.ground_speed == 450
        assert result.vertical_rate == 0
        assert result.track == 270
        assert result.squawk == "1200"
        assert result.aircraft_type == "B738"
        assert result.registration == "N12345"
        assert result.origin_icao == "KJFK"
        assert result.origin_iata == "JFK"
        assert result.destination_icao == "KLAX"
        assert result.destination_iata == "LAX"
        assert result.painted_as == "UAL"
        assert result.operating_as == "UAL"
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.eta, datetime)

    def test_map_position_with_none_fields(self):
        mock_pos = MagicMock()
        mock_pos.fr24_id = "fr24_456"
        mock_pos.hex = None
        mock_pos.callsign = None
        mock_pos.lat = 51.4700
        mock_pos.lon = -0.4530
        mock_pos.alt = 10000
        mock_pos.gspeed = 300
        mock_pos.vspeed = 1500
        mock_pos.track = 90
        mock_pos.squawk = "7000"
        mock_pos.timestamp = "2026-04-11T10:30:00Z"
        mock_pos.type = None
        mock_pos.reg = None
        mock_pos.orig_icao = None
        mock_pos.orig_iata = None
        mock_pos.dest_icao = None
        mock_pos.dest_iata = None
        mock_pos.eta = None
        mock_pos.painted_as = None
        mock_pos.operating_as = None

        result = FR24Client._map_position(mock_pos)

        assert result.hex == ""
        assert result.callsign is None
        assert result.aircraft_type is None
        assert result.eta is None

    def test_map_position_invalid_timestamp(self):
        mock_pos = MagicMock()
        mock_pos.fr24_id = "fr24_789"
        mock_pos.hex = "abcd12"
        mock_pos.callsign = "TEST"
        mock_pos.lat = 0
        mock_pos.lon = 0
        mock_pos.alt = 0
        mock_pos.gspeed = 0
        mock_pos.vspeed = 0
        mock_pos.track = 0
        mock_pos.squawk = "0000"
        mock_pos.timestamp = "invalid"
        mock_pos.type = None
        mock_pos.reg = None
        mock_pos.orig_icao = None
        mock_pos.orig_iata = None
        mock_pos.dest_icao = None
        mock_pos.dest_iata = None
        mock_pos.eta = None
        mock_pos.painted_as = None
        mock_pos.operating_as = None

        result = FR24Client._map_position(mock_pos)
        assert isinstance(result.timestamp, datetime)

    def test_map_summary_full(self):
        mock_summary = MagicMock()
        mock_summary.fr24_id = "fr24_sum_1"
        mock_summary.hex = "a1b2c3"
        mock_summary.callsign = "BAW456"
        mock_summary.flight = "BA456"
        mock_summary.type = "A320"
        mock_summary.reg = "G-EUUA"
        mock_summary.orig_icao = "EGLL"
        mock_summary.orig_iata = "LHR"
        mock_summary.dest_icao = "LFPG"
        mock_summary.dest_iata = "CDG"
        mock_summary.datetime_takeoff = "2026-04-11T08:00:00"
        mock_summary.runway_takeoff = "27L"
        mock_summary.datetime_landed = "2026-04-11T10:30:00"
        mock_summary.runway_landed = "08R"
        mock_summary.flight_time = 9000.0
        mock_summary.actual_distance = 340.0
        mock_summary.first_seen = "2026-04-11T07:50:00"
        mock_summary.last_seen = "2026-04-11T10:35:00"
        mock_summary.flight_ended = True
        mock_summary.painted_as = "BAW"
        mock_summary.operating_as = "BAW"

        result = FR24Client._map_summary(mock_summary)

        assert isinstance(result, FR24FlightSummary)
        assert result.fr24_id == "fr24_sum_1"
        assert result.flight_number == "BA456"
        assert result.aircraft_type == "A320"
        assert result.registration == "G-EUUA"
        assert isinstance(result.datetime_takeoff, datetime)
        assert isinstance(result.datetime_landed, datetime)
        assert result.flight_time == 9000.0
        assert result.flight_ended is True

    def test_map_summary_with_none_fields(self):
        mock_summary = MagicMock()
        mock_summary.fr24_id = "fr24_sum_2"
        mock_summary.hex = None
        mock_summary.callsign = None
        mock_summary.flight = None
        mock_summary.type = None
        mock_summary.reg = None
        mock_summary.orig_icao = None
        mock_summary.orig_iata = None
        mock_summary.dest_icao = None
        mock_summary.dest_iata = None
        mock_summary.datetime_takeoff = None
        mock_summary.runway_takeoff = None
        mock_summary.datetime_landed = None
        mock_summary.runway_landed = None
        mock_summary.flight_time = None
        mock_summary.actual_distance = None
        mock_summary.first_seen = None
        mock_summary.last_seen = None
        mock_summary.flight_ended = None
        mock_summary.painted_as = None
        mock_summary.operating_as = None

        result = FR24Client._map_summary(mock_summary)

        assert result.hex == ""
        assert result.datetime_takeoff is None
        assert result.flight_ended is None


class TestFR24ClientMethods:
    """Test FR24Client method behavior with mocked SDK."""

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_live_positions_empty(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sdk.live.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        with FR24Client(api_token="test") as client:
            result = client.get_live_positions(
                bounds={"north": 52, "south": 50, "west": -1, "east": 1},
                limit=100,
            )

        assert result == []
        mock_sdk.live.get_full.assert_called_once()

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_live_positions_with_data(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_pos = MagicMock()
        mock_pos.fr24_id = "fr24_1"
        mock_pos.hex = "4b1a02"
        mock_pos.callsign = "KLM123"
        mock_pos.lat = 51.0
        mock_pos.lon = 0.0
        mock_pos.alt = 30000
        mock_pos.gspeed = 400
        mock_pos.vspeed = 0
        mock_pos.track = 180
        mock_pos.squawk = "1200"
        mock_pos.timestamp = "2026-04-11T10:00:00Z"
        mock_pos.type = "B737"
        mock_pos.reg = "PH-BXA"
        mock_pos.orig_icao = "EHAM"
        mock_pos.orig_iata = "AMS"
        mock_pos.dest_icao = "EGLL"
        mock_pos.dest_iata = "LHR"
        mock_pos.eta = None
        mock_pos.painted_as = "KLM"
        mock_pos.operating_as = "KLM"

        mock_response = MagicMock()
        mock_response.data = [mock_pos]
        mock_sdk.live.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        with FR24Client(api_token="test") as client:
            result = client.get_live_positions(limit=50)

        assert len(result) == 1
        assert result[0].hex == "4b1a02"
        assert result[0].callsign == "KLM123"

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_live_positions_raises_without_context(self, mock_base_client):
        client = FR24Client(api_token="test")
        with pytest.raises(RuntimeError, match="Client not initialized"):
            client.get_live_positions()

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_historic_positions(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sdk.historic.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        ts = datetime(2026, 4, 11, 10, 0, 0, tzinfo=timezone.utc)
        with FR24Client(api_token="test") as client:
            result = client.get_historic_positions(timestamp=ts, limit=100)

        assert result == []
        mock_sdk.historic.get_full.assert_called_once()

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_flight_tracks_empty(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sdk.flight_tracks.get.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        with FR24Client(api_token="test") as client:
            result = client.get_flight_tracks(flight_id="34242a02")

        assert result.fr24_id == "34242a02"
        assert result.tracks == []

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_flight_tracks_with_data(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_point = MagicMock()
        mock_point.timestamp = "2026-04-11T10:00:00Z"
        mock_point.lat = 51.0
        mock_point.lon = 0.0
        mock_point.alt = 30000
        mock_point.gspeed = 400
        mock_point.vspeed = 0
        mock_point.track = 180
        mock_point.squawk = "1200"

        mock_track = MagicMock()
        mock_track.fr24_id = "34242a02"
        mock_track.tracks = [mock_point]

        mock_response = MagicMock()
        mock_response.data = [mock_track]
        mock_sdk.flight_tracks.get.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        with FR24Client(api_token="test") as client:
            result = client.get_flight_tracks(flight_id="34242a02")

        assert len(result.tracks) == 1
        assert result.tracks[0]["lat"] == 51.0
        assert result.tracks[0]["alt"] == 30000

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_flight_summary_empty(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sdk.flight_summary.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        with FR24Client(api_token="test") as client:
            result = client.get_flight_summary(limit=10)

        assert result == []


# ============================================================================
# FR24FlightService Tests
# ============================================================================


class TestFR24FlightService:
    """Test FR24FlightService methods."""

    def test_init(self):
        service = FR24FlightService(api_token="test")
        assert service.api_token == "test"

    def test_init_no_token(self):
        service = FR24FlightService()
        assert service.api_token is None

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_positions_near_time_and_location_live(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_pos = MagicMock()
        mock_pos.fr24_id = "fr24_live"
        mock_pos.hex = "abc123"
        mock_pos.callsign = "TEST1"
        mock_pos.lat = 50.0
        mock_pos.lon = 10.0
        mock_pos.alt = 35000
        mock_pos.gspeed = 450
        mock_pos.vspeed = 0
        mock_pos.track = 270
        mock_pos.squawk = "1200"
        mock_pos.timestamp = "2026-04-11T10:00:00Z"
        mock_pos.type = "B738"
        mock_pos.reg = "N123"
        mock_pos.orig_icao = "KJFK"
        mock_pos.orig_iata = "JFK"
        mock_pos.dest_icao = "KLAX"
        mock_pos.dest_iata = "LAX"
        mock_pos.eta = None
        mock_pos.painted_as = "TEST"
        mock_pos.operating_as = "TEST"

        mock_response = MagicMock()
        mock_response.data = [mock_pos]
        mock_sdk.live.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        service = FR24FlightService(api_token="test")
        ts = datetime.now(timezone.utc)
        results = service.get_positions_near_time_and_location(
            timestamp=ts,
            lat=50.0,
            lon=10.0,
            radius_km=50.0,
            limit=10,
        )

        assert len(results) == 1
        assert results[0]["hex"] == "abc123"
        assert results[0]["latitude"] == 50.0
        mock_sdk.live.get_full.assert_called_once()

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_get_positions_near_time_and_location_historic(self, mock_base_client):
        mock_sdk = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sdk.historic.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        service = FR24FlightService(api_token="test")
        ts = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        results = service.get_positions_near_time_and_location(
            timestamp=ts,
            lat=50.0,
            lon=10.0,
            limit=10,
        )

        assert results == []
        mock_sdk.historic.get_full.assert_called_once()

    def test_get_flight_track_error(self):
        service = FR24FlightService(api_token="invalid")
        result = service.get_flight_track("nonexistent")
        assert result is None

    def test_get_flight_summary_by_hex_error(self):
        service = FR24FlightService(api_token="invalid")
        result = service.get_flight_summary_by_hex("nonexistent")
        assert result is None

    def test_enrich_flight_cache_entry_error(self):
        service = FR24FlightService(api_token="invalid")
        result = service.enrich_flight_cache_entry("nonexistent")
        # Should return empty dict on error, not crash
        assert isinstance(result, dict)

    def test_position_to_dict(self):
        pos = FR24FlightPosition(
            fr24_id="fr24_test",
            hex="abc123",
            callsign="TEST1",
            latitude=50.0,
            longitude=0.0,
            altitude=35000,
            ground_speed=450,
            vertical_rate=0,
            track=270,
            squawk="1200",
            timestamp=datetime(2026, 4, 11, 10, 0, 0, tzinfo=timezone.utc),
            aircraft_type="B738",
            registration="N123",
            origin_icao="KJFK",
            origin_iata="JFK",
            destination_icao="KLAX",
            destination_iata="LAX",
            eta=None,
            painted_as="TEST",
            operating_as="TEST",
        )

        result = FR24FlightService._position_to_dict(pos)

        assert result["fr24_id"] == "fr24_test"
        assert result["hex"] == "abc123"
        assert result["latitude"] == 50.0
        assert result["altitude"] == 35000
        assert result["aircraft_type"] == "B738"
        assert result["registration"] == "N123"

    def test_summary_to_dict(self):
        summary = FR24FlightSummary(
            fr24_id="fr24_sum",
            hex="def456",
            callsign="TEST2",
            flight_number="T123",
            aircraft_type="A320",
            registration="N456",
            origin_icao="KORD",
            origin_iata="ORD",
            destination_icao="KATL",
            destination_iata="ATL",
            datetime_takeoff=datetime(2026, 4, 11, 8, 0, 0, tzinfo=timezone.utc),
            runway_takeoff="10L",
            datetime_landed=datetime(2026, 4, 11, 11, 0, 0, tzinfo=timezone.utc),
            runway_landed="26R",
            flight_time=10800.0,
            actual_distance=950.0,
            first_seen=datetime(2026, 4, 11, 7, 50, 0, tzinfo=timezone.utc),
            last_seen=datetime(2026, 4, 11, 11, 5, 0, tzinfo=timezone.utc),
            flight_ended=True,
            painted_as="TEST",
            operating_as="TEST",
        )

        result = FR24FlightService._summary_to_dict(summary)

        assert result["fr24_id"] == "fr24_sum"
        assert result["flight_number"] == "T123"
        assert result["flight_time"] == 10800.0
        assert result["flight_ended"] is True
        assert "2026-04-11" in result["datetime_takeoff"]


# ============================================================================
# Dual-Source FlightService Tests
# ============================================================================


class TestDualSourceFlightService:
    """Test FlightService with FR24 integration."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_opensky_client(self):
        return AsyncMock()

    def test_merge_data_sources(self):
        from chemtrail.services.flight_service import FlightService

        # New source added to empty
        result = FlightService._merge_data_sources(None, "opensky")
        assert result == ["opensky"]

        # Duplicate source not added
        result = FlightService._merge_data_sources(["opensky"], "opensky")
        assert result == ["opensky"]

        # Multiple sources
        result = FlightService._merge_data_sources(["opensky"], "fr24")
        assert set(result) == {"opensky", "fr24"}

        # Already has both
        result = FlightService._merge_data_sources(["opensky", "fr24"], "opensky")
        assert set(result) == {"opensky", "fr24"}

    def test_merge_data_sources_order_independent(self):
        from chemtrail.services.flight_service import FlightService

        result1 = FlightService._merge_data_sources(["fr24"], "opensky")
        result2 = FlightService._merge_data_sources(["opensky"], "fr24")
        assert set(result1) == set(result2)


# ============================================================================
# DetectionService Correlation Score Tests
# ============================================================================


class TestCorrelationScore:
    """Test the correlation score calculation."""

    def test_no_flight_match(self):
        from chemtrail.archive.detection_service import DetectionService

        # Create minimal mock
        mock_detector = MagicMock()
        mock_vs = MagicMock()
        mock_fs = MagicMock()
        mock_embedder = MagicMock()

        service = DetectionService(
            session=MagicMock(),
            vector_store=mock_vs,
            flight_service=mock_fs,
            contrail_detector=mock_detector,
            embedder=mock_embedder,
        )

        score = service._calculate_correlation_score([], {}, 50.0, 0.0)
        assert score == 0.0

    def test_flight_match_no_fr24(self):
        from chemtrail.archive.detection_service import DetectionService

        mock_detector = MagicMock()
        mock_vs = MagicMock()
        mock_fs = MagicMock()
        mock_embedder = MagicMock()

        service = DetectionService(
            session=MagicMock(),
            vector_store=mock_vs,
            flight_service=mock_fs,
            contrail_detector=mock_detector,
            embedder=mock_embedder,
        )

        flight_match = [{"icao24": "abc123", "callsign": "TEST1"}]
        score = service._calculate_correlation_score(flight_match, {}, 50.0, 0.0)
        assert score == 0.7

    def test_flight_match_with_fr24_id(self):
        from chemtrail.archive.detection_service import DetectionService

        mock_detector = MagicMock()
        mock_vs = MagicMock()
        mock_fs = MagicMock()
        mock_embedder = MagicMock()

        service = DetectionService(
            session=MagicMock(),
            vector_store=mock_vs,
            flight_service=mock_fs,
            contrail_detector=mock_detector,
            embedder=mock_embedder,
        )

        flight_match = [{"icao24": "abc123"}]
        fr24_meta = {"fr24_id": "fr24_123"}
        score = service._calculate_correlation_score(flight_match, fr24_meta, 50.0, 0.0)
        assert score == 0.85

    def test_flight_match_with_track_proximity(self):
        from chemtrail.archive.detection_service import DetectionService

        mock_detector = MagicMock()
        mock_vs = MagicMock()
        mock_fs = MagicMock()
        mock_embedder = MagicMock()

        service = DetectionService(
            session=MagicMock(),
            vector_store=mock_vs,
            flight_service=mock_fs,
            contrail_detector=mock_detector,
            embedder=mock_embedder,
        )

        flight_match = [{"icao24": "abc123"}]
        fr24_meta = {
            "fr24_id": "fr24_123",
            "flight_track": [
                {"lat": 50.0, "lon": 0.0},  # Very close to est position
                {"lat": 51.0, "lon": 1.0},
            ],
        }
        score = service._calculate_correlation_score(
            flight_match, fr24_meta, 50.01, 0.01
        )
        assert score == 1.0  # 0.7 + 0.15 + 0.15

    def test_correlation_score_capped_at_1(self):
        from chemtrail.archive.detection_service import DetectionService

        mock_detector = MagicMock()
        mock_vs = MagicMock()
        mock_fs = MagicMock()
        mock_embedder = MagicMock()

        service = DetectionService(
            session=MagicMock(),
            vector_store=mock_vs,
            flight_service=mock_fs,
            contrail_detector=mock_detector,
            embedder=mock_embedder,
        )

        flight_match = [{"icao24": "abc123"}]
        fr24_meta = {
            "fr24_id": "fr24_123",
            "flight_track": [{"lat": 50.0, "lon": 0.0}],
        }
        score = service._calculate_correlation_score(
            flight_match, fr24_meta, 50.0, 0.0
        )
        assert score <= 1.0
