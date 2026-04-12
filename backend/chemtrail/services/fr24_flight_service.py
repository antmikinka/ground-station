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

"""FR24 flight data service for chemtrail tracker."""

import os
import time
from typing import Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

from common.common import logger
from ..api.fr24_client import FR24Client, FR24FlightPosition, FR24FlightSummary


@dataclass
class FR24Config:
    """FR24 service configuration."""
    api_token: Optional[str] = None
    rate_limit: int = 60  # requests per minute
    enrichment_limit: int = 50  # max flights per batch
    cache_ttl: int = 300  # seconds
    timeout: int = 30  # request timeout in seconds
    max_retries: int = 3  # max retry attempts
    rate_limit_window: float = field(default=60.0, repr=False)  # sliding window in seconds

    @classmethod
    def from_env(cls) -> "FR24Config":
        """Load configuration from environment variables."""
        return cls(
            api_token=os.environ.get("FR24_API_TOKEN"),
            rate_limit=int(os.environ.get("FR24_RATE_LIMIT", 60)),
            enrichment_limit=int(os.environ.get("FR24_ENRICHMENT_LIMIT", 50)),
            cache_ttl=int(os.environ.get("FR24_CACHE_TTL", 300)),
            timeout=int(os.environ.get("FR24_TIMEOUT", 30)),
            max_retries=int(os.environ.get("FR24_MAX_RETRIES", 3)),
        )


class FR24FlightService:
    """
    Service for fetching flight data from Flightradar24 API.

    This service is synchronous and should be called via asyncio.to_thread()
    when used from async code. It handles FR24-specific data transformation
    and correlation with the FlightCache model.

    Key responsibilities:
    - Fetch live/historic positions from FR24
    - Fetch flight summaries and tracks
    - Transform FR24 data to FlightCache-compatible format
    - Correlate FR24 hex codes with OpenSky icao24 (same format)
    """

    def __init__(self, api_token: Optional[str] = None, config: Optional[FR24Config] = None):
        """
        Initialize FR24 flight service.

        Args:
            api_token: FR24 API token (optional, falls back to env var)
            config: FR24Config instance (optional, falls back to from_env())
        """
        if config:
            self.config = config
            self.api_token = config.api_token or api_token
        else:
            self.config = FR24Config.from_env()
            self.api_token = api_token or self.config.api_token

        self.rate_limit = self.config.rate_limit
        self.enrichment_limit = self.config.enrichment_limit
        self.cache_ttl = self.config.cache_ttl
        self.timeout = self.config.timeout
        self.max_retries = self.config.max_retries

        # Rate limiting state
        self._request_timestamps: List[float] = []

    def _enforce_rate_limit(self):
        """Enforce rate limit by sleeping if necessary.

        Uses a sliding window algorithm to ensure no more than
        rate_limit requests per rate_limit_window seconds.
        """
        now = time.monotonic()
        window = self.config.rate_limit_window

        # Remove timestamps outside the current window
        self._request_timestamps = [
            ts for ts in self._request_timestamps
            if now - ts < window
        ]

        if len(self._request_timestamps) >= self.rate_limit:
            # Calculate how long to sleep
            oldest_in_window = self._request_timestamps[0]
            sleep_time = window - (now - oldest_in_window) + 0.1
            if sleep_time > 0:
                logger.warning(
                    f"FR24 rate limit reached, sleeping {sleep_time:.1f}s"
                )
                time.sleep(sleep_time)

        self._request_timestamps.append(time.monotonic())

    def validate_api_token(self) -> bool:
        """Validate FR24 API token by making test request.

        Returns:
            True if token is valid, False otherwise.
        """
        if not self.api_token:
            logger.warning("FR24 API token not configured")
            return False

        try:
            self._enforce_rate_limit()
            with FR24Client(api_token=self.api_token) as client:
                # Make minimal test request
                positions = client.get_live_positions(limit=1)
                logger.info("FR24 API token validation successful")
                return True
        except Exception as e:
            logger.error(f"FR24 API token validation failed: {e}")
            return False

    def health_check(self) -> dict:
        """Perform FR24 service health check.

        Returns:
            Health status dict:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "api_accessible": bool,
                "token_valid": bool,
                "last_check": datetime,
            }
        """
        result = {
            "status": "unhealthy",
            "api_accessible": False,
            "token_valid": False,
            "last_check": datetime.now(timezone.utc),
        }

        if not self.api_token:
            result["status"] = "degraded"
            result["api_accessible"] = True
            logger.warning("FR24 health check: API token not configured, running in degraded mode")
            return result

        try:
            token_valid = self.validate_api_token()
            result["token_valid"] = token_valid
            result["api_accessible"] = True
            result["status"] = "healthy" if token_valid else "degraded"
        except Exception as e:
            result["status"] = "unhealthy"
            logger.error(f"FR24 health check failed: {e}")

        return result

    def get_positions_near_time_and_location(
        self,
        timestamp: datetime,
        lat: float,
        lon: float,
        radius_km: float = 50.0,
        time_tolerance_seconds: int = 60,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get FR24 flight positions near a specific time and location.

        Args:
            timestamp: Target timestamp for historical query
            lat: Latitude center point
            lon: Longitude center point
            radius_km: Search radius in kilometers
            time_tolerance_seconds: Time window for historical search
            limit: Maximum results

        Returns:
            List of normalized flight position dicts
        """
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * abs(lat / 90.0) if lat != 0 else 111.0)

        bounds = {
            "north": min(lat + lat_delta, 90.0),
            "south": max(lat - lat_delta, -90.0),
            "west": lon - lon_delta,
            "east": lon + lon_delta,
        }
        # Normalize longitude wrapping
        if bounds["west"] < -180.0:
            bounds["west"] += 360.0
        if bounds["east"] > 180.0:
            bounds["east"] -= 360.0

        now = datetime.now(timezone.utc)
        time_diff = abs((now - timestamp).total_seconds())

        self._enforce_rate_limit()
        with FR24Client(api_token=self.api_token) as client:
            if time_diff > time_tolerance_seconds:
                positions = client.get_historic_positions(
                    timestamp=timestamp,
                    bounds=bounds,
                    limit=limit,
                )
            else:
                positions = client.get_live_positions(
                    bounds=bounds,
                    limit=limit,
                )

            return [self._position_to_dict(pos) for pos in positions]

    def get_flight_track(self, fr24_id: str) -> Optional[Dict]:
        """
        Get flight track for a specific flight.

        Args:
            fr24_id: FR24 flight ID (hex format)

        Returns:
            Dict with fr24_id and tracks list, or None if not found
        """
        try:
            self._enforce_rate_limit()
            with FR24Client(api_token=self.api_token) as client:
                track = client.get_flight_tracks(flight_id=fr24_id)

                if not track.tracks:
                    return None

                return {
                    "fr24_id": track.fr24_id,
                    "tracks": track.tracks,
                }
        except Exception as e:
            logger.error(f"Error fetching FR24 flight track for {fr24_id}: {e}")
            return None

    def get_flight_summary_by_hex(self, hex_code: str) -> Optional[Dict]:
        """
        Get flight summary by ICAO hex code.

        Args:
            hex_code: ICAO 24-bit hex code

        Returns:
            Dict with flight summary data, or None if not found
        """
        try:
            self._enforce_rate_limit()
            with FR24Client(api_token=self.api_token) as client:
                tracks = client.get_flight_tracks(flight_id=hex_code)

                if not tracks.tracks:
                    return None

                summaries = client.get_flight_summary(
                    flight_ids=[tracks.fr24_id],
                    limit=1,
                )

                if not summaries:
                    return None

                return self._summary_to_dict(summaries[0])
        except Exception as e:
            logger.error(f"Error fetching FR24 flight summary for {hex_code}: {e}")
            return None

    def enrich_flight_cache_entry(
        self,
        icao24: str,
        existing_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Enrich a FlightCache entry with FR24-specific data.

        Args:
            icao24: ICAO 24-bit hex code (same format in FR24 and OpenSky)
            existing_data: Existing flight data from OpenSky (optional)

        Returns:
            Dict with merged data from both sources
        """
        enriched = existing_data or {}

        # Check if we have a valid token before attempting enrichment
        if not self.api_token:
            logger.debug(f"FR24 enrichment skipped for {icao24}: no API token configured")
            return enriched

        summary = self.get_flight_summary_by_hex(icao24)
        if summary:
            enriched.update({
                "fr24_id": summary.get("fr24_id"),
                "painted_as": summary.get("painted_as"),
                "operating_as": summary.get("operating_as"),
                "origin_icao": summary.get("origin_icao"),
                "origin_iata": summary.get("origin_iata"),
                "destination_icao": summary.get("destination_icao"),
                "destination_iata": summary.get("destination_iata"),
                "datetime_takeoff": summary.get("datetime_takeoff"),
                "datetime_landed": summary.get("datetime_landed"),
                "flight_time": summary.get("flight_time"),
            })

        track = self.get_flight_track(icao24)
        if track:
            enriched["flight_track"] = track.get("tracks", [])

        return enriched

    @staticmethod
    def _position_to_dict(pos: FR24FlightPosition) -> Dict:
        """Convert FR24FlightPosition to dict for FlightCache."""
        return {
            "fr24_id": pos.fr24_id,
            "hex": pos.hex,
            "callsign": pos.callsign,
            "latitude": pos.latitude,
            "longitude": pos.longitude,
            "altitude": pos.altitude,
            "ground_speed": pos.ground_speed,
            "vertical_rate": pos.vertical_rate,
            "track": pos.track,
            "squawk": pos.squawk,
            "timestamp": pos.timestamp.isoformat(),
            "aircraft_type": pos.aircraft_type,
            "registration": pos.registration,
            "origin_icao": pos.origin_icao,
            "destination_icao": pos.destination_icao,
            "painted_as": pos.painted_as,
            "operating_as": pos.operating_as,
            "eta": pos.eta.isoformat() if pos.eta else None,
        }

    @staticmethod
    def _summary_to_dict(summary: FR24FlightSummary) -> Dict:
        """Convert FR24FlightSummary to dict."""
        return {
            "fr24_id": summary.fr24_id,
            "hex": summary.hex,
            "callsign": summary.callsign,
            "flight_number": summary.flight_number,
            "aircraft_type": summary.aircraft_type,
            "registration": summary.registration,
            "origin_icao": summary.origin_icao,
            "origin_iata": summary.origin_iata,
            "destination_icao": summary.destination_icao,
            "destination_iata": summary.destination_iata,
            "datetime_takeoff": summary.datetime_takeoff.isoformat() if summary.datetime_takeoff else None,
            "runway_takeoff": summary.runway_takeoff,
            "datetime_landed": summary.datetime_landed.isoformat() if summary.datetime_landed else None,
            "runway_landed": summary.runway_landed,
            "flight_time": summary.flight_time,
            "actual_distance": summary.actual_distance,
            "first_seen": summary.first_seen.isoformat() if summary.first_seen else None,
            "last_seen": summary.last_seen.isoformat() if summary.last_seen else None,
            "flight_ended": summary.flight_ended,
            "painted_as": summary.painted_as,
            "operating_as": summary.operating_as,
        }
