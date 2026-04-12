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

"""Tests for circuit breaker pattern implementation."""

import pytest
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from common.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    get_default_circuit_breaker,
    reset_default_circuit_breaker,
)


# ============================================================================
# CircuitBreaker Basic Tests
# ============================================================================


class TestCircuitBreakerInitialization:
    """Test CircuitBreaker initialization and configuration."""

    def test_init_default_values(self):
        """Test circuit breaker initializes with default values."""
        cb = CircuitBreaker()

        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
        assert cb.success_threshold == 2
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.last_failure_time is None

    def test_init_custom_values(self):
        """Test circuit breaker initializes with custom values."""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=4,
            name="test_circuit",
        )

        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0
        assert cb.success_threshold == 4
        assert cb.state == CircuitState.CLOSED

    def test_init_with_name(self):
        """Test circuit breaker name is set correctly."""
        cb = CircuitBreaker(name="fr24_service")
        # Name is used internally for logging
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Test that initial state is CLOSED."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_closed_to_open_on_failure_threshold(self):
        """Test transition from CLOSED to OPEN after failure_threshold failures."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record failures up to threshold
        for i in range(3):
            with pytest.raises(ValueError):
                with cb:
                    raise ValueError(f"Test failure {i}")
                assert cb.state == CircuitState.CLOSED

        # After 3rd failure, should be OPEN
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_open_to_half_open_after_recovery_timeout(self):
        """Test transition from OPEN to HALF-OPEN after recovery_timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Trip the circuit
        for _ in range(2):
            try:
                with cb:
                    raise ValueError("failure")
            except ValueError:
                pass

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Accessing state should trigger transition to HALF-OPEN
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success_threshold(self):
        """Test transition from HALF-OPEN to CLOSED after success_threshold successes."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, success_threshold=2)

        # Trip the circuit
        for _ in range(2):
            try:
                with cb:
                    raise ValueError("failure")
            except ValueError:
                pass

        # Wait for recovery timeout
        time.sleep(0.15)

        # Verify HALF-OPEN state
        assert cb.state == CircuitState.HALF_OPEN

        # Record successes
        for _ in range(2):
            with cb:
                pass  # Success

        # Should be CLOSED now
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_half_open_to_open_on_failure(self):
        """Test transition from HALF-OPEN to OPEN on any failure."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, success_threshold=2)

        # Trip the circuit
        for _ in range(2):
            try:
                with cb:
                    raise ValueError("failure")
            except ValueError:
                pass

        # Wait for recovery timeout
        time.sleep(0.15)

        # Verify HALF-OPEN state
        assert cb.state == CircuitState.HALF_OPEN

        # Record one failure in HALF-OPEN
        try:
            with cb:
                raise ValueError("failure during recovery")
        except ValueError:
            pass

        # Should be OPEN again
        assert cb.state == CircuitState.OPEN

    def test_closed_resets_failure_count_on_success(self):
        """Test that successes in CLOSED state reset failure count."""
        cb = CircuitBreaker(failure_threshold=5)

        # Record some failures
        for _ in range(3):
            try:
                with cb:
                    raise ValueError("failure")
            except ValueError:
                pass

        assert cb.failure_count == 3

        # Record a success
        with cb:
            pass

        # Failure count should be reset
        assert cb.failure_count == 0


class TestCircuitBreakerCallMethod:
    """Test CircuitBreaker.call() method."""

    def test_call_with_successful_function(self):
        """Test call() executes function and records success."""
        cb = CircuitBreaker()

        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_call_with_failing_function(self):
        """Test call() records failure when function raises."""
        cb = CircuitBreaker(failure_threshold=2)

        def fail_func():
            raise RuntimeError("test error")

        with pytest.raises(RuntimeError):
            cb.call(fail_func)

        assert cb.failure_count == 1

    def test_call_with_arguments(self):
        """Test call() passes arguments correctly."""
        cb = CircuitBreaker()

        def add(a, b, c=0):
            return a + b + c

        result = cb.call(add, 1, 2, c=3)
        assert result == 6

    def test_call_rejects_when_open(self):
        """Test call() raises CircuitOpenError when circuit is OPEN."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10)

        # Trip the circuit
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
            except ValueError:
                pass

        assert cb.state == CircuitState.OPEN

        # Should raise CircuitOpenError
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.call(lambda: "should not execute")

        assert "OPEN" in str(exc_info.value)
        assert exc_info.value.retry_after is not None


class TestCircuitBreakerContextManager:
    """Test CircuitBreaker as context manager."""

    def test_context_manager_success(self):
        """Test context manager records success on normal exit."""
        cb = CircuitBreaker()

        with cb:
            result = 2 + 2

        assert result == 4
        assert cb.state == CircuitState.CLOSED

    def test_context_manager_failure(self):
        """Test context manager records failure on exception."""
        cb = CircuitBreaker(failure_threshold=2)

        with pytest.raises(ValueError):
            with cb:
                raise ValueError("test error")

        assert cb.failure_count == 1

    def test_context_manager_rejects_when_open(self):
        """Test context manager raises CircuitOpenError when entering OPEN circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10)

        # Trip the circuit
        try:
            with cb:
                raise ValueError("trip")
        except ValueError:
            pass

        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitOpenError):
            with cb:
                pass  # Should not execute

    def test_context_manager_does_not_record_circuit_open_error(self):
        """Test that CircuitOpenError is not recorded as a failure."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10)

        # Trip the circuit
        try:
            with cb:
                raise ValueError("trip")
        except ValueError:
            pass

        assert cb.failure_count == 1

        # Try to enter open circuit multiple times
        for _ in range(3):
            with pytest.raises(CircuitOpenError):
                with cb:
                    pass

        # Failure count should still be 1
        assert cb.failure_count == 1


# ============================================================================
# CircuitBreaker Thread Safety Tests
# ============================================================================


class TestCircuitBreakerThreadSafety:
    """Test circuit breaker thread safety."""

    def test_concurrent_failures(self):
        """Test thread-safe handling of concurrent failures."""
        cb = CircuitBreaker(failure_threshold=10)
        errors = []

        def fail():
            try:
                with cb:
                    raise ValueError("failure")
            except (ValueError, CircuitOpenError):
                # Both ValueError (from the raise) and CircuitOpenError (from open circuit) are expected
                pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Should have recorded 10 failures and opened
        assert cb.state == CircuitState.OPEN

    def test_concurrent_successes(self):
        """Test thread-safe handling of concurrent successes."""
        cb = CircuitBreaker()
        errors = []

        def succeed():
            try:
                with cb:
                    pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=succeed) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cb.state == CircuitState.CLOSED

    def test_concurrent_state_transitions(self):
        """Test thread-safe state transitions."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=0.05, success_threshold=2)
        results = {"successes": 0, "failures": 0, "circuit_open": 0}
        lock = threading.Lock()

        def worker(should_fail):
            try:
                with cb:
                    if should_fail:
                        raise ValueError("failure")
                with lock:
                    results["successes"] += 1
            except CircuitOpenError:
                with lock:
                    results["circuit_open"] += 1
            except ValueError:
                with lock:
                    results["failures"] += 1

        # Mix of failing and succeeding threads
        threads = []
        for i in range(50):
            should_fail = i % 3 == 0  # Every third thread fails
            threads.append(threading.Thread(target=worker, args=(should_fail,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All operations should complete without errors
        total = results["successes"] + results["failures"] + results["circuit_open"]
        assert total == 50


# ============================================================================
# CircuitBreaker Reset Tests
# ============================================================================


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    def test_reset_from_open(self):
        """Test reset transitions from OPEN to CLOSED."""
        cb = CircuitBreaker(failure_threshold=2)

        # Trip the circuit
        for _ in range(2):
            try:
                with cb:
                    raise ValueError("failure")
            except ValueError:
                pass

        assert cb.state == CircuitState.OPEN

        # Reset
        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.last_failure_time is None

    def test_reset_from_half_open(self):
        """Test reset transitions from HALF-OPEN to CLOSED."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Trip the circuit
        for _ in range(2):
            try:
                with cb:
                    raise ValueError("failure")
            except ValueError:
                pass

        # Wait for HALF-OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Reset
        cb.reset()

        assert cb.state == CircuitState.CLOSED

    def test_reset_from_closed(self):
        """Test reset from CLOSED state is idempotent."""
        cb = CircuitBreaker()

        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


# ============================================================================
# CircuitBreaker State Info Tests
# ============================================================================


class TestCircuitBreakerStateInfo:
    """Test get_state_info method."""

    def test_get_state_info_closed(self):
        """Test state info in CLOSED state."""
        cb = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=2,
        )

        info = cb.get_state_info()

        assert info["state"] == "closed"
        assert info["failure_count"] == 0
        assert info["success_count"] == 0
        assert info["last_failure"] is None
        assert info["failure_threshold"] == 5
        assert info["recovery_timeout"] == 60.0
        assert info["success_threshold"] == 2

    def test_get_state_info_open(self):
        """Test state info in OPEN state."""
        cb = CircuitBreaker(failure_threshold=1)

        # Trip the circuit
        try:
            with cb:
                raise ValueError("failure")
        except ValueError:
            pass

        info = cb.get_state_info()

        assert info["state"] == "open"
        assert info["failure_count"] == 1
        assert info["last_failure"] is not None

    def test_get_state_info_half_open(self):
        """Test state info in HALF-OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        # Trip the circuit
        try:
            with cb:
                raise ValueError("failure")
        except ValueError:
            pass

        # Wait for HALF-OPEN
        time.sleep(0.15)

        info = cb.get_state_info()

        assert info["state"] == "half-open"


# ============================================================================
# CircuitBreaker Default Instance Tests
# ============================================================================


class TestDefaultCircuitBreaker:
    """Test default circuit breaker functions."""

    def test_get_default_creates_new(self):
        """Test get_default_circuit_breaker creates new instance."""
        reset_default_circuit_breaker()
        cb = get_default_circuit_breaker()

        assert isinstance(cb, CircuitBreaker)
        assert cb.state == CircuitState.CLOSED

    def test_get_default_returns_same_instance(self):
        """Test get_default_circuit_breaker returns same instance."""
        reset_default_circuit_breaker()
        cb1 = get_default_circuit_breaker()
        cb2 = get_default_circuit_breaker()

        assert cb1 is cb2

    def test_reset_default_clears_instance(self):
        """Test reset_default_circuit_breaker clears the instance."""
        reset_default_circuit_breaker()
        get_default_circuit_breaker()
        reset_default_circuit_breaker()
        cb = get_default_circuit_breaker()

        # Should be a fresh instance
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


# ============================================================================
# CircuitBreaker FR24 Integration Tests
# ============================================================================


class TestCircuitBreakerFR24Integration:
    """Test circuit breaker integration with FR24 services."""

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_fr24_service_with_circuit_breaker(self, mock_base_client):
        """Test FR24FlightService uses circuit breaker."""
        from chemtrail.services.fr24_flight_service import FR24FlightService

        # Setup mock to fail
        mock_sdk = MagicMock()
        mock_sdk.live.get_full.side_effect = ConnectionError("API down")
        mock_base_client.return_value = mock_sdk

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        service = FR24FlightService(api_token="test", circuit_breaker=cb)

        # Trigger failures
        for _ in range(3):
            try:
                service.get_positions_near_time_and_location(
                    timestamp=datetime.now(timezone.utc),
                    lat=50.0,
                    lon=10.0,
                    limit=1,
                )
            except (ConnectionError, CircuitOpenError):
                pass

        # Circuit should be OPEN
        assert cb.state == CircuitState.OPEN

        # Subsequent calls should return empty list immediately
        result = service.get_positions_near_time_and_location(
            timestamp=datetime.now(timezone.utc),
            lat=50.0,
            lon=10.0,
            limit=1,
        )

        assert result == []

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_fr24_service_health_check_includes_circuit_state(self, mock_base_client):
        """Test health_check includes circuit breaker state."""
        from chemtrail.services.fr24_flight_service import FR24FlightService

        service = FR24FlightService(api_token="test")

        health = service.health_check()

        assert "circuit_breaker" in health
        assert "state" in health["circuit_breaker"]
        assert "failure_count" in health["circuit_breaker"]
        assert "last_failure" in health["circuit_breaker"]
        assert health["circuit_breaker"]["state"] in ["closed", "open", "half-open"]

    @patch("chemtrail.api.fr24_client.FR24BaseClient")
    def test_fr24_client_with_circuit_breaker(self, mock_base_client):
        """Test FR24Client wraps calls with circuit breaker."""
        from chemtrail.api.fr24_client import FR24Client

        cb = CircuitBreaker(failure_threshold=2)
        mock_sdk = MagicMock()
        mock_sdk.live.get_full.side_effect = ConnectionError("API down")
        mock_base_client.return_value = mock_sdk

        with FR24Client(api_token="test", circuit_breaker=cb) as client:
            # Trigger failures
            for _ in range(2):
                try:
                    client.get_live_positions(limit=1)
                except (ConnectionError, CircuitOpenError):
                    pass

            # Circuit should be OPEN
            assert cb.state == CircuitState.OPEN

            # Next call should raise CircuitOpenError
            with pytest.raises(CircuitOpenError):
                client.get_live_positions(limit=1)

    def test_fr24_config_circuit_breaker_settings(self):
        """Test FR24Config includes circuit breaker settings."""
        from chemtrail.services.fr24_flight_service import FR24Config
        import os

        # Save original env
        original = {
            "failure": os.environ.get("FR24_CB_FAILURE_THRESHOLD"),
            "recovery": os.environ.get("FR24_CB_RECOVERY_TIMEOUT"),
            "success": os.environ.get("FR24_CB_SUCCESS_THRESHOLD"),
        }

        try:
            os.environ["FR24_CB_FAILURE_THRESHOLD"] = "10"
            os.environ["FR24_CB_RECOVERY_TIMEOUT"] = "120"
            os.environ["FR24_CB_SUCCESS_THRESHOLD"] = "5"

            config = FR24Config.from_env()

            assert config.cb_failure_threshold == 10
            assert config.cb_recovery_timeout == 120.0
            assert config.cb_success_threshold == 5
        finally:
            # Restore original env
            for key, value in original.items():
                if value is not None:
                    os.environ[f"FR24_CB_{key.upper()}"] = value
                else:
                    os.environ.pop(f"FR24_CB_{key.upper()}", None)


# ============================================================================
# CircuitBreaker Edge Cases
# ============================================================================


class TestCircuitBreakerEdgeCases:
    """Test circuit breaker edge cases."""

    def test_zero_failure_threshold(self):
        """Test circuit opens immediately with failure_threshold=0."""
        cb = CircuitBreaker(failure_threshold=0)

        # Should already be at threshold
        try:
            with cb:
                raise ValueError("failure")
        except ValueError:
            pass

        assert cb.state == CircuitState.OPEN

    def test_recovery_timeout_zero(self):
        """Test immediate transition to HALF-OPEN with recovery_timeout=0."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)

        # Trip the circuit
        try:
            with cb:
                raise ValueError("failure")
        except ValueError:
            pass

        # Circuit is OPEN immediately after failure
        # But accessing state triggers _check_state_transition which moves to HALF-OPEN
        # This is expected behavior - state property always returns current effective state
        state = cb.state
        assert state in (CircuitState.OPEN, CircuitState.HALF_OPEN)

        # With recovery_timeout=0, state should immediately be HALF-OPEN
        assert cb.state == CircuitState.HALF_OPEN

    def test_circuit_open_error_has_retry_after(self):
        """Test CircuitOpenError includes retry_after information."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30)

        # Trip the circuit
        try:
            with cb:
                raise ValueError("failure")
        except ValueError:
            pass

        with pytest.raises(CircuitOpenError) as exc_info:
            with cb:
                pass

        assert exc_info.value.retry_after is not None
        assert 0 < exc_info.value.retry_after <= 30

    def test_nested_context_managers(self):
        """Test nested context manager usage."""
        cb = CircuitBreaker()

        with cb:
            with cb:
                pass
            pass

        assert cb.state == CircuitState.CLOSED

    def test_exception_with_no_message(self):
        """Test handling exceptions without error messages."""
        cb = CircuitBreaker(failure_threshold=2)

        class SilentException(Exception):
            pass

        try:
            with cb:
                raise SilentException()
        except SilentException:
            pass

        assert cb.failure_count == 1
