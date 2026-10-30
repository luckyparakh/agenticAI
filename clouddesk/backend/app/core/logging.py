"""Structured JSON logging.

Every line carries `request_id` and `workflow_id` (CLAUDE.md §16), so a single
HTTP request or a single workflow run can be followed across the API, the graph
and the tools without threading an argument through every call.

Both ids live in `ContextVar`s. That is what makes them work under asyncio: each
task inherits the context it was created in, so a background workflow keeps the
`workflow_id` set when it started without the logging call sites knowing anything
about it.

Usage:

    setup_logging()                       # once, at startup
    bind_request_id("abc123")             # middleware, per request
    with workflow_context(workflow_id):   # workflow service, per run
        ...

Nothing here raises on a bad record. Logging is telemetry, and telemetry must not
break the thing it observes.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

# Correlation ids. Default to None so a log line from outside any request is still valid.
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_workflow_id: ContextVar[str | None] = ContextVar("workflow_id", default=None)

# Attributes the stdlib puts on every LogRecord. Anything else came from
# `logger.info(..., extra={...})` and is worth emitting.
_STANDARD_RECORD_FIELDS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)

_CONFIGURED_FLAG = "_clouddesk_json_logging"


# --- Correlation ids --------------------------------------------------------


def bind_request_id(request_id: str | None = None) -> str:
    """Set the request id for this context, generating one when absent (N3)."""
    value = request_id or str(uuid.uuid4())
    _request_id.set(value)
    return value


def get_request_id() -> str | None:
    return _request_id.get()


def bind_workflow_id(workflow_id: str | None) -> None:
    _workflow_id.set(workflow_id)


def get_workflow_id() -> str | None:
    return _workflow_id.get()


@contextmanager
def workflow_context(workflow_id: str) -> Iterator[None]:
    """Tag every log line inside the block with `workflow_id`, then restore."""
    token = _workflow_id.set(workflow_id)
    try:
        yield
    finally:
        _workflow_id.reset(token)


def clear_context() -> None:
    """Drop both ids. Mainly for tests and for pooled workers between jobs."""
    _request_id.set(None)
    _workflow_id.set(None)


# --- Formatter ---------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as one JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
            "workflow_id": _workflow_id.get(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        # Anything passed via `extra=` lands on the record as a custom attribute.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                payload.setdefault(key, value)

        # default=str keeps an unserialisable extra from killing the log line.
        return json.dumps(payload, default=str, ensure_ascii=False)


# --- Setup -------------------------------------------------------------------


def setup_logging(level: str | int | None = None) -> None:
    """Install the JSON formatter on the root logger.

    Idempotent: calling it twice does not double every line, which matters
    because the test suite and the app lifespan both call it.
    """
    if level is None:
        # Imported here so importing this module never pulls in settings parsing.
        from app.core.config import get_settings

        level = get_settings().log_level

    root = logging.getLogger()

    existing = next(
        (h for h in root.handlers if getattr(h, _CONFIGURED_FLAG, False)),
        None,
    )
    if existing is not None:
        root.setLevel(level)
        return

    # Replace anything a library installed, so output stays parseable.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    setattr(handler, _CONFIGURED_FLAG, True)

    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn ships its own handlers; strip them so its lines are JSON too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Module-level logger. Use `get_logger(__name__)`."""
    return logging.getLogger(name)
