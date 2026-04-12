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

"""Weather Service for historical weather data.

Responsibilities:
1. Fetch historical weather from Open-Meteo API
2. Cache weather data to reduce API calls
3. Provide weather enrichment for video metadata
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import httpx

from common.common import logger


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


class WeatherService:
    """
    Fetch and cache weather data for video enrichment.

    Uses Open-Meteo Archive API (free, no key required):
    https://api.open-meteo.com/v1/archive

    Usage:
        service = WeatherService()
        weather = service.get_historical_weather(
            lat=47.6062,
            lon=-122.3321,
            timestamp=datetime(2026, 4, 11, 12, 0),
        )
    """

    ARCHIVE_API_URL = "https://api.open-meteo.com/v1/archive"
    DEFAULT_CACHE_TTL_HOURS = 24

    def __init__(self, cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS):
        self._cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
        self._cache_ttl_hours = cache_ttl_hours
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if not self._client:
            self._client = httpx.Client(timeout=10.0)
        return self._client

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()

    def get_historical_weather(
        self,
        lat: float,
        lon: float,
        timestamp: datetime,
        lookback_hours: int = 1,
    ) -> Dict[str, Any]:
        """Fetch historical weather for a time range.

        Args:
            lat: Location latitude
            lon: Location longitude
            timestamp: Target timestamp
            lookback_hours: Hours to look back for data

        Returns:
            Dict with weather data:
            - temperature_c, humidity_pct, cloud_cover_pct
            - visibility_km, wind_speed_ms, wind_direction
            - weather_code, weather_description
        """
        cache_key = self._cache_key(lat, lon, timestamp)

        # Check cache
        if cache_key in self._cache:
            cached_data, cached_at = self._cache[cache_key]
            age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
            if age_hours < self._cache_ttl_hours:
                logger.debug(f"Weather cache hit for {cache_key}")
                return cached_data

        # Fetch from API
        logger.info(f"Fetching weather for ({lat}, {lon}) at {timestamp}")

        client = self._get_client()

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": (timestamp - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d"),
            "end_date": timestamp.strftime("%Y-%m-%d"),
            "hourly": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "cloud_cover,"
                "visibility,"
                "wind_speed_10m,"
                "wind_direction_10m,"
                "weather_code"
            ),
            "timezone": "UTC",
        }

        try:
            response = client.get(self.ARCHIVE_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            # Parse hourly data
            weather_data = self._parse_hourly_data(data, timestamp)

            # Aggregate to single result
            if weather_data:
                result = self._aggregate_weather_data(weather_data)
            else:
                result = self._empty_result()

            # Cache result
            self._cache[cache_key] = (result, datetime.now(timezone.utc))
            logger.debug(f"Cached weather data for {cache_key}")

            return result

        except httpx.HTTPError as e:
            logger.error(f"Open-Meteo API error: {e}")
            return self._empty_result()

    def get_forecast(
        self,
        lat: float,
        lon: float,
        days: int = 1,
    ) -> Dict[str, Any]:
        """Get weather forecast for planning future captures.

        Args:
            lat: Location latitude
            lon: Location longitude
            days: Number of days to forecast

        Returns:
            Dict with forecast data
        """
        forecast_url = "https://api.open-meteo.com/v1/forecast"

        client = self._get_client()

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability",
            "timezone": "UTC",
            "forecast_days": days,
        }

        try:
            response = client.get(forecast_url, params=params)
            response.raise_for_status()
            data = response.json()

            return self._parse_forecast_data(data)

        except httpx.HTTPError as e:
            logger.error(f"Open-Meteo forecast error: {e}")
            return {}

    def _cache_key(self, lat: float, lon: float, timestamp: datetime) -> str:
        """Generate cache key."""
        date_str = timestamp.strftime("%Y-%m-%d")
        return f"{lat:.4f}_{lon:.4f}_{date_str}"

    def _parse_hourly_data(
        self,
        api_response: dict,
        target_timestamp: datetime,
    ) -> List[WeatherData]:
        """Parse Open-Meteo hourly response into WeatherData objects."""
        hourly = api_response.get("hourly", {})
        times = hourly.get("time", [])

        weather_data = []
        for i, time_str in enumerate(times):
            try:
                ts = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.strptime(time_str, "%Y-%m-%dT%H:%M")
                ts = ts.replace(tzinfo=timezone.utc)

            weather_data.append(WeatherData(
                timestamp=ts,
                temperature_c=self._safe_get(hourly, "temperature_2m", i, 0),
                humidity_pct=self._safe_get(hourly, "relative_humidity_2m", i, 0),
                cloud_cover_pct=self._safe_get(hourly, "cloud_cover", i, 0),
                visibility_km=self._safe_get(hourly, "visibility", i, 10000) / 1000,  # m -> km
                wind_speed_ms=self._safe_get(hourly, "wind_speed_10m", i, 0) / 3.6,  # km/h -> m/s
                wind_direction=self._safe_get(hourly, "wind_direction_10m", i, 0),
                weather_code=self._safe_get(hourly, "weather_code", i, 0),
                weather_description=WEATHER_CODE_DESCRIPTION.get(
                    self._safe_get(hourly, "weather_code", i, 0),
                    "unknown"
                ),
            ))

        return weather_data

    def _aggregate_weather_data(self, weather_data: List[WeatherData]) -> Dict[str, Any]:
        """Aggregate hourly data to single result."""
        if not weather_data:
            return self._empty_result()

        return {
            "temperature_c": round(sum(w.temperature_c for w in weather_data) / len(weather_data), 1),
            "humidity_pct": round(sum(w.humidity_pct for w in weather_data) / len(weather_data), 1),
            "cloud_cover_pct": round(sum(w.cloud_cover_pct for w in weather_data) / len(weather_data), 1),
            "visibility_km": round(sum(w.visibility_km for w in weather_data) / len(weather_data), 1),
            "wind_speed_ms": round(sum(w.wind_speed_ms for w in weather_data) / len(weather_data), 1),
            "wind_direction": round(sum(w.wind_direction for w in weather_data) / len(weather_data), 1),
            "weather_code": self._dominant_weather_code(weather_data),
            "weather_description": self._dominant_weather_description(weather_data),
        }

    def _dominant_weather_code(self, weather_data: List[WeatherData]) -> int:
        """Get most frequent weather code."""
        codes = [w.weather_code for w in weather_data]
        if not codes:
            return 0
        return max(set(codes), key=codes.count)

    def _dominant_weather_description(self, weather_data: List[WeatherData]) -> str:
        """Get most frequent weather description."""
        descriptions = [w.weather_description for w in weather_data]
        if not descriptions:
            return "unknown"
        return max(set(descriptions), key=descriptions.count)

    def _parse_forecast_data(self, api_response: dict) -> Dict[str, Any]:
        """Parse Open-Meteo forecast response."""
        daily = api_response.get("daily", {})

        forecasts = []
        times = daily.get("time", [])
        for i, date_str in enumerate(times):
            forecasts.append({
                "date": date_str,
                "weather_code": self._safe_get(daily, "weather_code", i, 0),
                "weather_description": WEATHER_CODE_DESCRIPTION.get(
                    self._safe_get(daily, "weather_code", i, 0),
                    "unknown"
                ),
                "temp_max_c": self._safe_get(daily, "temperature_2m_max", i, 0),
                "temp_min_c": self._safe_get(daily, "temperature_2m_min", i, 0),
                "precipitation_probability": self._safe_get(daily, "precipitation_probability", i, 0),
            })

        return {"forecasts": forecasts}

    def _safe_get(self, d: dict, key: str, index: int, default: Any = 0) -> Any:
        """Safely get value from list at index with default."""
        lst = d.get(key, [])
        if index < len(lst):
            return lst[index]
        return default

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty weather result."""
        return {
            "temperature_c": None,
            "humidity_pct": None,
            "cloud_cover_pct": None,
            "visibility_km": None,
            "wind_speed_ms": None,
            "wind_direction": None,
            "weather_code": None,
            "weather_description": "unknown",
        }

    def __enter__(self) -> "WeatherService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
