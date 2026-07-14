#!/usr/bin/env python3
"""
CortexLLM Reliability Wrappers — retry decorator and circuit breaker.

Retry decorator:
  - Transient errors only (network, timeout, rate-limit)
  - Exponential backoff + jitter
  - No retry on auth/malformed-request errors
  - Configurable max retries and base delay

Circuit breaker:
  - Halt and alert after N consecutive tool failures
  - No infinite retry loops
  - Auto-reset after cooldown period
  - Per-tool tracking

Usage:
    from reliability import retry, circuit_breaker

    @retry(max_retries=3, base_delay=1.0)
    def call_llm(prompt):
        ...

    cb = CircuitBreaker(name="web_search", threshold=5)
    async with cb:
        result = await search_web(query)
"""

import asyncio
import functools
import json
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type, Union

from cortexllm_db import db

# ---------------------------------------------------------------------------
# Retry Decorator
# ---------------------------------------------------------------------------

# Error types that should NOT be retried (auth, bad request, etc.)
NON_RETRYABLE_EXCEPTIONS = (
    PermissionError,
    ValueError,
    json.JSONDecodeError,
)

# Status codes that should NOT be retried
NON_RETRYABLE_STATUSES = {400, 401, 403, 404, 422}


def is_retryable(error: Exception) -> bool:
    """Determine if an error is transient and should be retried."""
    if isinstance(error, NON_RETRYABLE_EXCEPTIONS):
        return False
    # Connection/timeout errors are always retryable
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True
    # Check for common transient error messages
    msg = str(error).lower()
    transient_patterns = [
        "timeout", "timed out", "connection refused", "connection reset",
        "rate limit", "too many requests", "429", "503", "502", "504",
        "service unavailable", "temporarily", "try again", "retry",
        "internal server error", "bad gateway", "gateway timeout",
    ]
    return any(p in msg for p in transient_patterns)


def retry(max_retries: int = 3, base_delay: float = 1.0,
          backoff_factor: float = 2.0, jitter: float = 0.1,
          on_retry: Callable = None):
    """Decorator: retry on transient errors with exponential backoff + jitter.

    Args:
        max_retries: Maximum number of retry attempts (default 3)
        base_delay: Initial delay in seconds (default 1.0)
        backoff_factor: Multiplier for each retry (default 2.0)
        jitter: Random jitter fraction (default 0.1 = 10%)
        on_retry: Optional callback(attempt, error, delay) for logging

    Usage:
        @retry(max_retries=3, base_delay=1.0)
        def fetch_data(url):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if not is_retryable(e) or attempt >= max_retries:
                        raise
                    delay = base_delay * (backoff_factor ** attempt)
                    # Add jitter: random ±jitter%
                    delay *= 1 + random.uniform(-jitter, jitter)
                    if on_retry:
                        on_retry(attempt + 1, e, delay)
                    time.sleep(delay)
            raise last_error  # Should not reach here

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if not is_retryable(e) or attempt >= max_retries:
                        raise
                    delay = base_delay * (backoff_factor ** attempt)
                    delay *= 1 + random.uniform(-jitter, jitter)
                    if on_retry:
                        on_retry(attempt + 1, e, delay)
                    await asyncio.sleep(delay)
            raise last_error

        # Return appropriate wrapper based on whether func is a coroutine
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreakerState:
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing — requests blocked
    HALF_OPEN = "half_open" # Testing if recovered


class CircuitBreaker:
    """Circuit breaker for tool/model failures.

    Prevents infinite retry loops by opening the circuit after N consecutive
    failures. Auto-resets to half-open after cooldown period.

    Usage:
        cb = CircuitBreaker(name="web_search", threshold=5)
        with cb:
            result = search_web(query)
    """

    def __init__(self, name: str, threshold: int = 5,
                 cooldown_seconds: int = 60,
                 half_open_max_tries: int = 1):
        self.name = name
        self.threshold = threshold
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.half_open_max_tries = half_open_max_tries

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_tries = 0
        self._state_file = Path(os.environ.get(
            "CORTEXLLM_DIR", str(Path.home() / ".config/cortexllm")
        )) / "circuit_breakers.json"

        self._load_state()

    # ------------------------------------------------------------------
    # Context manager interface
    # ------------------------------------------------------------------

    def __enter__(self):
        self._check_state()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # An error occurred
            self._record_failure()
            if is_retryable(exc_val):
                # Transient — let the retry decorator handle it
                return False
            # Non-retryable — count as circuit failure
            return False
        # Success
        self._record_success()
        return False

    async def __aenter__(self):
        self._check_state()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _check_state(self):
        """Check current circuit state and transition if needed."""
        now = datetime.now()

        if self._state == CircuitBreakerState.OPEN:
            # Check if cooldown has elapsed
            if (self._last_failure_time and
                    now - self._last_failure_time > self.cooldown):
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_tries = 0
                self._save_state()
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Cooldown expires at "
                    f"{(self._last_failure_time + self.cooldown).strftime('%H:%M:%S')}"
                )

        if self._state == CircuitBreakerState.HALF_OPEN:
            if self._half_open_tries >= self.half_open_max_tries:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is HALF_OPEN and "
                    f"has used all test attempts"
                )
            self._half_open_tries += 1

    def _record_failure(self):
        """Record a failure and potentially open the circuit."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._failure_count >= self.threshold:
            self._state = CircuitBreakerState.OPEN
            self._log_event("circuit_opened",
                            f"Opened after {self._failure_count} failures")

        self._save_state()

    def _record_success(self):
        """Record a success and potentially close the circuit."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._half_open_tries = 0
            self._log_event("circuit_closed",
                            "Closed after successful half-open test")
        elif self._failure_count > 0:
            # Partial recovery — reduce failure count
            self._failure_count = max(0, self._failure_count - 1)

        self._save_state()

    def _log_event(self, event_type: str, message: str):
        """Log circuit breaker event."""
        try:
            db.log_event(
                profile="system",
                event_type=f"circuit_breaker_{event_type}",
                event_data={
                    "breaker": self.name,
                    "state": self._state,
                    "failures": self._failure_count,
                    "message": message,
                }
            )
        except Exception:
            pass  # Non-critical

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self):
        """Load circuit breaker state from disk."""
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                breaker_data = data.get(self.name, {})
                self._state = breaker_data.get("state", CircuitBreakerState.CLOSED)
                self._failure_count = breaker_data.get("failures", 0)
                last_failure = breaker_data.get("last_failure")
                if last_failure:
                    self._last_failure_time = datetime.fromisoformat(last_failure)
                self._half_open_tries = breaker_data.get("half_open_tries", 0)
        except Exception:
            pass

    def _save_state(self):
        """Save circuit breaker state to disk."""
        try:
            data = {}
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
            data[self.name] = {
                "state": self._state,
                "failures": self._failure_count,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "half_open_tries": self._half_open_tries,
                "updated": datetime.now().isoformat(),
            }
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._state == CircuitBreakerState.OPEN

    @property
    def state(self) -> str:
        return self._state

    def reset(self):
        """Manually reset the circuit breaker."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_tries = 0
        self._save_state()
        self._log_event("circuit_reset", "Manually reset")


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is open and blocking requests."""
    pass


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, threshold: int = 5,
                        cooldown_seconds: int = 60) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name, threshold=threshold,
            cooldown_seconds=cooldown_seconds
        )
    return _circuit_breakers[name]


def reset_all_circuit_breakers():
    """Reset all circuit breakers."""
    for cb in _circuit_breakers.values():
        cb.reset()
    _circuit_breakers.clear()