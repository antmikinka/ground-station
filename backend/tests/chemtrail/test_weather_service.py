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

"""Tests for WeatherService module."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from chemtrail.sources.weather_service import (
    WeatherService,
    WeatherData,
    WEATHER_CODE_DESCRIPTION,
)


class TestWeatherCodeDescription:
    """Test WMO weather code descriptions."""

    def test_clear_weather(self):
        """Test clear weather description."""
        assert WEATHER_CODE_DESCRIPTION[0] == "clear"

    def test_cloudy_weather(self):
        """Test cloudy weather descriptions."""
        assert WEATHER_CODE_DESCRIPTION[1] == "mainly_clear"
        assert WEATHER_CODE_DESCRIPTION[2] == "partly_cloudy"
        assert WEATHER_CODE_DESCRIPTION[3] == "overcast"

    def test_precipitation_weather(self):
        """Test precipitation weather descriptions."""
        assert WEATHER_CODE_DESCRIPTION[51] == "light_drizzle"
        assert WEATHER_CODE_DESCRIPTION[61] == "light_rain"
        assert WEATHER_CODE_DESCRIPTION[71] == "light_snow"

    def test_thunderstorm_weather(self):
        """Test thunderstorm weather descriptions."""
        assert WEATHER_CODE_DESCRIPTION[95] == "thunderstorm"
        assert WEATHER_CODE_DESCRIPTION[96] == "thunderstorm_hail"


class TestWeatherData:
    """Test WeatherData dataclass."""

    def test_weather_data_creation(self):
        """Test creating WeatherData instance."""
        timestamp = datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
        weather = WeatherData(
            timestamp=timestamp,
            temperature_c=22.5,
            humidity_pct=65.0,
            cloud_cover_pct=30.0,
            visibility_km=10.0,
            wind_speed_ms=5.5,
            wind_direction=180.0,
            weather_code=1,
            weather_description="mainly_clear",
        )

        assert weather.temperature_c == 22.5
        assert weather.humidity_pct == 65.0
        assert weather.weather_code == 1


class TestWeatherService:
    """Test WeatherService class."""

    @pytest.fixture
    def service(self):
        """Create WeatherService instance."""
        return WeatherService()

    @pytest.fixture
    def sample_location(self):
        """Sample location coordinates."""
        return {"lat": 47.6062, "lon": -122.3321}

    @pytest.fixture
    def sample_timestamp(self):
        """Sample timestamp."""
        return datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)

    def test_default_cache_ttl(self):
        """Test default cache TTL."""
        service = WeatherService()
        assert service._cache_ttl_hours == 24

    def test_custom_cache_ttl(self):
        """Test custom cache TTL."""
        service = WeatherService(cache_ttl_hours=48)
        assert service._cache_ttl_hours == 48

    def test_cache_key_generation(self, service, sample_location, sample_timestamp):
        """Test cache key generation."""
        key = service._cache_key(
            sample_location["lat"],
            sample_location["lon"],
            sample_timestamp,
        )

        assert "47.6062" in key
        assert "-122.3321" in key
        assert "2026-04-11" in key

    @patch("httpx.Client")
    def test_get_historical_weather_cache_miss(
        self, mock_client_class, service, sample_location, sample_timestamp
    ):
        """Test fetching weather when cache miss."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hourly": {
                "time": ["2026-04-11T11:00", "2026-04-11T12:00"],
                "temperature_2m": [20.0, 22.0],
                "relative_humidity_2m": [60, 65],
                "cloud_cover": [20, 30],
                "visibility": [10000, 10000],
                "wind_speed_10m": [10.8, 14.4],
                "wind_direction_10m": [180, 185],
                "weather_code": [1, 1],
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = service.get_historical_weather(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            timestamp=sample_timestamp,
        )

        assert result["temperature_c"] is not None
        assert result["weather_code"] is not None

        # Verify API was called
        mock_client.get.assert_called_once()

    @patch("httpx.Client")
    def test_get_historical_weather_cache_hit(
        self, mock_client_class, service, sample_location, sample_timestamp
    ):
        """Test fetching weather when cache hit."""
        # Mock API response for first call
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hourly": {
                "time": ["2026-04-11T11:00", "2026-04-11T12:00"],
                "temperature_2m": [20.0, 22.0],
                "relative_humidity_2m": [60, 65],
                "cloud_cover": [20, 30],
                "visibility": [10000, 10000],
                "wind_speed_10m": [10.8, 14.4],
                "wind_direction_10m": [180, 185],
                "weather_code": [1, 1],
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # First call - cache miss
        result1 = service.get_historical_weather(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            timestamp=sample_timestamp,
        )

        # Second call - cache hit
        result2 = service.get_historical_weather(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            timestamp=sample_timestamp,
        )

        # Results should be the same (cached)
        assert result1["temperature_c"] == result2["temperature_c"]

        # API should only be called once
        mock_client.get.assert_called_once()

    @patch("httpx.Client")
    def test_get_historical_weather_cache_expired(
        self, mock_client_class, service, sample_location, sample_timestamp
    ):
        """Test fetching weather when cache expired."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hourly": {
                "time": ["2026-04-11T11:00", "2026-04-11T12:00"],
                "temperature_2m": [20.0, 22.0],
                "relative_humidity_2m": [60, 65],
                "cloud_cover": [20, 30],
                "visibility": [10000, 10000],
                "wind_speed_10m": [10.8, 14.4],
                "wind_direction_10m": [180, 185],
                "weather_code": [1, 1],
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # First call
        service.get_historical_weather(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            timestamp=sample_timestamp,
        )

        # Expire cache by setting old timestamp
        cache_key = service._cache_key(
            sample_location["lat"],
            sample_location["lon"],
            sample_timestamp,
        )
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        service._cache[cache_key] = (service._cache[cache_key][0], old_time)

        # Second call - cache expired
        service.get_historical_weather(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            timestamp=sample_timestamp,
        )

        # API should be called twice (cache expired)
        assert mock_client.get.call_count == 2

    @patch("httpx.Client")
    def test_get_historical_weather_http_error(
        self, mock_client_class, service, sample_location, sample_timestamp
    ):
        """Test handling HTTP errors."""
        import httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPError("Connection error")
        mock_client_class.return_value = mock_client

        result = service.get_historical_weather(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            timestamp=sample_timestamp,
        )

        # Should return empty result, not raise
        assert result["temperature_c"] is None
        assert result["weather_description"] == "unknown"

    @patch("httpx.Client")
    def test_get_historical_weather_empty_response(
        self, mock_client_class, service, sample_location, sample_timestamp
    ):
        """Test handling empty API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"hourly": {"time": []}}
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = service.get_historical_weather(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            timestamp=sample_timestamp,
        )

        assert result["temperature_c"] is None
        assert result["weather_description"] == "unknown"

    @patch("httpx.Client")
    def test_get_forecast_success(self, mock_client_class, service, sample_location):
        """Test weather forecast fetching."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "daily": {
                "time": ["2026-04-11", "2026-04-12"],
                "weather_code": [1, 2],
                "temperature_2m_max": [22.0, 24.0],
                "temperature_2m_min": [12.0, 14.0],
                "precipitation_probability": [10, 20],
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = service.get_forecast(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            days=2,
        )

        assert "forecasts" in result
        assert len(result["forecasts"]) == 2
        assert result["forecasts"][0]["temp_max_c"] == 22.0

    @patch("httpx.Client")
    def test_get_forecast_http_error(self, mock_client_class, service, sample_location):
        """Test forecast error handling."""
        import httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPError("API error")
        mock_client_class.return_value = mock_client

        result = service.get_forecast(
            lat=sample_location["lat"],
            lon=sample_location["lon"],
            days=1,
        )

        assert result == {}

    def test_safe_get_existing_value(self, service):
        """Test safe_get with existing value."""
        data = {"key": [1, 2, 3]}
        result = service._safe_get(data, "key", 1, default=0)
        assert result == 2

    def test_safe_get_missing_key(self, service):
        """Test safe_get with missing key."""
        data = {"other": [1, 2, 3]}
        result = service._safe_get(data, "key", 0, default=99)
        assert result == 99

    def test_safe_get_index_out_of_range(self, service):
        """Test safe_get with index out of range."""
        data = {"key": [1, 2]}
        result = service._safe_get(data, "key", 10, default=99)
        assert result == 99

    def test_safe_get_default_value(self, service):
        """Test safe_get default value."""
        data = {}
        result = service._safe_get(data, "key", 0)
        assert result == 0

    def test_empty_result(self, service):
        """Test empty result structure."""
        result = service._empty_result()

        assert result["temperature_c"] is None
        assert result["humidity_pct"] is None
        assert result["cloud_cover_pct"] is None
        assert result["visibility_km"] is None
        assert result["wind_speed_ms"] is None
        assert result["wind_direction"] is None
        assert result["weather_code"] is None
        assert result["weather_description"] == "unknown"

    def test_context_manager(self):
        """Test context manager support."""
        with WeatherService() as svc:
            assert isinstance(svc, WeatherService)

    def test_close_method(self, service):
        """Test close method."""
        # Create client
        service._client = MagicMock()
        service.close()

        # Client should be closed
        service._client.close.assert_called_once()

    def test_parse_hourly_data(self, service, sample_timestamp):
        """Test parsing hourly API response."""
        api_response = {
            "hourly": {
                "time": ["2026-04-11T11:00", "2026-04-11T12:00"],
                "temperature_2m": [20.0, 22.0],
                "relative_humidity_2m": [60, 65],
                "cloud_cover": [20, 30],
                "visibility": [10000, 10000],
                "wind_speed_10m": [10.8, 14.4],
                "wind_direction_10m": [180, 185],
                "weather_code": [1, 2],
            }
        }

        result = service._parse_hourly_data(api_response, sample_timestamp)

        assert len(result) == 2
        assert result[0].temperature_c == 20.0
        assert result[1].temperature_c == 22.0
        assert result[0].humidity_pct == 60
        assert result[1].humidity_pct == 65

    def test_aggregate_weather_data(self, service):
        """Test aggregating hourly weather data."""
        weather_data = [
            WeatherData(
                timestamp=datetime(2026, 4, 11, 11, 0, tzinfo=timezone.utc),
                temperature_c=20.0,
                humidity_pct=60.0,
                cloud_cover_pct=20.0,
                visibility_km=10.0,
                wind_speed_ms=3.0,
                wind_direction=180.0,
                weather_code=1,
                weather_description="mainly_clear",
            ),
            WeatherData(
                timestamp=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
                temperature_c=22.0,
                humidity_pct=65.0,
                cloud_cover_pct=30.0,
                visibility_km=10.0,
                wind_speed_ms=4.0,
                wind_direction=185.0,
                weather_code=2,
                weather_description="partly_cloudy",
            ),
        ]

        result = service._aggregate_weather_data(weather_data)

        assert result["temperature_c"] == 21.0  # Average
        assert result["humidity_pct"] == 62.5  # Average
        assert result["cloud_cover_pct"] == 25.0  # Average

    def test_dominant_weather_code(self, service):
        """Test finding dominant weather code."""
        weather_data = [
            WeatherData(
                timestamp=datetime(2026, 4, 11, 11, 0, tzinfo=timezone.utc),
                temperature_c=20.0,
                humidity_pct=60.0,
                cloud_cover_pct=20.0,
                visibility_km=10.0,
                wind_speed_ms=3.0,
                wind_direction=180.0,
                weather_code=1,
                weather_description="mainly_clear",
            ),
            WeatherData(
                timestamp=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
                temperature_c=22.0,
                humidity_pct=65.0,
                cloud_cover_pct=30.0,
                visibility_km=10.0,
                wind_speed_ms=4.0,
                wind_direction=185.0,
                weather_code=1,
                weather_description="mainly_clear",
            ),
            WeatherData(
                timestamp=datetime(2026, 4, 11, 13, 0, tzinfo=timezone.utc),
                temperature_c=23.0,
                humidity_pct=70.0,
                cloud_cover_pct=40.0,
                visibility_km=9.0,
                wind_speed_ms=5.0,
                wind_direction=190.0,
                weather_code=2,
                weather_description="partly_cloudy",
            ),
        ]

        dominant = service._dominant_weather_code(weather_data)
        assert dominant == 1  # Most frequent

    def test_dominant_weather_description(self, service):
        """Test finding dominant weather description."""
        weather_data = [
            WeatherData(
                timestamp=datetime(2026, 4, 11, 11, 0, tzinfo=timezone.utc),
                temperature_c=20.0,
                humidity_pct=60.0,
                cloud_cover_pct=20.0,
                visibility_km=10.0,
                wind_speed_ms=3.0,
                wind_direction=180.0,
                weather_code=1,
                weather_description="clear",
            ),
            WeatherData(
                timestamp=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
                temperature_c=22.0,
                humidity_pct=65.0,
                cloud_cover_pct=30.0,
                visibility_km=10.0,
                wind_speed_ms=4.0,
                wind_direction=185.0,
                weather_code=1,
                weather_description="clear",
            ),
            WeatherData(
                timestamp=datetime(2026, 4, 11, 13, 0, tzinfo=timezone.utc),
                temperature_c=23.0,
                humidity_pct=70.0,
                cloud_cover_pct=40.0,
                visibility_km=9.0,
                wind_speed_ms=5.0,
                wind_direction=190.0,
                weather_code=2,
                weather_description="cloudy",
            ),
        ]

        dominant = service._dominant_weather_description(weather_data)
        assert dominant == "clear"  # Most frequent

    def test_parse_forecast_data(self, service):
        """Test parsing forecast API response."""
        api_response = {
            "daily": {
                "time": ["2026-04-11", "2026-04-12"],
                "weather_code": [1, 2],
                "temperature_2m_max": [22.0, 24.0],
                "temperature_2m_min": [12.0, 14.0],
                "precipitation_probability": [10, 20],
            }
        }

        result = service._parse_forecast_data(api_response)

        assert "forecasts" in result
        assert len(result["forecasts"]) == 2
        assert result["forecasts"][0]["date"] == "2026-04-11"
        assert result["forecasts"][0]["weather_code"] == 1
        assert result["forecasts"][0]["precipitation_probability"] == 10

    def test_wind_speed_conversion(self, service):
        """Test wind speed conversion from km/h to m/s."""
        api_response = {
            "hourly": {
                "time": ["2026-04-11T12:00"],
                "wind_speed_10m": [36.0],  # 36 km/h = 10 m/s
                "wind_direction_10m": [180],
                "weather_code": [0],
            }
        }

        result = service._parse_hourly_data(
            api_response, datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
        )

        assert result[0].wind_speed_ms == 10.0

    def test_visibility_conversion(self, service):
        """Test visibility conversion from meters to kilometers."""
        api_response = {
            "hourly": {
                "time": ["2026-04-11T12:00"],
                "visibility": [5000],  # 5000m = 5km
                "weather_code": [0],
            }
        }

        result = service._parse_hourly_data(
            api_response, datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
        )

        assert result[0].visibility_km == 5.0

    def test_isoformat_timestamp_parsing(self, service):
        """Test parsing ISO format timestamps with Z suffix."""
        api_response = {
            "hourly": {
                "time": ["2026-04-11T12:00Z"],
                "weather_code": [0],
            }
        }

        result = service._parse_hourly_data(
            api_response, datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
        )

        assert result[0].timestamp is not None

    def test_standard_timestamp_parsing(self, service):
        """Test parsing standard ISO format timestamps."""
        api_response = {
            "hourly": {
                "time": ["2026-04-11T12:00"],
                "weather_code": [0],
            }
        }

        result = service._parse_hourly_data(
            api_response, datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
        )

        assert result[0].timestamp is not None
