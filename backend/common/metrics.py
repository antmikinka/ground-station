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

"""Metrics collection utilities for FR24 operations.

This module provides thread-safe metrics collection for monitoring FR24 API
operations, including request counts, latency tracking, error categorization,
and cache performance metrics.

Key features:
- MetricsCollector: Thread-safe metrics aggregation
- Percentile calculations for latency analysis
- Error breakdown by category
- Prometheus text format export (optional)
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ErrorBreakdown:
    """Error counts by category."""
    timeout: int = 0
    rate_limit: int = 0
    circuit_open: int = 0
    api_error: int = 0
    other: int = 0


@dataclass
class CacheMetrics:
    """Cache hit/miss metrics."""
    hits: int = 0
    misses: int = 0

    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker state transition metrics."""
    closed_to_open: int = 0
    open_to_half_open: int = 0
    half_open_to_closed: int = 0
    half_open_to_open: int = 0

    @property
    def total_transitions(self) -> int:
        """Total number of state transitions."""
        return (
            self.closed_to_open +
            self.open_to_half_open +
            self.half_open_to_closed +
            self.half_open_to_open
        )


class MetricsCollector:
    """Thread-safe metrics collector for FR24 operations.

    This collector aggregates metrics for monitoring and observability,
    including request counts, latency distributions, error categorization,
    rate limit utilization, cache performance, and circuit breaker activity.

    All methods are thread-safe and can be called from concurrent contexts.

    Attributes:
        request_count_total: Total number of requests made
        request_count_success: Number of successful requests
        request_count_failure: Number of failed requests
        latencies: List of request latencies in milliseconds
        errors: Error counts categorized by type
        rate_limit_utilization: List of rate limit utilization samples (0.0-1.0)
        cache: Cache hit/miss metrics
        circuit_breaker: Circuit breaker transition metrics

    Example:
        >>> collector = MetricsCollector()
        >>>
        >>> # Record a successful request
        >>> collector.record_request(duration=150.5, success=True)
        >>>
        >>> # Record a failed request
        >>> collector.record_request(
        ...     duration=200.0,
        ...     success=False,
        ...     error_type="timeout"
        ... )
        >>>
        >>> # Get summary
        >>> summary = collector.get_summary()
        >>> print(f"Success rate: {summary['success_rate']:.2f}%")
    """

    def __init__(self):
        """Initialize metrics collector with empty metrics."""
        self._lock = threading.Lock()

        # Request counts
        self._request_count_total = 0
        self._request_count_success = 0
        self._request_count_failure = 0

        # Latency tracking (in milliseconds)
        self._latencies: List[float] = []

        # Error breakdown
        self._errors = ErrorBreakdown()

        # Rate limit utilization samples
        self._rate_limit_samples: List[float] = []

        # Cache metrics
        self._cache = CacheMetrics()

        # Circuit breaker metrics
        self._circuit_breaker = CircuitBreakerMetrics()

    def record_request(
        self,
        duration: float,
        success: bool,
        error_type: Optional[str] = None,
    ) -> None:
        """Record a request with its duration and outcome.

        Args:
            duration: Request duration in milliseconds
            success: Whether the request was successful
            error_type: Type of error if failed (timeout, rate_limit,
                circuit_open, api_error, other). Ignored if success=True.

        Example:
            >>> collector.record_request(duration=125.5, success=True)
            >>> collector.record_request(
            ...     duration=200.0,
            ...     success=False,
            ...     error_type="timeout"
            ... )
        """
        with self._lock:
            self._request_count_total += 1

            if success:
                self._request_count_success += 1
            else:
                self._request_count_failure += 1
                if error_type:
                    self._record_error(error_type)

            self._latencies.append(duration)

    def _record_error(self, error_type: str) -> None:
        """Record an error by category.

        Args:
            error_type: One of timeout, rate_limit, circuit_open, api_error, other
        """
        if error_type == "timeout":
            self._errors.timeout += 1
        elif error_type == "rate_limit":
            self._errors.rate_limit += 1
        elif error_type == "circuit_open":
            self._errors.circuit_open += 1
        elif error_type == "api_error":
            self._errors.api_error += 1
        else:
            self._errors.other += 1

    def record_rate_limit_utilization(self, pct: float) -> None:
        """Record a rate limit utilization sample.

        Args:
            pct: Utilization percentage as 0.0-1.0 where 1.0 means at limit

        Example:
            >>> # At 45 of 60 requests per minute limit
            >>> collector.record_rate_limit_utilization(45 / 60)  # 0.75
        """
        with self._lock:
            # Clamp to valid range
            pct = max(0.0, min(1.0, pct))
            self._rate_limit_samples.append(pct)

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self._cache.hits += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self._cache.misses += 1

    def record_circuit_state_change(
        self,
        from_state: str,
        to_state: str,
    ) -> None:
        """Record a circuit breaker state transition.

        Args:
            from_state: Previous state (closed, open, half-open)
            to_state: New state (closed, open, half-open)

        Example:
            >>> collector.record_circuit_state_change("closed", "open")
            >>> collector.record_circuit_state_change("open", "half-open")
        """
        with self._lock:
            from_state = from_state.lower()
            to_state = to_state.lower()

            if from_state == "closed" and to_state == "open":
                self._circuit_breaker.closed_to_open += 1
            elif from_state == "open" and to_state == "half-open":
                self._circuit_breaker.open_to_half_open += 1
            elif from_state == "half-open" and to_state == "closed":
                self._circuit_breaker.half_open_to_closed += 1
            elif from_state == "half-open" and to_state == "open":
                self._circuit_breaker.half_open_to_open += 1

    def get_latency_percentiles(self) -> Dict[str, float]:
        """Calculate latency percentiles.

        Returns:
            Dictionary with p50, p90, p95, p99 latency values in milliseconds.
            Returns all zeros if no latencies recorded.

        Example:
            >>> percentiles = collector.get_latency_percentiles()
            >>> print(f"P95 latency: {percentiles['p95']:.2f}ms")
        """
        with self._lock:
            if not self._latencies:
                return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}

            sorted_latencies = sorted(self._latencies)
            n = len(sorted_latencies)

            def percentile(p: float) -> float:
                """Calculate percentile value."""
                if n == 1:
                    return sorted_latencies[0]
                k = (n - 1) * p / 100.0
                f = int(k)
                c = f + 1
                if c >= n:
                    return sorted_latencies[-1]
                return sorted_latencies[f] + (k - f) * (sorted_latencies[c] - sorted_latencies[f])

            return {
                "p50": round(percentile(50), 2),
                "p90": round(percentile(90), 2),
                "p95": round(percentile(95), 2),
                "p99": round(percentile(99), 2),
            }

    def get_summary(self) -> Dict:
        """Get comprehensive metrics summary.

        Returns:
            Dictionary containing:
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
            >>> summary = collector.get_summary()
            >>> print(f"Total requests: {summary['total_requests']}")
            >>> print(f"Success rate: {summary['success_rate']:.2f}%")
        """
        with self._lock:
            # Calculate success rate
            if self._request_count_total == 0:
                success_rate = 0.0
            else:
                success_rate = (self._request_count_success / self._request_count_total) * 100.0

            # Calculate average latency
            if self._latencies:
                avg_latency = sum(self._latencies) / len(self._latencies)
            else:
                avg_latency = 0.0

            # Calculate rate limit utilization average
            if self._rate_limit_samples:
                rate_limit_util = sum(self._rate_limit_samples) / len(self._rate_limit_samples)
            else:
                rate_limit_util = 0.0

            # Calculate percentiles inline (avoid deadlock from calling get_latency_percentiles)
            if not self._latencies:
                percentiles = {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
            else:
                sorted_latencies = sorted(self._latencies)
                n = len(sorted_latencies)

                def _percentile(p: float) -> float:
                    if n == 1:
                        return sorted_latencies[0]
                    k = (n - 1) * p / 100.0
                    f = int(k)
                    c = f + 1
                    if c >= n:
                        return sorted_latencies[-1]
                    return sorted_latencies[f] + (k - f) * (sorted_latencies[c] - sorted_latencies[f])

                percentiles = {
                    "p50": round(_percentile(50), 2),
                    "p90": round(_percentile(90), 2),
                    "p95": round(_percentile(95), 2),
                    "p99": round(_percentile(99), 2),
                }

            return {
                "total_requests": self._request_count_total,
                "success_count": self._request_count_success,
                "failure_count": self._request_count_failure,
                "success_rate": round(success_rate, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "latency_percentiles": percentiles,
                "error_breakdown": {
                    "timeout": self._errors.timeout,
                    "rate_limit": self._errors.rate_limit,
                    "circuit_open": self._errors.circuit_open,
                    "api_error": self._errors.api_error,
                    "other": self._errors.other,
                },
                "rate_limit_utilization": round(rate_limit_util, 4),
                "cache_hit_ratio": round(self._cache.hit_ratio, 4),
                "cache_hits": self._cache.hits,
                "cache_misses": self._cache.misses,
                "circuit_breaker_transitions": self._circuit_breaker.total_transitions,
            }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Metrics in Prometheus exposition format suitable for scraping.
            Returns empty string if no metrics recorded at all.

        Example:
            >>> metrics_text = collector.export_prometheus()
            >>> print(metrics_text)
            # HELP fr24_requests_total Total number of FR24 requests
            # TYPE fr24_requests_total counter
            fr24_requests_total{status="success"} 100
            ...
        """
        with self._lock:
            # Check if there are any metrics to export
            has_request_metrics = self._request_count_total > 0
            has_cache_metrics = self._cache.hits > 0 or self._cache.misses > 0
            has_circuit_breaker_metrics = self._circuit_breaker.total_transitions > 0

            if not (has_request_metrics or has_cache_metrics or has_circuit_breaker_metrics):
                return ""

            lines = []

            # Request counts (only if we have request metrics)
            if has_request_metrics:
                lines.append("# HELP fr24_requests_total Total number of FR24 requests")
                lines.append("# TYPE fr24_requests_total counter")
                lines.append(f'fr24_requests_total{{status="success"}} {self._request_count_success}')
                lines.append(f'fr24_requests_total{{status="failure"}} {self._request_count_failure}')

                # Error breakdown
                lines.append("")
                lines.append("# HELP fr24_errors_total Total number of FR24 errors by type")
                lines.append("# TYPE fr24_errors_total counter")
                lines.append(f'fr24_errors_total{{type="timeout"}} {self._errors.timeout}')
                lines.append(f'fr24_errors_total{{type="rate_limit"}} {self._errors.rate_limit}')
                lines.append(f'fr24_errors_total{{type="circuit_open"}} {self._errors.circuit_open}')
                lines.append(f'fr24_errors_total{{type="api_error"}} {self._errors.api_error}')
                lines.append(f'fr24_errors_total{{type="other"}} {self._errors.other}')

                # Latency histogram buckets (simplified - just sum and count)
                if self._latencies:
                    lines.append("")
                    lines.append("# HELP fr24_request_latency_ms Request latency in milliseconds")
                    lines.append("# TYPE fr24_request_latency_ms summary")
                    lines.append(f"fr24_request_latency_ms_count {len(self._latencies)}")
                    lines.append(f"fr24_request_latency_ms_sum {sum(self._latencies):.2f}")

                    # Calculate percentiles inline (avoid deadlock from calling get_latency_percentiles)
                    sorted_latencies = sorted(self._latencies)
                    n = len(sorted_latencies)

                    def _percentile(p: float) -> float:
                        if n == 1:
                            return sorted_latencies[0]
                        k = (n - 1) * p / 100.0
                        f = int(k)
                        c = f + 1
                        if c >= n:
                            return sorted_latencies[-1]
                        return sorted_latencies[f] + (k - f) * (sorted_latencies[c] - sorted_latencies[f])

                    p50 = round(_percentile(50), 2)
                    p90 = round(_percentile(90), 2)
                    p95 = round(_percentile(95), 2)
                    p99 = round(_percentile(99), 2)

                    lines.append(f'fr24_request_latency_ms{{quantile="0.50"}} {p50:.2f}')
                    lines.append(f'fr24_request_latency_ms{{quantile="0.90"}} {p90:.2f}')
                    lines.append(f'fr24_request_latency_ms{{quantile="0.95"}} {p95:.2f}')
                    lines.append(f'fr24_request_latency_ms{{quantile="0.99"}} {p99:.2f}')

            # Cache metrics (always export if we have any metrics)
            lines.append("")
            lines.append("# HELP fr24_cache_hits Cache hit count")
            lines.append("# TYPE fr24_cache_hits counter")
            lines.append(f"fr24_cache_hits {self._cache.hits}")
            lines.append("# HELP fr24_cache_misses Cache miss count")
            lines.append("# TYPE fr24_cache_misses counter")
            lines.append(f"fr24_cache_misses {self._cache.misses}")

            # Circuit breaker metrics (always export if we have any metrics)
            lines.append("")
            lines.append("# HELP fr24_circuit_breaker_transitions Circuit breaker state transitions")
            lines.append("# TYPE fr24_circuit_breaker_transitions counter")
            lines.append(f'fr24_circuit_breaker_transitions{{transition="closed_to_open"}} {self._circuit_breaker.closed_to_open}')
            lines.append(f'fr24_circuit_breaker_transitions{{transition="open_to_half_open"}} {self._circuit_breaker.open_to_half_open}')
            lines.append(f'fr24_circuit_breaker_transitions{{transition="half_open_to_closed"}} {self._circuit_breaker.half_open_to_closed}')
            lines.append(f'fr24_circuit_breaker_transitions{{transition="half_open_to_open"}} {self._circuit_breaker.half_open_to_open}')

            return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics to initial state.

        This clears all recorded metrics and is useful for testing or
        periodic metric collection windows.

        Example:
            >>> collector.reset()
            >>> assert collector.get_summary()["total_requests"] == 0
        """
        with self._lock:
            self._request_count_total = 0
            self._request_count_success = 0
            self._request_count_failure = 0
            self._latencies = []
            self._errors = ErrorBreakdown()
            self._rate_limit_samples = []
            self._cache = CacheMetrics()
            self._circuit_breaker = CircuitBreakerMetrics()

    @property
    def request_count_total(self) -> int:
        """Get total request count."""
        with self._lock:
            return self._request_count_total

    @property
    def request_count_success(self) -> int:
        """Get successful request count."""
        with self._lock:
            return self._request_count_success

    @property
    def request_count_failure(self) -> int:
        """Get failed request count."""
        with self._lock:
            return self._request_count_failure

    @property
    def avg_latency_ms(self) -> float:
        """Get average latency in milliseconds."""
        with self._lock:
            if not self._latencies:
                return 0.0
            return sum(self._latencies) / len(self._latencies)

    @property
    def cache_hit_ratio(self) -> float:
        """Get cache hit ratio."""
        with self._lock:
            return self._cache.hit_ratio
