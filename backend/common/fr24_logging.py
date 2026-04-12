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

"""Structured logging utilities for FR24 API operations.

This module provides structured logging capabilities for Flightradar24 API calls,
including correlation ID tracking, request/response logging, and enrichment operation
tracing.

Key features:
- LoggingContext: Context manager for correlation ID propagation
- log_fr24_request: Structured logging for API requests
- log_fr24_enrichment: Structured logging for data enrichment operations
"""

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Generator, Optional

from common.common import logger


# Context variable for correlation ID propagation across async boundaries
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context.

    Returns:
        The current correlation ID string, or None if not set.
    """
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in the current context.

    Args:
        correlation_id: The correlation ID to set.
    """
    _correlation_id.set(correlation_id)


@contextmanager
def LoggingContext(correlation_id: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
    """Context manager for structured logging with correlation ID tracking.

    This context manager establishes a logging context with a unique correlation ID
    that can be used to trace related operations across service boundaries. If no
    correlation ID is provided, a new UUID4 is generated.

    The context provides a structured fields dictionary that can be used for
    consistent logging across the application.

    Args:
        correlation_id: Optional existing correlation ID. If None, a new UUID is generated.

    Yields:
        A dictionary containing structured logging fields:
        - correlation_id: The current correlation ID
        - component: "fr24_service" identifier

    Example:
        >>> with LoggingContext() as ctx:
        ...     logger.info("Processing request", extra=ctx)
        ...     # All logs in this block share the same correlation_id

        >>> with LoggingContext(existing_id) as ctx:
        ...     # Continue tracing an existing request chain
    """
    # Generate new ID or use provided one
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    # Store in context variable for access by other logging functions
    token = _correlation_id.set(correlation_id)

    # Structured fields for consistent logging
    fields = {
        "correlation_id": correlation_id,
        "component": "fr24_service",
    }

    try:
        logger.debug(f"Starting logging context with correlation_id={correlation_id}")
        yield fields
    finally:
        _correlation_id.reset(token)
        logger.debug(f"Ending logging context with correlation_id={correlation_id}")


def log_fr24_request(
    method: str,
    endpoint: str,
    hex_code: Optional[str] = None,
    latency_ms: Optional[float] = None,
    status_code: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a structured FR24 API request.

    This function logs FR24 API calls with consistent structured fields for
    monitoring, debugging, and analysis. It automatically includes the current
    correlation ID if one is set in the context.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint being called
        hex_code: Optional ICAO hex code for the aircraft
        latency_ms: Request latency in milliseconds
        status_code: HTTP response status code
        success: Whether the request was successful
        error_message: Optional error message if request failed
        extra_fields: Optional additional structured fields to include

    Example:
        >>> start_time = time.time()
        >>> try:
        ...     response = call_fr24_api()
        ...     latency = (time.time() - start_time) * 1000
        ...     log_fr24_request(
        ...         method="GET",
        ...         endpoint="/flight/tracks",
        ...         hex_code="4b1a02",
        ...         latency_ms=latency,
        ...         status_code=response.status,
        ...         success=True
        ...     )
        ... except Exception as e:
        ...     log_fr24_request(
        ...         method="GET",
        ...         endpoint="/flight/tracks",
        ...         hex_code="4b1a02",
        ...         success=False,
        ...         error_message=str(e)
        ...     )
    """
    # Build structured log fields
    log_fields = {
        "event": "fr24_request",
        "method": method,
        "endpoint": endpoint,
        "success": success,
    }

    # Add optional fields
    if hex_code:
        log_fields["hex_code"] = hex_code
    if latency_ms is not None:
        log_fields["latency_ms"] = round(latency_ms, 2)
    if status_code:
        log_fields["status_code"] = status_code
    if error_message:
        log_fields["error_message"] = error_message

    # Merge extra fields
    if extra_fields:
        log_fields.update(extra_fields)

    # Add correlation context
    correlation_id = get_correlation_id()
    if correlation_id:
        log_fields["correlation_id"] = correlation_id

    # Log at appropriate level
    if success:
        logger.info(f"FR24 {method} {endpoint} completed", extra=log_fields)
    else:
        logger.error(f"FR24 {method} {endpoint} failed", extra=log_fields)


def log_fr24_enrichment(
    icao24: str,
    fields_enriched: list,
    duration_ms: float,
    source: str = "fr24",
    success: bool = True,
    error_message: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a structured FR24 enrichment operation.

    This function logs data enrichment operations where FR24 data is merged
    with existing flight information. It tracks which fields were enriched,
    the duration of the operation, and any errors encountered.

    Args:
        icao24: ICAO 24-bit hex code of the aircraft
        fields_enriched: List of field names that were enriched
        duration_ms: Duration of enrichment operation in milliseconds
        source: Data source identifier (default: "fr24")
        success: Whether enrichment was successful
        error_message: Optional error message if enrichment failed
        extra_fields: Optional additional structured fields to include

    Example:
        >>> start = time.time()
        >>> enriched_fields = ["fr24_id", "flight_number", "origin_icao"]
        >>> try:
        ...     data = enrich_flight_data(icao24)
        ...     duration = (time.time() - start) * 1000
        ...     log_fr24_enrichment(
        ...         icao24=icao24,
        ...         fields_enriched=enriched_fields,
        ...         duration_ms=duration
        ...     )
        ... except Exception as e:
        ...     log_fr24_enrichment(
        ...         icao24=icao24,
        ...         fields_enriched=[],
        ...         duration_ms=(time.time() - start) * 1000,
        ...         success=False,
        ...         error_message=str(e)
        ...     )
    """
    # Build structured log fields
    log_fields = {
        "event": "fr24_enrichment",
        "icao24": icao24,
        "source": source,
        "fields_enriched": fields_enriched,
        "fields_count": len(fields_enriched),
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }

    # Add optional fields
    if error_message:
        log_fields["error_message"] = error_message

    # Merge extra fields
    if extra_fields:
        log_fields.update(extra_fields)

    # Add correlation context
    correlation_id = get_correlation_id()
    if correlation_id:
        log_fields["correlation_id"] = correlation_id

    # Log at appropriate level
    if success:
        if fields_enriched:
            logger.info(
                f"FR24 enrichment completed for {icao24}: {len(fields_enriched)} fields",
                extra=log_fields,
            )
        else:
            logger.debug(f"FR24 enrichment completed for {icao24}: no new fields", extra=log_fields)
    else:
        logger.warning(f"FR24 enrichment failed for {icao24}", extra=log_fields)


def log_rate_limit_event(
    event_type: str,
    current_count: int,
    limit: int,
    window_seconds: float,
    sleep_time: Optional[float] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a rate limit event.

    This function logs rate limiting events including when limits are reached
    and sleep delays are applied.

    Args:
        event_type: Type of event ("enforcing", "sleeping", "released")
        current_count: Current number of requests in the window
        limit: The configured rate limit
        window_seconds: The rate limit window in seconds
        sleep_time: Optional sleep time applied in seconds
        extra_fields: Optional additional structured fields

    Example:
        >>> log_rate_limit_event(
        ...     event_type="sleeping",
        ...     current_count=60,
        ...     limit=60,
        ...     window_seconds=60.0,
        ...     sleep_time=2.5
        ... )
    """
    log_fields = {
        "event": f"rate_limit_{event_type}",
        "current_count": current_count,
        "rate_limit": limit,
        "window_seconds": window_seconds,
    }

    if sleep_time is not None:
        log_fields["sleep_time_seconds"] = round(sleep_time, 2)

    if extra_fields:
        log_fields.update(extra_fields)

    correlation_id = get_correlation_id()
    if correlation_id:
        log_fields["correlation_id"] = correlation_id

    if event_type == "sleeping":
        logger.warning(
            f"FR24 rate limit reached: {current_count}/{limit} requests, "
            f"sleeping {sleep_time:.1f}s",
            extra=log_fields,
        )
    else:
        logger.debug(f"FR24 rate limit {event_type}", extra=log_fields)
