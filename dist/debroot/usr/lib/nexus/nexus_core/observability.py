from __future__ import annotations

import json
import logging
import time
import uuid
from collections import Counter
from contextvars import ContextVar
from typing import Any

try:
    from fastapi import Request
except ModuleNotFoundError:  # pragma: no cover - allows lightweight CLI commands
    Request = Any


correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
metrics_counter: Counter[str] = Counter()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = (
            getattr(record, "correlation_id", None) or correlation_id_var.get()
        )
        if correlation_id:
            payload["correlation_id"] = correlation_id
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        root.addHandler(handler)
    for handler in root.handlers:
        handler.setFormatter(JsonFormatter())
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str = "nexus") -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"extra_fields": fields})


def increment_metric(name: str, value: int = 1) -> None:
    metrics_counter[name] += value


def get_metrics_snapshot() -> dict[str, int]:
    return dict(metrics_counter)


async def correlation_id_middleware(request: Request, call_next):
    incoming = request.headers.get("x-correlation-id") or request.headers.get(
        "x-request-id"
    )
    correlation_id = (
        incoming.strip() if incoming and incoming.strip() else uuid.uuid4().hex
    )
    token = correlation_id_var.set(correlation_id)
    start = time.time()
    logger = get_logger("nexus.http")
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.time() - start) * 1000)
        increment_metric("http_requests_total")
        increment_metric("http_requests_failed")
        log_event(
            logger,
            logging.ERROR,
            "request_failed",
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
        )
        raise
    finally:
        correlation_id_var.reset(token)

    duration_ms = round((time.time() - start) * 1000)
    increment_metric("http_requests_total")
    if response.status_code >= 500:
        increment_metric("http_requests_failed")
    response.headers["x-correlation-id"] = correlation_id
    log_event(
        logger,
        logging.INFO,
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        correlation_id=correlation_id,
    )
    return response
