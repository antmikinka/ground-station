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

"""Flightradar24 API client wrapper for chemtrail tracker."""

from typing import Dict, List, Optional, Union, TYPE_CHECKING
from datetime import datetime, timezone
from dataclasses import dataclass

from fr24sdk import Client as FR24BaseClient
from fr24sdk.models.flight import (
    FlightPositionsFull,
    FlightSummaryFull,
    FlightTracks,
)
from fr24sdk.models.geographic import Boundary, AltitudeRange

if TYPE_CHECKING:
    from common.circuit_breaker import CircuitBreaker


@dataclass
class FR24FlightPosition:
    """Normalized flight position from FR24."""
    fr24_id: str
    hex: str  # ICAO 24-bit hex (equivalent to OpenSky icao24)
    callsign: Optional[str]
    latitude: float
    longitude: float
    altitude: int  # feet
    ground_speed: int  # knots
    vertical_rate: int  # feet/min
    track: int  # heading degrees
    squawk: str
    timestamp: datetime
    aircraft_type: Optional[str]
    registration: Optional[str]
    origin_icao: Optional[str]
    origin_iata: Optional[str]
    destination_icao: Optional[str]
    destination_iata: Optional[str]
    eta: Optional[datetime]
    painted_as: Optional[str]  # Airline ICAO (branding)
    operating_as: Optional[str]  # Airline ICAO (operator)


@dataclass
class FR24FlightSummary:
    """Flight summary from FR24."""
    fr24_id: str
    hex: str
    callsign: Optional[str]
    flight_number: Optional[str]
    aircraft_type: Optional[str]
    registration: Optional[str]
    origin_icao: Optional[str]
    origin_iata: Optional[str]
    destination_icao: Optional[str]
    destination_iata: Optional[str]
    datetime_takeoff: Optional[datetime]
    runway_takeoff: Optional[str]
    datetime_landed: Optional[datetime]
    runway_landed: Optional[str]
    flight_time: Optional[float]  # seconds
    actual_distance: Optional[float]  # km
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    flight_ended: Optional[bool]
    painted_as: Optional[str]
    operating_as: Optional[str]


@dataclass
class FR24FlightTrack:
    """Flight track with positional points."""
    fr24_id: str
    tracks: List[Dict]  # List of {timestamp, lat, lon, alt, gspeed, vspeed, track, squawk}


class FR24Client:
    """
    Wrapper for Flightradar24 SDK client.

    Provides methods needed by chemtrail tracker with normalized data structures.
    All methods are synchronous and should be called via asyncio.to_thread()
    when used from async code.

    Usage:
        # Synchronous
        with FR24Client() as client:
            positions = client.get_live_positions(bounds={...})

        # Async (recommended)
        positions = await asyncio.to_thread(
            client.get_live_positions, bounds={...}
        )

        # With circuit breaker
        cb = CircuitBreaker()
        with FR24Client(api_token="token", circuit_breaker=cb) as client:
            positions = client.get_live_positions()
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        circuit_breaker: Optional["CircuitBreaker"] = None,
    ):
        """
        Initialize FR24 client.

        Args:
            api_token: FR24 API token. If None, reads from FR24_API_TOKEN env var.
            circuit_breaker: Optional CircuitBreaker instance for resilience.
                If provided, all SDK calls will be wrapped with circuit breaker logic.
        """
        self._client: Optional[FR24BaseClient] = None
        self._api_token = api_token
        self._circuit_breaker = circuit_breaker

    def __enter__(self) -> "FR24Client":
        self._client = FR24BaseClient(api_token=self._api_token)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            self._client.close()

    def get_live_positions(
        self,
        bounds: Optional[Dict[str, float]] = None,
        callsigns: Optional[List[str]] = None,
        registrations: Optional[List[str]] = None,
        altitude_range: Optional[Dict[str, int]] = None,
        ground_speed: Optional[int] = None,
        limit: int = 1000,
    ) -> List[FR24FlightPosition]:
        """
        Get live flight positions with optional filters.

        Args:
            bounds: Bounding box {north, south, west, east}
            callsigns: Filter by callsigns
            registrations: Filter by aircraft registrations
            altitude_range: Altitude filter {min_altitude, max_altitude} in feet
            ground_speed: Maximum ground speed filter
            limit: Maximum number of results (1-30000)

        Returns:
            List of FR24FlightPosition objects

        Raises:
            CircuitOpenError: If circuit breaker is open
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")

        boundary = None
        if bounds:
            boundary = Boundary(
                north=bounds["north"],
                south=bounds["south"],
                west=bounds["west"],
                east=bounds["east"],
            )

        altitude_ranges = None
        if altitude_range:
            altitude_ranges = [AltitudeRange(
                min_altitude=altitude_range["min_altitude"],
                max_altitude=altitude_range["max_altitude"],
            )]

        def _make_request():
            return self._client.live.get_full(
                bounds=boundary,
                callsigns=callsigns,
                registrations=registrations,
                altitude_ranges=altitude_ranges,
                gspeed=ground_speed,
                limit=limit,
            )

        if self._circuit_breaker:
            response = self._circuit_breaker.call(_make_request)
        else:
            response = _make_request()

        return [self._map_position(pos) for pos in (response.data or [])]

    def get_historic_positions(
        self,
        timestamp: Union[int, datetime],
        bounds: Optional[Dict[str, float]] = None,
        callsigns: Optional[List[str]] = None,
        limit: int = 1000,
    ) -> List[FR24FlightPosition]:
        """
        Get historical flight positions for a specific timestamp.

        Args:
            timestamp: UNIX timestamp or datetime object (min: 2016-05-11)
            bounds: Bounding box {north, south, west, east}
            callsigns: Filter by callsigns
            limit: Maximum number of results

        Returns:
            List of FR24FlightPosition objects

        Raises:
            CircuitOpenError: If circuit breaker is open
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")

        boundary = None
        if bounds:
            boundary = Boundary(
                north=bounds["north"],
                south=bounds["south"],
                west=bounds["west"],
                east=bounds["east"],
            )

        def _make_request():
            return self._client.historic.get_full(
                timestamp=timestamp,
                bounds=boundary,
                callsigns=callsigns,
                limit=limit,
            )

        if self._circuit_breaker:
            response = self._circuit_breaker.call(_make_request)
        else:
            response = _make_request()

        return [self._map_position(pos) for pos in (response.data or [])]

    def get_flight_tracks(self, flight_id: str) -> FR24FlightTrack:
        """
        Get positional track for a specific flight.

        Args:
            flight_id: FR24 flight ID (hex format, e.g., "34242a02")

        Returns:
            FR24FlightTrack with list of track points

        Raises:
            CircuitOpenError: If circuit breaker is open
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")

        def _make_request():
            return self._client.flight_tracks.get(flight_id=flight_id)

        if self._circuit_breaker:
            response = self._circuit_breaker.call(_make_request)
        else:
            response = _make_request()

        track_data = response.data[0] if response.data else None
        if not track_data:
            return FR24FlightTrack(fr24_id=flight_id, tracks=[])

        return FR24FlightTrack(
            fr24_id=track_data.fr24_id,
            tracks=[
                {
                    "timestamp": point.timestamp,
                    "lat": point.lat,
                    "lon": point.lon,
                    "alt": point.alt,
                    "gspeed": point.gspeed,
                    "vspeed": point.vspeed,
                    "track": point.track,
                    "squawk": point.squawk,
                }
                for point in (track_data.tracks or [])
            ],
        )

    def get_flight_summary(
        self,
        flight_ids: Optional[List[str]] = None,
        callsigns: Optional[List[str]] = None,
        flight_datetime_from: Optional[datetime] = None,
        flight_datetime_to: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[FR24FlightSummary]:
        """
        Get flight summary information.

        Args:
            flight_ids: List of FR24 flight IDs
            callsigns: Filter by callsigns
            flight_datetime_from: Start of time range
            flight_datetime_to: End of time range
            limit: Maximum number of results

        Returns:
            List of FR24FlightSummary objects

        Raises:
            CircuitOpenError: If circuit breaker is open
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")

        def _make_request():
            return self._client.flight_summary.get_full(
                flight_ids=flight_ids,
                callsigns=callsigns,
                flight_datetime_from=flight_datetime_from,
                flight_datetime_to=flight_datetime_to,
                limit=limit,
            )

        if self._circuit_breaker:
            response = self._circuit_breaker.call(_make_request)
        else:
            response = _make_request()

        return [self._map_summary(summary) for summary in (response.data or [])]

    @staticmethod
    def _map_position(pos: FlightPositionsFull) -> FR24FlightPosition:
        """Map FR24 API position to normalized dataclass."""
        try:
            ts = datetime.fromisoformat(pos.timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        eta = None
        if pos.eta:
            try:
                eta = datetime.fromisoformat(pos.eta.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return FR24FlightPosition(
            fr24_id=pos.fr24_id,
            hex=pos.hex or "",
            callsign=pos.callsign,
            latitude=pos.lat,
            longitude=pos.lon,
            altitude=pos.alt,
            ground_speed=pos.gspeed,
            vertical_rate=pos.vspeed,
            track=pos.track,
            squawk=pos.squawk,
            timestamp=ts,
            aircraft_type=pos.type,
            registration=pos.reg,
            origin_icao=pos.orig_icao,
            origin_iata=pos.orig_iata,
            destination_icao=pos.dest_icao,
            destination_iata=pos.dest_iata,
            eta=eta,
            painted_as=pos.painted_as,
            operating_as=pos.operating_as,
        )

    @staticmethod
    def _map_summary(summary: FlightSummaryFull) -> FR24FlightSummary:
        """Map FR24 API summary to normalized dataclass."""
        def parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
            if not dt_str:
                return None
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None

        return FR24FlightSummary(
            fr24_id=summary.fr24_id,
            hex=summary.hex or "",
            callsign=summary.callsign,
            flight_number=summary.flight,
            aircraft_type=summary.type,
            registration=summary.reg,
            origin_icao=summary.orig_icao,
            origin_iata=summary.orig_iata,
            destination_icao=summary.dest_icao,
            destination_iata=summary.dest_iata,
            datetime_takeoff=parse_dt(summary.datetime_takeoff),
            runway_takeoff=summary.runway_takeoff,
            datetime_landed=parse_dt(summary.datetime_landed),
            runway_landed=summary.runway_landed,
            flight_time=summary.flight_time,
            actual_distance=summary.actual_distance,
            first_seen=parse_dt(summary.first_seen),
            last_seen=parse_dt(summary.last_seen),
            flight_ended=summary.flight_ended,
            painted_as=summary.painted_as,
            operating_as=summary.operating_as,
        )
