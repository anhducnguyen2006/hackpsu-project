"""Process-local request limits for authenticated, expensive routes.

Counters live in this worker process only. They reset on restart and are not
shared with other workers or machines. This is not distributed enforcement.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import threading
import time

from fastapi import HTTPException

from app.config import settings


class PrincipalLimiter:
    def __init__(self, *, max_calls: int, window_seconds: float, max_in_flight: int) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.max_in_flight = max_in_flight
        self._events: dict[str, list[float]] = {}
        self._in_flight: dict[str, int] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._in_flight.clear()

    @contextmanager
    def limit(self, subject: str) -> Iterator[None]:
        self._acquire(subject)
        try:
            yield
        finally:
            self._release(subject)

    def _acquire(self, subject: str) -> None:
        now = time.monotonic()
        with self._lock:
            inflight = self._in_flight.get(subject, 0)
            if inflight >= self.max_in_flight:
                raise HTTPException(
                    status_code=429,
                    detail="Too many concurrent requests for this account.",
                )
            window_start = now - self.window_seconds
            recent = [stamp for stamp in self._events.get(subject, []) if stamp >= window_start]
            if len(recent) >= self.max_calls:
                self._events[subject] = recent
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests for this account. Try again later.",
                )
            recent.append(now)
            self._events[subject] = recent
            self._in_flight[subject] = inflight + 1

    def _release(self, subject: str) -> None:
        with self._lock:
            current = self._in_flight.get(subject, 0)
            if current <= 1:
                self._in_flight.pop(subject, None)
            else:
                self._in_flight[subject] = current - 1


discovery_gate = PrincipalLimiter(
    max_calls=settings.auth_discovery_limit,
    window_seconds=settings.auth_discovery_window_seconds,
    max_in_flight=settings.auth_discovery_concurrency,
)
analysis_gate = PrincipalLimiter(
    max_calls=settings.auth_analysis_limit,
    window_seconds=settings.auth_analysis_window_seconds,
    max_in_flight=settings.auth_analysis_concurrency,
)
similarity_gate = PrincipalLimiter(
    max_calls=settings.auth_similarity_limit,
    window_seconds=settings.auth_similarity_window_seconds,
    max_in_flight=settings.auth_similarity_concurrency,
)
