"""Structured JSON logging (Cloud Logging compatible) with per-request context.

Log-based metrics key off the "event" field; see docs/operations.md.
Never pass passcodes, tokens or full destination URLs to the logger.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_service = "safelinks"

_SEVERITY = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": _SEVERITY.get(record.levelname, "DEFAULT"),
            "service": _service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            entry["request_id"] = rid
        fields = getattr(record, "fields", None)
        if fields:
            entry.update(fields)
        if record.exc_info:
            # Stack traces go to logs only, never to clients.
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(service: str, level: str = "INFO") -> None:
    global _service
    _service = service
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Our middleware writes one access log per request; uvicorn's would duplicate it and
    # include raw query strings.
    logging.getLogger("uvicorn.access").disabled = True


def event(name: str, level: int = logging.INFO, **fields: object) -> None:
    """Emit a metric-bearing structured event."""
    logging.getLogger("safelinks.events").log(
        level, name, extra={"fields": {"event": name, **fields}}
    )
