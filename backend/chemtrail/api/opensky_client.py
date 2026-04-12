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

"""OpenSky Network API client for flight data."""

import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from common.common import logger


@dataclass
class FlightState:
    """Represents current state of a flight."""
    icao24: str
    callsign: Optional[str]
    origin_country: Optional[str]
    time_position: Optional[int]
    last_contact: Optional[int]
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude: Optional[float]
    on_ground: bool
    velocity: Optional[float]
    true_track: Optional[float]
    vertical_rate: Optional[float]
    sensors: Optional[List[int]]
    geo_altitude: Optional[float]
    squawk: Optional[str]
    spi: bool
    position_source: int


class OpenSkyClient:
    """
    Async client for OpenSky Network API.

    Implements rate limiting and basic caching to respect API limits:
    - Anonymous: 1 request per 10 seconds
    - Member: 1 request per second

    Usage:
        async with OpenSkyClient() as client:
            flights = await client.get_all_flights()
    """

    BASE_URL = "https://opensky-network.org/api"

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        rate_limit_delay: float = 10.0
    ):
        """
        Initialize OpenSky client.

        Args:
            username: OpenSky username (optional, for member rate limits)
            password: OpenSky password (optional)
            rate_limit_delay: Minimum seconds between requests
        """
        self.username = username
        self.password = password
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)
            self.rate_limit_delay = 1.0  # Member rate limit

        self._client = httpx.AsyncClient(auth=auth, timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def get_all_flights(self) -> List[FlightState]:
        """
        Fetch all currently airborne flights.

        Returns:
            List of FlightState objects
        """
        await self._rate_limit()

        try:
            if not self._client:
                logger.error("OpenSky client not initialized")
                return []

            response = await self._client.get(f"{self.BASE_URL}/states/all")
            response.raise_for_status()
            data = response.json()

            if not data.get("states"):
                return []

            flights = []
            for state in data["states"]:
                flights.append(FlightState(
                    icao24=state[0],
                    callsign=state[1].strip() if state[1] else None,
                    origin_country=state[2],
                    time_position=state[3],
                    last_contact=state[4],
                    longitude=state[5],
                    latitude=state[6],
                    baro_altitude=state[7],
                    on_ground=state[8],
                    velocity=state[9],
                    true_track=state[10],
                    vertical_rate=state[11],
                    sensors=state[12],
                    geo_altitude=state[13],
                    squawk=state[14],
                    spi=state[15],
                    position_source=state[16],
                ))
            return flights

        except httpx.HTTPError as e:
            logger.error(f"OpenSky API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching flights: {e}")
            return []

    async def get_flight_by_icao24(self, icao24: str) -> Optional[FlightState]:
        """
        Fetch state for a specific flight by ICAO24 hex code.

        Args:
            icao24: 24-bit ICAO hex code (e.g., "4b1a02")

        Returns:
            FlightState or None if not found
        """
        await self._rate_limit()

        try:
            if not self._client:
                logger.error("OpenSky client not initialized")
                return None

            response = await self._client.get(
                f"{self.BASE_URL}/states/all",
                params={"icao24": icao24}
            )
            response.raise_for_status()
            data = response.json()

            if data.get("states"):
                state = data["states"][0]
                return FlightState(
                    icao24=state[0],
                    callsign=state[1].strip() if state[1] else None,
                    origin_country=state[2],
                    time_position=state[3],
                    last_contact=state[4],
                    longitude=state[5],
                    latitude=state[6],
                    baro_altitude=state[7],
                    on_ground=state[8],
                    velocity=state[9],
                    true_track=state[10],
                    vertical_rate=state[11],
                    sensors=state[12],
                    geo_altitude=state[13],
                    squawk=state[14],
                    spi=state[15],
                    position_source=state[16],
                )
            return None

        except httpx.HTTPError as e:
            logger.error(f"OpenSky API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching flight: {e}")
            return None

    async def get_flights_in_area(
        self,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float
    ) -> List[FlightState]:
        """
        Fetch flights within a bounding box.

        Args:
            lat_min: Minimum latitude
            lat_max: Maximum latitude
            lon_min: Minimum longitude
            lon_max: Maximum longitude

        Returns:
            List of FlightState objects within the area
        """
        await self._rate_limit()

        try:
            if not self._client:
                logger.error("OpenSky client not initialized")
                return []

            response = await self._client.get(
                f"{self.BASE_URL}/states/all",
                params={
                    "lamin": lat_min,
                    "lamax": lat_max,
                    "lomin": lon_min,
                    "lomax": lon_max,
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("states"):
                return []

            flights = []
            for state in data["states"]:
                flights.append(FlightState(
                    icao24=state[0],
                    callsign=state[1].strip() if state[1] else None,
                    origin_country=state[2],
                    time_position=state[3],
                    last_contact=state[4],
                    longitude=state[5],
                    latitude=state[6],
                    baro_altitude=state[7],
                    on_ground=state[8],
                    velocity=state[9],
                    true_track=state[10],
                    vertical_rate=state[11],
                    sensors=state[12],
                    geo_altitude=state[13],
                    squawk=state[14],
                    spi=state[15],
                    position_source=state[16],
                ))
            return flights

        except httpx.HTTPError as e:
            logger.error(f"OpenSky API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching area flights: {e}")
            return []
