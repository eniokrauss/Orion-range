"""
Structured logging setup for Orion Range.

Log format: one JSON object per line in production, human-readable in dev.
Every record automatically receives context fields injected by log_context
(job_id, org_id, blueprint_id, request_id, etc.) so log aggregators can
filter and correlate without string parsing.

Format selection:
  ORION_ENV=prod  →  JSON  (one object per line, structured)
  ORION_ENV=dev   →  text  (human-readable, coloured-friendly)
  LOG_FORMAT=json →  JSON  (override regardless of env)
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone

from app.core.config import settings


# ── context-injecting filter ──────────────────────────────────────────────────

class _ContextFilter(logging.Filter):
    """
    Injects all active log_context fields into every LogRecord as attributes.
    This lets formatters render them without the callers needing to pass extras.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        from app.core.log_context import get_log_context
        ctx = get_log_context()
        for key, value in ctx.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        # Ensure common fields are always present (avoids KeyError in formatters)
        for field in ("request_id", "job_id", "org_id", "blueprint_id", "step_key"):
            if not hasattr(record, field):
                setattr(record, field, None)
        return True


# ── JSON formatter ────────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """
    Emits each log record as a single JSON object.
    Useful for Loki / Elasticsearch / any structured log aggregator.
    """

    _CORE_FIELDS = frozenset({
        "name", "levelname", "message",
        "request_id", "job_id", "org_id", "blueprint_id", "step_key",
    })

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        record.message = record.getMessage()
        obj: dict = {
            "ts":       datetime.now(tz=timezone.utc).isoformat(),
            "level":    record.levelname,
            "logger":   record.name,
            "message":  record.message,
        }
        # Inject context fields if present and not None
        for field in ("request_id", "job_id", "org_id", "blueprint_id", "step_key"):
            val = getattr(record, field, None)
            if val is not None:
                obj[field] = val

        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            obj["exception"] = record.exc_text

        return json.dumps(obj, ensure_ascii=False)


# ── text formatter (dev) ──────────────────────────────────────────────────────

class _TextFormatter(logging.Formatter):
    """
    Human-readable formatter. Appends context fields in square brackets
    at the end of each line so they're visible but not noisy.

    Example:
        2025-01-15 12:34:56 INFO  job_runner - Step 'provision_vms' starting
            [job_id=abc123 org_id=default blueprint_id=bp-456]
    """

    _FMT = "%(asctime)s %(levelname)-5s %(name)s - %(message)s"

    def __init__(self) -> None:
        super().__init__(self._FMT, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        base = super().format(record)
        ctx_parts = []
        for field in ("request_id", "job_id", "org_id", "blueprint_id", "step_key"):
            val = getattr(record, field, None)
            if val is not None:
                ctx_parts.append(f"{field}={val}")
        if ctx_parts:
            return f"{base}  [{' '.join(ctx_parts)}]"
        return base


# ── public setup function ─────────────────────────────────────────────────────

def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    use_json = (
        getattr(settings, "log_format", "").lower() == "json"
        or settings.orion_env.lower() in ("prod", "production", "staging")
    )

    formatter: logging.Formatter = _JsonFormatter() if use_json else _TextFormatter()
    ctx_filter = _ContextFilter()

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any handlers added by a previous call (e.g. during test reloads)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(ctx_filter)
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").propagate = False
