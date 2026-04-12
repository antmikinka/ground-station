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

"""Circuit breaker pattern implementation for resilient API calls.

This module provides a production-grade circuit breaker implementation
to prevent cascade failures when external services (like FR24 API) are down.

Key features:
- Three states: CLOSED (normal), OPEN (failing), HALF-OPEN (testing recovery)
- Configurable thresholds for failure/success transitions
- Thread-safe state management using threading.Lock
- Structured logging for state transitions
- Context manager support for wrapping API calls

Circuit Breaker Pattern:
- CLOSED: Normal operation, requests pass through. Failures increment counter.
- OPEN: Circuit tripped, requests fail immediately without calling service.
- HALF-OPEN: Testing recovery, limited requests allowed to probe service health.

State Transitions:
- CLOSED -> OPEN: When consecutive failures reach failure_threshold
- OPEN -> HALF-OPEN: After recovery_timeout seconds have elapsed
- HALF-OPEN -> CLOSED: When consecutive successes reach success_threshold
- HALF-OPEN -> OPEN: When any request fails during recovery testing
"""

import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from common.common import logger
from common.fr24_logging import LoggingContext


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests.

    This exception indicates that the circuit breaker has tripped due to
    repeated failures and is not allowing requests through to the protected
    service.

    Attributes:
        message: Human-readable error message
        last_failure: Timestamp of the last failure that caused the circuit to open
        retry_after: Seconds until the circuit will transition to half-open state
    """
    def __init__(self, message: str, last_failure: Optional[datetime] = None, retry_after: Optional[float] = None):
        super().__init__(message)
        self.last_failure = last_failure
        self.retry_after = retry_after


T = TypeVar('T')


class CircuitBreaker:
    """Production-grade circuit breaker for resilient service calls.

    This circuit breaker protects against cascade failures when external
    services are experiencing issues. It tracks consecutive failures and
    temporarily stops sending requests when a failure threshold is reached.

    The circuit breaker is thread-safe and can be used in concurrent environments.

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait in OPEN state before transitioning to HALF-OPEN
        success_threshold: Number of consecutive successes in HALF-OPEN to close circuit
        name: Optional identifier for this circuit breaker instance

    Example:
        >>> cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        >>>
        >>> # Using as context manager
        >>> with cb:
        ...     result = call_external_service()
        >>>
        >>> # Using call() method
        >>> result = cb.call(call_external_service, arg1, arg2)
        >>>
        >>> # Check current state
        >>> print(cb.state)  # CircuitState.CLOSED
        >>> print(cb.failure_count)  # 0

    State Transitions:
        CLOSED -> OPEN: After failure_threshold consecutive failures
        OPEN -> HALF_OPEN: After recovery_timeout seconds
        HALF_OPEN -> CLOSED: After success_threshold consecutive successes
        HALF_OPEN -> OPEN: On any failure during recovery testing
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        name: Optional[str] = None,
    ):
        """Initialize circuit breaker with configurable thresholds.

        Args:
            failure_threshold: Consecutive failures before opening circuit (default: 5)
            recovery_timeout: Seconds in OPEN state before HALF-OPEN (default: 60)
            success_threshold: Consecutive successes in HALF-OPEN to close (default: 2)
            name: Optional identifier for logging purposes
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold
        self._name = name or "circuit_breaker"

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None

        # Thread safety
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN)
        """
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def failure_count(self) -> int:
        """Get current consecutive failure count.

        Returns:
            Number of consecutive failures
        """
        with self._lock:
            return self._failure_count

    @property
    def success_count(self) -> int:
        """Get current consecutive success count.

        Returns:
            Number of consecutive successes (relevant in HALF-OPEN state)
        """
        with self._lock:
            return self._success_count

    @property
    def last_failure_time(self) -> Optional[datetime]:
        """Get timestamp of last failure.

        Returns:
            datetime of last failure, or None if no failures recorded
        """
        with self._lock:
            return self._last_failure_time

    @property
    def failure_threshold(self) -> int:
        """Get failure threshold setting.

        Returns:
            Number of consecutive failures before opening circuit
        """
        return self._failure_threshold

    @property
    def recovery_timeout(self) -> float:
        """Get recovery timeout setting.

        Returns:
            Seconds to wait in OPEN state before transitioning to HALF-OPEN
        """
        return self._recovery_timeout

    @property
    def success_threshold(self) -> int:
        """Get success threshold setting.

        Returns:
            Number of consecutive successes in HALF-OPEN to close circuit
        """
        return self._success_threshold

    def _check_state_transition(self) -> None:
        """Check if state should transition based on timeouts.

        This method checks if the circuit should transition from OPEN to
        HALF-OPEN based on the recovery timeout. Must be called with lock held.

        Note:
            This method assumes the lock is already acquired.
        """
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
            if elapsed >= self._recovery_timeout:
                old_state = self._state
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(
                    f"Circuit breaker '{self._name}' transitioned from {old_state.value} to {self._state.value}",
                    extra={
                        "event": "circuit_breaker_transition",
                        "circuit_name": self._name,
                        "from_state": old_state.value,
                        "to_state": self._state.value,
                        "recovery_timeout_elapsed": elapsed,
                    }
                )

    def _record_success(self) -> None:
        """Record a successful call.

        Updates success/failure counters and handles state transitions.
        Must be called with lock held.

        Note:
            This method assumes the lock is already acquired.
        """
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                old_state = self._state
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info(
                    f"Circuit breaker '{self._name}' transitioned from {old_state.value} to {self._state.value}",
                    extra={
                        "event": "circuit_breaker_transition",
                        "circuit_name": self._name,
                        "from_state": old_state.value,
                        "to_state": self._state.value,
                        "success_threshold_reached": self._success_count,
                    }
                )
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success in CLOSED state
            if self._failure_count > 0:
                self._failure_count = 0
                logger.debug(
                    f"Circuit breaker '{self._name}' reset failure count on success",
                    extra={
                        "event": "circuit_breaker_success",
                        "circuit_name": self._name,
                        "state": self._state.value,
                    }
                )

    def _record_failure(self) -> None:
        """Record a failed call.

        Updates failure counters and handles state transitions.
        Must be called with lock held.

        Note:
            This method assumes the lock is already acquired.
        """
        self._last_failure_time = datetime.now(timezone.utc)

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in HALF-OPEN immediately opens the circuit
            old_state = self._state
            self._state = CircuitState.OPEN
            self._success_count = 0
            logger.warning(
                f"Circuit breaker '{self._name}' transitioned from {old_state.value} to {self._state.value}",
                extra={
                    "event": "circuit_breaker_transition",
                    "circuit_name": self._name,
                    "from_state": old_state.value,
                    "to_state": self._state.value,
                    "reason": "failure_during_recovery",
                }
            )
        elif self._state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                old_state = self._state
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self._name}' transitioned from {old_state.value} to {self._state.value}",
                    extra={
                        "event": "circuit_breaker_transition",
                        "circuit_name": self._name,
                        "from_state": old_state.value,
                        "to_state": self._state.value,
                        "failure_count": self._failure_count,
                        "failure_threshold": self._failure_threshold,
                    }
                )

    def _allow_request(self) -> bool:
        """Check if a request should be allowed through.

        Returns:
            True if request should proceed, False if it should be rejected

        Raises:
            CircuitOpenError: If circuit is OPEN and rejecting requests
        """
        self._check_state_transition()

        if self._state == CircuitState.CLOSED:
            return True
        elif self._state == CircuitState.HALF_OPEN:
            return True
        else:  # OPEN
            retry_after = None
            if self._last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
                retry_after = max(0, self._recovery_timeout - elapsed)

            raise CircuitOpenError(
                f"Circuit breaker '{self._name}' is OPEN. Requests are being rejected.",
                last_failure=self._last_failure_time,
                retry_after=retry_after,
            )

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with circuit breaker protection.

        This method wraps a function call with circuit breaker logic.
        If the circuit is OPEN, CircuitOpenError is raised immediately.
        Failures and successes are recorded to manage state transitions.

        Args:
            func: Function to execute
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func

        Returns:
            The return value of func

        Raises:
            CircuitOpenError: If circuit is OPEN
            Any exception raised by func (after recording the failure)

        Example:
            >>> cb = CircuitBreaker()
            >>> try:
            ...     result = cb.call(risky_api_call, url)
            ... except CircuitOpenError:
            ...     # Circuit is open, use fallback
            ...     result = get_cached_data()
            ... except APIError as e:
            ...     # API call failed, circuit recorded the failure
            ...     result = get_cached_data()
        """
        with self._lock:
            self._allow_request()

        try:
            result = func(*args, **kwargs)
            with self._lock:
                self._record_success()
            return result
        except CircuitOpenError:
            # Don't record CircuitOpenError as a failure
            raise
        except Exception as e:
            with self._lock:
                self._record_failure()
            raise

    def __enter__(self) -> "CircuitBreaker":
        """Enter the context manager.

        Returns:
            self

        Raises:
            CircuitOpenError: If circuit is OPEN when entering context

        Example:
            >>> cb = CircuitBreaker()
            >>> with cb:  # Calls __enter__
            ...     result = call_external_service()
        """
        with self._lock:
            self._allow_request()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """Exit the context manager.

        Records success or failure based on whether an exception was raised.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised

        Returns:
            False to propagate any exception, True to suppress it

        Example:
            >>> cb = CircuitBreaker()
            >>> with cb:  # __enter__ called
            ...     pass  # __exit__ called with None
        """
        with self._lock:
            if exc_type is None:
                # No exception - record success
                self._record_success()
            elif issubclass(exc_type, CircuitOpenError):
                # Don't record CircuitOpenError as a failure
                pass
            else:
                # Other exception - record failure
                self._record_failure()
        return False  # Propagate exception

    def reset(self) -> None:
        """Reset circuit breaker to initial CLOSED state.

        This clears all failure/success counts and resets the state to CLOSED.
        Useful for manual intervention or testing scenarios.

        Example:
            >>> cb = CircuitBreaker()
            >>> # ... circuit opens after failures
            >>> cb.reset()  # Manually reset to CLOSED
            >>> assert cb.state == CircuitState.CLOSED
        """
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

            if old_state != CircuitState.CLOSED:
                logger.info(
                    f"Circuit breaker '{self._name}' manually reset from {old_state.value} to CLOSED",
                    extra={
                        "event": "circuit_breaker_reset",
                        "circuit_name": self._name,
                        "from_state": old_state.value,
                    }
                )

    def get_state_info(self) -> dict:
        """Get comprehensive state information.

        Returns:
            Dictionary with current state and metrics:
            - state: Current CircuitState as string
            - failure_count: Current consecutive failure count
            - success_count: Current consecutive success count
            - last_failure: ISO format datetime of last failure or None
            - failure_threshold: Configured failure threshold
            - recovery_timeout: Configured recovery timeout
            - success_threshold: Configured success threshold

        Example:
            >>> cb = CircuitBreaker()
            >>> info = cb.get_state_info()
            >>> print(f"Circuit is {info['state']}")
        """
        with self._lock:
            self._check_state_transition()
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
                "success_threshold": self._success_threshold,
            }


# Module-level default circuit breaker instance
_default_circuit_breaker: Optional[CircuitBreaker] = None
_default_circuit_lock = threading.Lock()


def get_default_circuit_breaker() -> CircuitBreaker:
    """Get or create the default module-level circuit breaker.

    Returns:
        The default CircuitBreaker instance, creating it if necessary.

    Example:
        >>> cb = get_default_circuit_breaker()
        >>> with cb:
        ...     make_api_call()
    """
    global _default_circuit_breaker
    with _default_circuit_lock:
        if _default_circuit_breaker is None:
            _default_circuit_breaker = CircuitBreaker(name="fr24_default")
        return _default_circuit_breaker


def reset_default_circuit_breaker() -> None:
    """Reset the default circuit breaker to initial state.

    This is useful for testing or manual recovery scenarios.
    """
    global _default_circuit_breaker
    with _default_circuit_lock:
        if _default_circuit_breaker is not None:
            _default_circuit_breaker.reset()
            _default_circuit_breaker = None
