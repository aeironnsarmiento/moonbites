from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from typing import Deque


WINDOW_SECONDS = 60.0
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_OPEN_SECONDS = 300.0


class GeminiGuardrails:
    def __init__(self) -> None:
        self._calls_by_key: defaultdict[str, Deque[float]] = defaultdict(deque)
        self._failure_count = 0
        self._circuit_open_until: float | None = None
        self._lock = Lock()

    def allow_call(self, key: str, *, limit: int, now: float) -> tuple[bool, str | None]:
        with self._lock:
            if self._circuit_open_until is not None:
                if now < self._circuit_open_until:
                    return False, "circuit_open"
                self._circuit_open_until = None

            timestamps = self._calls_by_key[key]
            self._prune_old_calls(timestamps, now)

            if len(timestamps) >= limit:
                return False, "rate_limited"

            timestamps.append(now)
            return True, None

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0

    def record_failure(self, now: float) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= CIRCUIT_FAILURE_THRESHOLD:
                self._circuit_open_until = now + CIRCUIT_OPEN_SECONDS
                self._failure_count = 0

    def _prune_old_calls(self, timestamps: Deque[float], now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()


gemini_guardrails = GeminiGuardrails()
