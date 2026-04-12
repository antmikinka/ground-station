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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from common.common import logger
from common.fr24_logging import (
    LoggingContext,
    log_fr24_enrichment,
    log_fr24_request,
    log_rate_limit_event,
)
from common.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from common.metrics import MetricsCollector
from ..api.fr24_client import FR24Client, FR24FlightPosition, FR24FlightSummary

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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
    # Circuit breaker settings
    cb_failure_threshold: int = 5  # consecutive failures before opening circuit
    cb_recovery_timeout: float = 60.0  # seconds before transitioning to half-open
    cb_success_threshold: int = 2  # consecutive successes in half-open to close

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
            cb_failure_threshold=int(os.environ.get("FR24_CB_FAILURE_THRESHOLD", 5)),
            cb_recovery_timeout=float(os.environ.get("FR24_CB_RECOVERY_TIMEOUT", 60.0)),
            cb_success_threshold=int(os.environ.get("FR24_CB_SUCCESS_THRESHOLD", 2)),
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

    def __init__(
        self,
        api_token: Optional[str] = None,
        config: Optional[FR24Config] = None,
        session: Optional["Session"] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Initialize FR24 flight service.

        Args:
            api_token: FR24 API token (optional, falls back to env var)
            config: FR24Config instance (optional, falls back to from_env())
            session: Optional SQLAlchemy session for rate limit persistence
            circuit_breaker: Optional CircuitBreaker instance. If not provided,
                one will be created using config settings.
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
        self._session = session

        # Initialize circuit breaker
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=self.config.cb_failure_threshold,
            recovery_timeout=self.config.cb_recovery_timeout,
            success_threshold=self.config.cb_success_threshold,
            name="fr24_flight_service",
        )

        # Initialize metrics collector
        self._metrics = MetricsCollector()

        # Load persisted rate limit state from database
        if session:
            self._load_rate_limit_state()

    def _enforce_rate_limit(self):
        """Enforce rate limit by sleeping if necessary.

        Uses a sliding window algorithm to ensure no more than
        rate_limit requests per rate_limit_window seconds.

        Logs rate limit events with structured logging and persists
        state to database if session is available.
        """
        now = time.monotonic()
        window = self.config.rate_limit_window

        # Remove timestamps outside the current window
        old_count = len(self._request_timestamps)
        self._request_timestamps = [
            ts for ts in self._request_timestamps
            if now - ts < window
        ]
        if old_count != len(self._request_timestamps):
            logger.debug(
                f"Rate limit cleanup: removed {old_count - len(self._request_timestamps)} old timestamps"
            )

        if len(self._request_timestamps) >= self.rate_limit:
            # Calculate how long to sleep
            oldest_in_window = self._request_timestamps[0]
            sleep_time = window - (now - oldest_in_window) + 0.1
            if sleep_time > 0:
                log_rate_limit_event(
                    event_type="sleeping",
                    current_count=len(self._request_timestamps),
                    limit=self.rate_limit,
                    window_seconds=window,
                    sleep_time=sleep_time,
                )
                time.sleep(sleep_time)

        self._request_timestamps.append(time.monotonic())

        # Persist state to database if session is available
        if self._session:
            self._save_rate_limit_state()

    def validate_api_token(self) -> bool:
        """Validate FR24 API token by making test request.

        Returns:
            True if token is valid, False otherwise.
        """
        if not self.api_token:
            logger.warning("FR24 API token not configured")
            return False

        start_time = time.time()
        try:
            self._enforce_rate_limit()
            with LoggingContext() as ctx:
                with FR24Client(api_token=self.api_token, circuit_breaker=self._circuit_breaker) as client:
                    # Make minimal test request
                    positions = client.get_live_positions(limit=1)
                    latency_ms = (time.time() - start_time) * 1000
                    log_fr24_request(
                        method="GET",
                        endpoint="/live/positions",
                        latency_ms=latency_ms,
                        status_code=200,
                        success=True,
                        extra_fields=ctx,
                    )
                    logger.info("FR24 API token validation successful", extra=ctx)
                    self._metrics.record_request(duration=latency_ms, success=True)
                    return True
        except CircuitOpenError:
            latency_ms = (time.time() - start_time) * 1000
            log_fr24_request(
                method="GET",
                endpoint="/live/positions",
                latency_ms=latency_ms,
                success=False,
                error_message="Circuit breaker is OPEN",
            )
            logger.warning("FR24 API token validation skipped: circuit breaker is OPEN")
            self._metrics.record_request(duration=latency_ms, success=False, error_type="circuit_open")
            return False
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            log_fr24_request(
                method="GET",
                endpoint="/live/positions",
                latency_ms=latency_ms,
                success=False,
                error_message=str(e),
            )
            logger.error(f"FR24 API token validation failed: {e}")
            self._metrics.record_request(duration=latency_ms, success=False, error_type="api_error")
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
                "circuit_breaker": {
                    "state": "closed" | "open" | "half-open",
                    "failure_count": int,
                    "last_failure": datetime|None,
                },
                "metrics": {
                    "total_requests": int,
                    "success_rate": float,
                    "avg_latency_ms": float,
                    "p95_latency_ms": float,
                    "error_breakdown": dict,
                    "rate_limit_utilization": float,
                },
            }
        """
        result = {
            "status": "unhealthy",
            "api_accessible": False,
            "token_valid": False,
            "last_check": datetime.now(timezone.utc),
            "circuit_breaker": {
                "state": self._circuit_breaker.state.value,
                "failure_count": self._circuit_breaker.failure_count,
                "last_failure": self._circuit_breaker.last_failure_time,
            },
        }

        # Add metrics summary
        metrics_summary = self._metrics.get_summary()
        result["metrics"] = {
            "total_requests": metrics_summary["total_requests"],
            "success_rate": metrics_summary["success_rate"],
            "avg_latency_ms": metrics_summary["avg_latency_ms"],
            "p95_latency_ms": metrics_summary["latency_percentiles"]["p95"],
            "error_breakdown": metrics_summary["error_breakdown"],
            "rate_limit_utilization": metrics_summary["rate_limit_utilization"],
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
            List of normalized flight position dicts.
            Returns empty list if circuit breaker is OPEN.
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

        start_time = time.time()
        with LoggingContext() as ctx:
            try:
                self._enforce_rate_limit()
                with FR24Client(api_token=self.api_token, circuit_breaker=self._circuit_breaker) as client:
                    if time_diff > time_tolerance_seconds:
                        endpoint = "/historic/positions"
                        positions = client.get_historic_positions(
                            timestamp=timestamp,
                            bounds=bounds,
                            limit=limit,
                        )
                    else:
                        endpoint = "/live/positions"
                        positions = client.get_live_positions(
                            bounds=bounds,
                            limit=limit,
                        )

                    latency_ms = (time.time() - start_time) * 1000
                    log_fr24_request(
                        method="GET",
                        endpoint=endpoint,
                        latency_ms=latency_ms,
                        status_code=200,
                        success=True,
                        extra_fields=ctx,
                    )
                    self._metrics.record_request(duration=latency_ms, success=True)

                    return [self._position_to_dict(pos) for pos in positions]
            except CircuitOpenError:
                latency_ms = (time.time() - start_time) * 1000
                log_fr24_request(
                    method="GET",
                    endpoint="/live/positions" if time_diff <= time_tolerance_seconds else "/historic/positions",
                    latency_ms=latency_ms,
                    success=False,
                    error_message="Circuit breaker is OPEN - returning cached/empty data",
                    extra_fields=ctx,
                )
                logger.warning("FR24 positions request skipped: circuit breaker is OPEN")
                self._metrics.record_request(duration=latency_ms, success=False, error_type="circuit_open")
                return []
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                log_fr24_request(
                    method="GET",
                    endpoint=endpoint if "endpoint" in dir() else "/unknown",
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(e),
                    extra_fields=ctx,
                )
                self._metrics.record_request(duration=latency_ms, success=False, error_type="api_error")
                raise

    def get_flight_track(self, fr24_id: str) -> Optional[Dict]:
        """
        Get flight track for a specific flight.

        Args:
            fr24_id: FR24 flight ID (hex format)

        Returns:
            Dict with fr24_id and tracks list, or None if not found.
            Returns None if circuit breaker is OPEN.
        """
        start_time = time.time()
        with LoggingContext() as ctx:
            try:
                self._enforce_rate_limit()
                with FR24Client(api_token=self.api_token, circuit_breaker=self._circuit_breaker) as client:
                    track = client.get_flight_tracks(flight_id=fr24_id)

                    latency_ms = (time.time() - start_time) * 1000

                    if not track.tracks:
                        log_fr24_request(
                            method="GET",
                            endpoint="/flight/tracks",
                            hex_code=fr24_id,
                            latency_ms=latency_ms,
                            status_code=200,
                            success=True,
                            extra_fields={"tracks_found": 0, **ctx},
                        )
                        self._metrics.record_request(duration=latency_ms, success=True)
                        return None

                    log_fr24_request(
                        method="GET",
                        endpoint="/flight/tracks",
                        hex_code=fr24_id,
                        latency_ms=latency_ms,
                        status_code=200,
                        success=True,
                        extra_fields={"tracks_found": len(track.tracks), **ctx},
                    )
                    self._metrics.record_request(duration=latency_ms, success=True)

                    return {
                        "fr24_id": track.fr24_id,
                        "tracks": track.tracks,
                    }
            except CircuitOpenError:
                latency_ms = (time.time() - start_time) * 1000
                log_fr24_request(
                    method="GET",
                    endpoint="/flight/tracks",
                    hex_code=fr24_id,
                    latency_ms=latency_ms,
                    success=False,
                    error_message="Circuit breaker is OPEN",
                    extra_fields=ctx,
                )
                logger.warning(f"FR24 flight track request skipped for {fr24_id}: circuit breaker is OPEN")
                self._metrics.record_request(duration=latency_ms, success=False, error_type="circuit_open")
                return None
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                log_fr24_request(
                    method="GET",
                    endpoint="/flight/tracks",
                    hex_code=fr24_id,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(e),
                )
                self._metrics.record_request(duration=latency_ms, success=False, error_type="api_error")
                logger.error(f"Error fetching FR24 flight track for {fr24_id}: {e}")
                return None

    def get_flight_summary_by_hex(self, hex_code: str) -> Optional[Dict]:
        """
        Get flight summary by ICAO hex code.

        Args:
            hex_code: ICAO 24-bit hex code

        Returns:
            Dict with flight summary data, or None if not found.
            Returns None if circuit breaker is OPEN.
        """
        start_time = time.time()
        with LoggingContext() as ctx:
            try:
                self._enforce_rate_limit()
                with FR24Client(api_token=self.api_token, circuit_breaker=self._circuit_breaker) as client:
                    tracks = client.get_flight_tracks(flight_id=hex_code)

                    if not tracks.tracks:
                        log_fr24_request(
                            method="GET",
                            endpoint="/flight/tracks",
                            hex_code=hex_code,
                            latency_ms=(time.time() - start_time) * 1000,
                            status_code=200,
                            success=True,
                            extra_fields={"tracks_found": 0, **ctx},
                        )
                        self._metrics.record_request(
                            duration=(time.time() - start_time) * 1000,
                            success=True,
                        )
                        return None

                    summaries = client.get_flight_summary(
                        flight_ids=[tracks.fr24_id],
                        limit=1,
                    )

                    latency_ms = (time.time() - start_time) * 1000

                    if not summaries:
                        log_fr24_request(
                            method="GET",
                            endpoint="/flight/summary",
                            hex_code=hex_code,
                            latency_ms=latency_ms,
                            status_code=200,
                            success=True,
                            extra_fields={"summaries_found": 0, **ctx},
                        )
                        self._metrics.record_request(duration=latency_ms, success=True)
                        return None

                    log_fr24_request(
                        method="GET",
                        endpoint="/flight/summary",
                        hex_code=hex_code,
                        latency_ms=latency_ms,
                        status_code=200,
                        success=True,
                        extra_fields={"summaries_found": 1, **ctx},
                    )
                    self._metrics.record_request(duration=latency_ms, success=True)

                    return self._summary_to_dict(summaries[0])
            except CircuitOpenError:
                latency_ms = (time.time() - start_time) * 1000
                log_fr24_request(
                    method="GET",
                    endpoint="/flight/summary",
                    hex_code=hex_code,
                    latency_ms=latency_ms,
                    success=False,
                    error_message="Circuit breaker is OPEN",
                    extra_fields=ctx,
                )
                logger.warning(f"FR24 flight summary request skipped for {hex_code}: circuit breaker is OPEN")
                self._metrics.record_request(duration=latency_ms, success=False, error_type="circuit_open")
                return None
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                log_fr24_request(
                    method="GET",
                    endpoint="/flight/summary",
                    hex_code=hex_code,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(e),
                )
                self._metrics.record_request(duration=latency_ms, success=False, error_type="api_error")
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
            Dict with merged data from both sources.
            Returns existing_data (or empty dict) if circuit breaker is OPEN.
        """
        enriched = existing_data or {}
        start_time = time.time()

        # Check if we have a valid token before attempting enrichment
        if not self.api_token:
            logger.debug(f"FR24 enrichment skipped for {icao24}: no API token configured")
            self._metrics.record_cache_miss()
            return enriched

        with LoggingContext() as ctx:
            fields_enriched = []

            try:
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
                    fields_enriched.extend([
                        "fr24_id", "painted_as", "operating_as",
                        "origin_icao", "origin_iata",
                        "destination_icao", "destination_iata",
                        "datetime_takeoff", "datetime_landed", "flight_time",
                    ])

                track = self.get_flight_track(icao24)
                if track:
                    enriched["flight_track"] = track.get("tracks", [])
                    fields_enriched.append("flight_track")

                duration_ms = (time.time() - start_time) * 1000

                # Record cache hit if we found data, miss otherwise
                if fields_enriched:
                    self._metrics.record_cache_hit()
                else:
                    self._metrics.record_cache_miss()

                log_fr24_enrichment(
                    icao24=icao24,
                    fields_enriched=fields_enriched,
                    duration_ms=duration_ms,
                    source="fr24",
                    success=True,
                    extra_fields=ctx,
                )

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self._metrics.record_cache_miss()
                log_fr24_enrichment(
                    icao24=icao24,
                    fields_enriched=fields_enriched,
                    duration_ms=duration_ms,
                    source="fr24",
                    success=False,
                    error_message=str(e),
                )
                logger.error(f"Error enriching flight data for {icao24}: {e}")

        return enriched

    def get_metrics(self) -> Dict:
        """Get comprehensive metrics summary.

        Returns:
            Dictionary containing all collected metrics:
            - total_requests: Total request count
            - success_count: Number of successful requests
            - failure_count: Number of failed requests
            - success_rate: Success percentage (0-100)
            - avg_latency_ms: Average latency in milliseconds
            - latency_percentiles: Dict with p50, p90, p95, p99
            - error_breakdown: Dict with counts by error type
            - rate_limit_utilization: Average utilization (0.0-1.0)
            - cache_hit_ratio: Cache hit ratio (0.0-1.0)
            - circuit_breaker_transitions: Total state transitions

        Example:
            >>> metrics = service.get_metrics()
            >>> print(f"P95 latency: {metrics['latency_percentiles']['p95']}ms")
        """
        return self._metrics.get_summary()

    def reset_metrics(self) -> None:
        """Reset all metrics to initial state.

        This is useful for testing or periodic metric collection windows.
        """
        self._metrics.reset()

    def _load_rate_limit_state(self) -> None:
        """Load rate limit state from database.

        Queries the service_state table for the FR24 rate limit state
        and restores the request timestamps list.
        """
        from db.models import ServiceState

        try:
            state = (
                self._session.query(ServiceState)
                .filter(ServiceState.service_name == "fr24_rate_limit")
                .first()
            )

            if state and state.state_data:
                timestamps = state.state_data.get("timestamps", [])
                now = time.monotonic()
                window = self.config.rate_limit_window

                # Filter out expired timestamps
                self._request_timestamps = [
                    ts for ts in timestamps
                    if now - ts < window
                ]

                logger.debug(
                    f"Loaded {len(self._request_timestamps)} rate limit timestamps from database"
                )
            else:
                logger.debug("No existing rate limit state found in database")

        except Exception as e:
            logger.warning(f"Failed to load rate limit state from database: {e}")
            self._request_timestamps = []

    def _save_rate_limit_state(self) -> None:
        """Save rate limit state to database.

        Persists the current request timestamps list to the service_state table.
        Uses upsert logic to create or update the state record.
        """
        from db.models import ServiceState
        from datetime import datetime, timezone

        try:
            # Query existing state
            state = (
                self._session.query(ServiceState)
                .filter(ServiceState.service_name == "fr24_rate_limit")
                .first()
            )

            state_data = {
                "timestamps": self._request_timestamps,
                "last_request_at": datetime.now(timezone.utc).isoformat(),
            }

            if state:
                # Update existing
                state.state_data = state_data
                state.updated_at = datetime.now(timezone.utc)
            else:
                # Create new
                state = ServiceState(
                    service_name="fr24_rate_limit",
                    state_data=state_data,
                )
                self._session.add(state)

            self._session.commit()
            logger.debug(f"Saved {len(self._request_timestamps)} rate limit timestamps to database")

        except Exception as e:
            logger.warning(f"Failed to save rate limit state to database: {e}")
            self._session.rollback()

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
