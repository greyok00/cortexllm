#!/usr/bin/env python3
"""
CortexLLM Gateway Client — shared HTTP client for the browser automation gateway.

Wraps all Gateway API calls with:
  - Retry decorator (exponential backoff + jitter)
  - Circuit breaker (halts after N consecutive failures)
  - Event logging (appears in observability dashboard)

Usage:
    from gateway_client import GatewayClient
    gw = GatewayClient()
    result = gw.navigate("https://example.com")
    result = gw.click("button.submit")
    result = gw.type_text("#search", "query")
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent))
from cortexllm_db import db
from reliability import retry, get_circuit_breaker, CircuitBreakerOpenError


class GatewayError(Exception):
    """Raised when the gateway returns an error response."""
    pass


def _log_retry(attempt: int, error: Exception, delay: float):
    """Static retry callback for gateway calls."""
    try:
        db.log_event(
            profile="system",
            event_type="gateway_retry",
            event_data={"attempt": attempt, "error": str(error)[:200], "delay": round(delay, 2)},
        )
    except Exception:
        pass


class GatewayClient:
    """HTTP client for the browser automation gateway with reliability wrappers."""

    def __init__(self, base_url: str = None,
                 token: str = "",
                 worker_name: str = "gateway"):
        self.base_url = (base_url or os.environ.get(
            "CORTEXLLM_GATEWAY_URL", "http://127.0.0.1:18789"
        )).rstrip("/")
        self.token = token or os.environ.get("CORTEXLLM_GATEWAY_TOKEN", "")
        self.worker_name = worker_name
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self._cb = get_circuit_breaker(f"gateway:{worker_name}", threshold=5, cooldown_seconds=60)

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> Dict:
        """Navigate the browser to a URL."""
        return self._gateway_call("POST", "navigate", {"url": url})

    def click(self, selector: str) -> Dict:
        """Click an element on the page."""
        return self._gateway_call("POST", "click", {"selector": selector})

    def type_text(self, selector: str, text: str) -> Dict:
        """Type text into an input field."""
        return self._gateway_call("POST", "type", {"selector": selector, "text": text})

    def snapshot(self) -> Dict:
        """Get the current page snapshot (accessibility tree)."""
        return self._gateway_call("GET", "snapshot")

    def screenshot(self) -> bytes:
        """Take a screenshot of the current page."""
        result = self._gateway_call("GET", "screenshot", raw=True)
        return result

    def evaluate(self, script: str) -> Dict:
        """Run JavaScript in the browser."""
        return self._gateway_call("POST", "evaluate", {"script": script})

    def wait_for(self, selector: str, timeout: int = 10) -> Dict:
        """Wait for an element to appear."""
        return self._gateway_call("POST", "wait", {"selector": selector, "timeout": timeout})

    def get_status(self) -> Dict:
        """Get gateway connection status."""
        return self._gateway_call("GET", "status")

    # ------------------------------------------------------------------
    # Internal gateway call with reliability wrappers
    # ------------------------------------------------------------------

    def _gateway_call(self, method: str, endpoint: str,
                      data: dict = None, raw: bool = False) -> Any:
        """Make a gateway API call with circuit breaker and retry."""
        # Check circuit breaker first
        if self._cb.is_open:
            raise CircuitBreakerOpenError(
                f"Gateway circuit breaker is OPEN for {self.worker_name}"
            )

        try:
            return self._do_call(method, endpoint, data, raw)
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            # Circuit breaker will record this
            raise

    @retry(max_retries=3, base_delay=1.0, on_retry=_log_retry)
    def _do_call(self, method: str, endpoint: str,
                 data: dict = None, raw: bool = False) -> Any:
        """The actual HTTP call with retry logic."""
        url = f"{self.base_url}/{endpoint}"
        headers = dict(self._headers)

        if data is not None:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
        else:
            req = urllib.request.Request(url, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if raw:
                    return resp.read()
                response_data = json.loads(resp.read().decode("utf-8"))
                if response_data.get("error"):
                    raise GatewayError(response_data["error"])
                return response_data
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8", errors="replace")
            if status in (400, 401, 403, 404, 422):
                raise  # Non-retryable
            raise GatewayError(f"HTTP {status}: {body}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise  # Retryable

    def _log_retry(self, attempt: int, error: Exception, delay: float):
        """Log retry attempts for observability."""
        try:
            db.log_event(
                profile=f"worker:{self.worker_name}",
                event_type="gateway_retry",
                event_data={
                    "attempt": attempt,
                    "error": str(error)[:200],
                    "delay": round(delay, 2),
                },
            )
        except Exception:
            pass
