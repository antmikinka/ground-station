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

"""Tests for metrics collection utilities."""

import pytest
import threading
import time
from unittest.mock import MagicMock, patch

from common.metrics import (
    MetricsCollector,
    ErrorBreakdown,
    CacheMetrics,
    CircuitBreakerMetrics,
)


# ============================================================================
# ErrorBreakdown Tests
# ============================================================================


class TestErrorBreakdown:
    """Test ErrorBreakdown dataclass."""

    def test_init_default_values(self):
        """Test ErrorBreakdown initializes with zero values."""
        eb = ErrorBreakdown()
        assert eb.timeout == 0
        assert eb.rate_limit == 0
        assert eb.circuit_open == 0
        assert eb.api_error == 0
        assert eb.other == 0


# ============================================================================
# CacheMetrics Tests
# ============================================================================


class TestCacheMetrics:
    """Test CacheMetrics dataclass."""

    def test_init_default_values(self):
        """Test CacheMetrics initializes with zero values."""
        cm = CacheMetrics()
        assert cm.hits == 0
        assert cm.misses == 0

    def test_hit_ratio_empty(self):
        """Test hit ratio returns 0.0 when no requests."""
        cm = CacheMetrics()
        assert cm.hit_ratio == 0.0

    def test_hit_ratio_all_hits(self):
        """Test hit ratio returns 1.0 when all hits."""
        cm = CacheMetrics(hits=10, misses=0)
        assert cm.hit_ratio == 1.0

    def test_hit_ratio_all_misses(self):
        """Test hit ratio returns 0.0 when all misses."""
        cm = CacheMetrics(hits=0, misses=10)
        assert cm.hit_ratio == 0.0

    def test_hit_ratio_mixed(self):
        """Test hit ratio calculation with mixed hits and misses."""
        cm = CacheMetrics(hits=7, misses=3)
        assert cm.hit_ratio == 0.7

    def test_hit_ratio_50_50(self):
        """Test hit ratio with equal hits and misses."""
        cm = CacheMetrics(hits=5, misses=5)
        assert cm.hit_ratio == 0.5


# ============================================================================
# CircuitBreakerMetrics Tests
# ============================================================================


class TestCircuitBreakerMetrics:
    """Test CircuitBreakerMetrics dataclass."""

    def test_init_default_values(self):
        """Test CircuitBreakerMetrics initializes with zero values."""
        cbm = CircuitBreakerMetrics()
        assert cbm.closed_to_open == 0
        assert cbm.open_to_half_open == 0
        assert cbm.half_open_to_closed == 0
        assert cbm.half_open_to_open == 0

    def test_total_transitions_empty(self):
        """Test total_transitions returns 0 when no transitions."""
        cbm = CircuitBreakerMetrics()
        assert cbm.total_transitions == 0

    def test_total_transitions(self):
        """Test total_transitions calculation."""
        cbm = CircuitBreakerMetrics(
            closed_to_open=3,
            open_to_half_open=2,
            half_open_to_closed=1,
            half_open_to_open=1,
        )
        assert cbm.total_transitions == 7


# ============================================================================
# MetricsCollector Basic Tests
# ============================================================================


class TestMetricsCollectorInitialization:
    """Test MetricsCollector initialization."""

    def test_init_default_values(self):
        """Test MetricsCollector initializes with empty metrics."""
        mc = MetricsCollector()
        summary = mc.get_summary()

        assert summary["total_requests"] == 0
        assert summary["success_count"] == 0
        assert summary["failure_count"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["avg_latency_ms"] == 0.0
        assert summary["error_breakdown"]["timeout"] == 0
        assert summary["cache_hits"] == 0
        assert summary["cache_misses"] == 0
        assert summary["circuit_breaker_transitions"] == 0

    def test_properties_empty(self):
        """Test properties return appropriate defaults when empty."""
        mc = MetricsCollector()

        assert mc.request_count_total == 0
        assert mc.request_count_success == 0
        assert mc.request_count_failure == 0
        assert mc.avg_latency_ms == 0.0
        assert mc.cache_hit_ratio == 0.0


# ============================================================================
# MetricsCollector Recording Tests
# ============================================================================


class TestMetricsCollectorRecording:
    """Test MetricsCollector recording methods."""

    def test_record_request_success(self):
        """Test recording successful requests."""
        mc = MetricsCollector()
        mc.record_request(duration=100.0, success=True)

        summary = mc.get_summary()
        assert summary["total_requests"] == 1
        assert summary["success_count"] == 1
        assert summary["failure_count"] == 0
        assert summary["success_rate"] == 100.0
        assert summary["avg_latency_ms"] == 100.0

    def test_record_request_failure(self):
        """Test recording failed requests."""
        mc = MetricsCollector()
        mc.record_request(duration=150.0, success=False, error_type="timeout")

        summary = mc.get_summary()
        assert summary["total_requests"] == 1
        assert summary["success_count"] == 0
        assert summary["failure_count"] == 1
        assert summary["success_rate"] == 0.0
        assert summary["error_breakdown"]["timeout"] == 1

    def test_record_request_failure_types(self):
        """Test recording different error types."""
        mc = MetricsCollector()

        mc.record_request(duration=100.0, success=False, error_type="timeout")
        mc.record_request(duration=100.0, success=False, error_type="rate_limit")
        mc.record_request(duration=100.0, success=False, error_type="circuit_open")
        mc.record_request(duration=100.0, success=False, error_type="api_error")
        mc.record_request(duration=100.0, success=False, error_type="other")
        mc.record_request(duration=100.0, success=False, error_type="unknown")

        summary = mc.get_summary()
        assert summary["error_breakdown"]["timeout"] == 1
        assert summary["error_breakdown"]["rate_limit"] == 1
        assert summary["error_breakdown"]["circuit_open"] == 1
        assert summary["error_breakdown"]["api_error"] == 1
        assert summary["error_breakdown"]["other"] == 2  # "other" and "unknown"

    def test_record_request_multiple(self):
        """Test recording multiple requests."""
        mc = MetricsCollector()

        for i in range(10):
            mc.record_request(duration=100.0 + i * 10, success=(i % 2 == 0))

        summary = mc.get_summary()
        assert summary["total_requests"] == 10
        assert summary["success_count"] == 5
        assert summary["failure_count"] == 5
        assert summary["success_rate"] == 50.0
        assert summary["avg_latency_ms"] == 145.0  # Average of 100, 110, ..., 190

    def test_record_rate_limit_utilization(self):
        """Test recording rate limit utilization."""
        mc = MetricsCollector()
        mc.record_rate_limit_utilization(0.5)
        mc.record_rate_limit_utilization(0.75)
        mc.record_rate_limit_utilization(1.0)

        summary = mc.get_summary()
        assert summary["rate_limit_utilization"] == 0.75  # Average of 0.5, 0.75, 1.0

    def test_record_rate_limit_utilization_clamped(self):
        """Test that rate limit utilization is clamped to 0.0-1.0."""
        mc = MetricsCollector()
        mc.record_rate_limit_utilization(-0.5)  # Should be clamped to 0.0
        mc.record_rate_limit_utilization(1.5)   # Should be clamped to 1.0

        summary = mc.get_summary()
        assert summary["rate_limit_utilization"] == 0.5  # Average of 0.0 and 1.0

    def test_record_cache_hit(self):
        """Test recording cache hits."""
        mc = MetricsCollector()
        mc.record_cache_hit()
        mc.record_cache_hit()
        mc.record_cache_hit()

        summary = mc.get_summary()
        assert summary["cache_hits"] == 3
        assert summary["cache_misses"] == 0
        assert summary["cache_hit_ratio"] == 1.0

    def test_record_cache_miss(self):
        """Test recording cache misses."""
        mc = MetricsCollector()
        mc.record_cache_miss()
        mc.record_cache_miss()

        summary = mc.get_summary()
        assert summary["cache_hits"] == 0
        assert summary["cache_misses"] == 2
        assert summary["cache_hit_ratio"] == 0.0

    def test_record_cache_mixed(self):
        """Test recording mixed cache hits and misses."""
        mc = MetricsCollector()
        mc.record_cache_hit()
        mc.record_cache_hit()
        mc.record_cache_hit()
        mc.record_cache_miss()
        mc.record_cache_miss()

        summary = mc.get_summary()
        assert summary["cache_hits"] == 3
        assert summary["cache_misses"] == 2
        assert summary["cache_hit_ratio"] == 0.6

    def test_record_circuit_state_change(self):
        """Test recording circuit breaker state transitions."""
        mc = MetricsCollector()
        mc.record_circuit_state_change("closed", "open")
        mc.record_circuit_state_change("open", "half-open")
        mc.record_circuit_state_change("half-open", "closed")

        summary = mc.get_summary()
        assert summary["circuit_breaker_transitions"] == 3

    def test_record_circuit_state_change_case_insensitive(self):
        """Test that state change recording is case insensitive."""
        mc = MetricsCollector()
        mc.record_circuit_state_change("CLOSED", "OPEN")
        mc.record_circuit_state_change("Open", "Half-Open")

        summary = mc.get_summary()
        assert summary["circuit_breaker_transitions"] == 2


# ============================================================================
# MetricsCollector Percentile Tests
# ============================================================================


class TestMetricsCollectorPercentiles:
    """Test latency percentile calculations."""

    def test_get_latency_percentiles_empty(self):
        """Test percentiles return zeros when no data."""
        mc = MetricsCollector()
        percentiles = mc.get_latency_percentiles()

        assert percentiles["p50"] == 0.0
        assert percentiles["p90"] == 0.0
        assert percentiles["p95"] == 0.0
        assert percentiles["p99"] == 0.0

    def test_get_latency_percentiles_single(self):
        """Test percentiles with single value."""
        mc = MetricsCollector()
        mc.record_request(duration=100.0, success=True)

        percentiles = mc.get_latency_percentiles()
        assert percentiles["p50"] == 100.0
        assert percentiles["p90"] == 100.0
        assert percentiles["p95"] == 100.0
        assert percentiles["p99"] == 100.0

    def test_get_latency_percentiles_uniform(self):
        """Test percentiles with uniform values."""
        mc = MetricsCollector()
        for _ in range(100):
            mc.record_request(duration=50.0, success=True)

        percentiles = mc.get_latency_percentiles()
        assert percentiles["p50"] == 50.0
        assert percentiles["p90"] == 50.0
        assert percentiles["p95"] == 50.0
        assert percentiles["p99"] == 50.0

    def test_get_latency_percentiles_increasing(self):
        """Test percentiles with increasing values."""
        mc = MetricsCollector()
        # Record 100 requests with increasing latency
        for i in range(100):
            mc.record_request(duration=float(i + 1), success=True)

        percentiles = mc.get_latency_percentiles()
        # With values 1-100:
        # p50 should be around 50
        # p90 should be around 90
        # p95 should be around 95
        # p99 should be around 99
        assert 49.0 <= percentiles["p50"] <= 51.0
        assert 89.0 <= percentiles["p90"] <= 91.0
        assert 94.0 <= percentiles["p95"] <= 96.0
        assert 98.0 <= percentiles["p99"] <= 100.0

    def test_get_latency_percentiles_with_outliers(self):
        """Test percentiles handle outliers correctly."""
        mc = MetricsCollector()
        # Record 90 normal requests and 10 slow outliers
        for _ in range(90):
            mc.record_request(duration=50.0, success=True)
        for _ in range(10):
            mc.record_request(duration=500.0, success=True)

        percentiles = mc.get_summary()["latency_percentiles"]
        # p50 should be 50 (normal)
        # p90 should be around boundary between normal and slow
        # p95 and p99 should show the outliers
        assert percentiles["p50"] == 50.0
        assert percentiles["p90"] <= 100.0  # At the boundary
        assert percentiles["p95"] > 100.0   # Into the outliers
        assert percentiles["p99"] > 400.0   # Deep in the outliers


# ============================================================================
# MetricsCollector Summary Tests
# ============================================================================


class TestMetricsCollectorSummary:
    """Test get_summary method."""

    def test_get_summary_comprehensive(self):
        """Test comprehensive summary with all metrics."""
        mc = MetricsCollector()

        # Record various metrics
        for i in range(20):
            mc.record_request(
                duration=100.0 + i * 5,
                success=(i % 4 != 0),
                error_type="timeout" if i % 4 == 0 else None,
            )

        mc.record_rate_limit_utilization(0.8)
        mc.record_cache_hit()
        mc.record_cache_hit()
        mc.record_cache_miss()
        mc.record_circuit_state_change("closed", "open")

        summary = mc.get_summary()

        assert summary["total_requests"] == 20
        assert summary["success_count"] == 15
        assert summary["failure_count"] == 5
        assert summary["success_rate"] == 75.0
        assert summary["avg_latency_ms"] == 147.5  # Average of 100, 105, ..., 195
        assert "p50" in summary["latency_percentiles"]
        assert "p95" in summary["latency_percentiles"]
        assert summary["error_breakdown"]["timeout"] == 5
        assert summary["rate_limit_utilization"] == 0.8
        assert summary["cache_hit_ratio"] == pytest.approx(0.6667, rel=0.01)
        assert summary["circuit_breaker_transitions"] == 1

    def test_get_summary_includes_all_fields(self):
        """Test that summary includes all expected fields."""
        mc = MetricsCollector()
        summary = mc.get_summary()

        expected_fields = [
            "total_requests",
            "success_count",
            "failure_count",
            "success_rate",
            "avg_latency_ms",
            "latency_percentiles",
            "error_breakdown",
            "rate_limit_utilization",
            "cache_hit_ratio",
            "cache_hits",
            "cache_misses",
            "circuit_breaker_transitions",
        ]

        for field in expected_fields:
            assert field in summary, f"Missing field: {field}"


# ============================================================================
# MetricsCollector Reset Tests
# ============================================================================


class TestMetricsCollectorReset:
    """Test reset functionality."""

    def test_reset_clears_all_metrics(self):
        """Test that reset clears all metrics."""
        mc = MetricsCollector()

        # Record some metrics
        mc.record_request(duration=100.0, success=True)
        mc.record_request(duration=150.0, success=False, error_type="timeout")
        mc.record_rate_limit_utilization(0.5)
        mc.record_cache_hit()
        mc.record_cache_miss()
        mc.record_circuit_state_change("closed", "open")

        # Reset
        mc.reset()

        summary = mc.get_summary()
        assert summary["total_requests"] == 0
        assert summary["success_count"] == 0
        assert summary["failure_count"] == 0
        assert summary["error_breakdown"]["timeout"] == 0
        assert summary["rate_limit_utilization"] == 0.0
        assert summary["cache_hits"] == 0
        assert summary["cache_misses"] == 0
        assert summary["circuit_breaker_transitions"] == 0

    def test_reset_multiple_times(self):
        """Test that reset can be called multiple times."""
        mc = MetricsCollector()
        mc.reset()
        mc.reset()
        mc.record_request(duration=100.0, success=True)
        mc.reset()

        assert mc.request_count_total == 0


# ============================================================================
# MetricsCollector Thread Safety Tests
# ============================================================================


class TestMetricsCollectorThreadSafety:
    """Test thread safety of MetricsCollector."""

    def test_concurrent_record_request(self):
        """Test thread-safe request recording."""
        mc = MetricsCollector()
        errors = []

        def record():
            try:
                mc.record_request(duration=100.0, success=True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert mc.request_count_total == 100

    def test_concurrent_mixed_operations(self):
        """Test thread-safe mixed operations."""
        mc = MetricsCollector()
        errors = []

        def worker(i):
            try:
                mc.record_request(duration=float(i), success=(i % 2 == 0))
                mc.record_rate_limit_utilization(i / 100.0)
                if i % 2 == 0:
                    mc.record_cache_hit()
                else:
                    mc.record_cache_miss()
                mc.record_circuit_state_change("closed", "open")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert mc.request_count_total == 50
        assert mc.request_count_success == 25
        assert mc.request_count_failure == 25

    def test_concurrent_get_summary(self):
        """Test thread-safe summary retrieval."""
        mc = MetricsCollector()
        summaries = []
        lock = threading.Lock()

        def get_summary():
            for _ in range(10):
                summary = mc.get_summary()
                with lock:
                    summaries.append(summary)

        # Also record while reading
        def record():
            for i in range(100):
                mc.record_request(duration=float(i), success=True)

        threads = [threading.Thread(target=get_summary) for _ in range(5)]
        threads.append(threading.Thread(target=record))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(summaries) == 50  # 5 threads * 10 iterations
        # All summaries should be valid dicts
        for s in summaries:
            assert isinstance(s, dict)
            assert "total_requests" in s

    def test_concurrent_reset(self):
        """Test thread-safe reset during recording."""
        mc = MetricsCollector()
        final_count = [0]
        lock = threading.Lock()

        def record():
            for _ in range(50):
                mc.record_request(duration=100.0, success=True)
                with lock:
                    final_count[0] += 1

        def reset():
            for _ in range(10):
                time.sleep(0.001)  # Small delay to interleave
                mc.reset()

        threads = [threading.Thread(target=record) for _ in range(5)]
        threads.append(threading.Thread(target=reset))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Count should be consistent (either all recorded or reset in between)
        assert mc.request_count_total <= 250  # Max possible


# ============================================================================
# MetricsCollector Prometheus Export Tests
# ============================================================================


class TestMetricsCollectorPrometheusExport:
    """Test Prometheus format export."""

    def test_export_prometheus_empty(self):
        """Test Prometheus export with no metrics."""
        mc = MetricsCollector()
        output = mc.export_prometheus()
        assert output == ""

    def test_export_prometheus_basic_format(self):
        """Test Prometheus export basic format."""
        mc = MetricsCollector()
        mc.record_request(duration=100.0, success=True)
        mc.record_request(duration=150.0, success=False, error_type="timeout")

        output = mc.export_prometheus()

        assert "# HELP fr24_requests_total" in output
        assert "# TYPE fr24_requests_total counter" in output
        assert 'fr24_requests_total{status="success"} 1' in output
        assert 'fr24_requests_total{status="failure"} 1' in output

    def test_export_prometheus_errors(self):
        """Test Prometheus export error metrics."""
        mc = MetricsCollector()
        mc.record_request(duration=100.0, success=False, error_type="timeout")
        mc.record_request(duration=100.0, success=False, error_type="rate_limit")
        mc.record_request(duration=100.0, success=False, error_type="circuit_open")

        output = mc.export_prometheus()

        assert '# HELP fr24_errors_total' in output
        assert 'fr24_errors_total{type="timeout"} 1' in output
        assert 'fr24_errors_total{type="rate_limit"} 1' in output
        assert 'fr24_errors_total{type="circuit_open"} 1' in output

    def test_export_prometheus_latency(self):
        """Test Prometheus export latency metrics."""
        mc = MetricsCollector()
        for i in range(10):
            mc.record_request(duration=float(i * 10), success=True)

        output = mc.export_prometheus()

        assert "# HELP fr24_request_latency_ms" in output
        assert "fr24_request_latency_ms_count 10" in output
        assert "fr24_request_latency_ms_sum" in output
        assert 'fr24_request_latency_ms{quantile="0.50"}' in output
        assert 'fr24_request_latency_ms{quantile="0.95"}' in output

    def test_export_prometheus_cache_metrics(self):
        """Test Prometheus export cache metrics."""
        mc = MetricsCollector()
        mc.record_cache_hit()
        mc.record_cache_hit()
        mc.record_cache_miss()

        output = mc.export_prometheus()

        assert "# HELP fr24_cache_hits" in output
        assert "fr24_cache_hits 2" in output
        assert "# HELP fr24_cache_misses" in output
        assert "fr24_cache_misses 1" in output

    def test_export_prometheus_circuit_breaker(self):
        """Test Prometheus export circuit breaker metrics."""
        mc = MetricsCollector()
        mc.record_circuit_state_change("closed", "open")
        mc.record_circuit_state_change("open", "half-open")
        mc.record_circuit_state_change("half-open", "closed")

        output = mc.export_prometheus()

        assert "# HELP fr24_circuit_breaker_transitions" in output
        assert 'fr24_circuit_breaker_transitions{transition="closed_to_open"} 1' in output
        assert 'fr24_circuit_breaker_transitions{transition="open_to_half_open"} 1' in output
        assert 'fr24_circuit_breaker_transitions{transition="half_open_to_closed"} 1' in output


# ============================================================================
# FR24FlightService Integration Tests
# ============================================================================


class TestFR24FlightServiceMetricsIntegration:
    """Test metrics integration with FR24FlightService."""

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_service_records_successful_requests(self, mock_base_client):
        """Test that service records successful API requests."""
        from chemtrail.services.fr24_flight_service import FR24FlightService
        from datetime import datetime, timezone

        mock_sdk = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sdk.live.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        service = FR24FlightService(api_token="test")
        service.get_positions_near_time_and_location(
            timestamp=datetime.now(timezone.utc),
            lat=50.0,
            lon=10.0,
            limit=1,
        )

        metrics = service.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["success_count"] == 1

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_service_records_failed_requests(self, mock_base_client):
        """Test that service records failed API requests."""
        from chemtrail.services.fr24_flight_service import FR24FlightService
        from datetime import datetime, timezone

        mock_sdk = MagicMock()
        mock_sdk.live.get_full.side_effect = ConnectionError("API error")
        mock_base_client.return_value = mock_sdk

        service = FR24FlightService(api_token="test")

        with pytest.raises(ConnectionError):
            service.get_positions_near_time_and_location(
                timestamp=datetime.now(timezone.utc),
                lat=50.0,
                lon=10.0,
                limit=1,
            )

        metrics = service.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["failure_count"] == 1

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_service_records_circuit_open(self, mock_base_client):
        """Test that service records circuit open errors."""
        from chemtrail.services.fr24_flight_service import FR24FlightService
        from common.circuit_breaker import CircuitBreaker
        from datetime import datetime, timezone

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        mock_sdk = MagicMock()
        mock_sdk.live.get_full.side_effect = ConnectionError("API down")
        mock_base_client.return_value = mock_sdk

        service = FR24FlightService(api_token="test", circuit_breaker=cb)

        # Trip the circuit
        for _ in range(2):
            try:
                service.get_positions_near_time_and_location(
                    timestamp=datetime.now(timezone.utc),
                    lat=50.0,
                    lon=10.0,
                    limit=1,
                )
            except ConnectionError:
                pass

        # Circuit should be open, next call returns empty without API call
        result = service.get_positions_near_time_and_location(
            timestamp=datetime.now(timezone.utc),
            lat=50.0,
            lon=10.0,
            limit=1,
        )

        assert result == []
        metrics = service.get_metrics()
        assert metrics["error_breakdown"]["circuit_open"] >= 1

    def test_health_check_includes_metrics(self):
        """Test that health_check includes metrics summary."""
        from chemtrail.services.fr24_flight_service import FR24FlightService

        service = FR24FlightService(api_token="test")
        health = service.health_check()

        assert "metrics" in health
        assert "total_requests" in health["metrics"]
        assert "success_rate" in health["metrics"]
        assert "avg_latency_ms" in health["metrics"]
        assert "p95_latency_ms" in health["metrics"]
        assert "error_breakdown" in health["metrics"]
        assert "rate_limit_utilization" in health["metrics"]

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_service_metrics_reset(self, mock_base_client):
        """Test that service metrics can be reset."""
        from chemtrail.services.fr24_flight_service import FR24FlightService
        from datetime import datetime, timezone

        mock_sdk = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sdk.live.get_full.return_value = mock_response
        mock_base_client.return_value = mock_sdk

        service = FR24FlightService(api_token="test")
        service.get_positions_near_time_and_location(
            timestamp=datetime.now(timezone.utc),
            lat=50.0,
            lon=10.0,
            limit=1,
        )

        assert service.get_metrics()["total_requests"] == 1

        service.reset_metrics()

        assert service.get_metrics()["total_requests"] == 0
