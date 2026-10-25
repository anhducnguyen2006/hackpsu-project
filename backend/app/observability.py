from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any


_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def set_request_id(value: str) -> Any:
    return _request_id.set(value)


def reset_request_id(token: Any) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


def timed_log(
    logger: logging.Logger,
    operation: str,
    started: float,
    *,
    status: str = "ok",
    **fields: object,
) -> None:
    """Emit bounded timing metadata without logging payloads or secrets."""
    logger.info(
        "timing request_id=%s operation=%s elapsed_ms=%.1f status=%s%s",
        get_request_id(),
        operation,
        (time.perf_counter() - started) * 1000,
        status,
        "".join(f" {key}={value}" for key, value in fields.items()),
    )
