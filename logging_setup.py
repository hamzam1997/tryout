"""Logging configuration.

On Cloud Run, emit one JSON object per line. Cloud Logging lifts the fields
into jsonPayload, so entries are filterable:

    jsonPayload.event="note_taker.completed"
    jsonPayload.meeting_id=2

Locally, fall back to plain text since JSON is unreadable in a terminal.
"""

import json
import logging
import os
import sys

# Cloud Run sets K_SERVICE; its absence means we are on a developer machine.
ON_CLOUD_RUN = bool(os.environ.get("K_SERVICE"))

class CloudLoggingFormatter(logging.Formatter):
    """Render a record as the JSON shape Cloud Logging understands."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            entry.update(fields)

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Install a single stdout handler. Safe to call more than once."""
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        CloudLoggingFormatter()
        if ON_CLOUD_RUN
        else logging.Formatter("%(levelname)-8s %(name)s  %(message)s")
    )

    root.addHandler(handler)
    root.setLevel(level)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields):
    """Log a named event with structured fields attached.

    Locally the fields are appended to the message so they stay visible; on
    Cloud Run they become queryable jsonPayload entries.
    """
    payload = {"event": event, **fields}
    if ON_CLOUD_RUN:
        logger.log(level, event, extra={"fields": payload})
    else:
        readable = " ".join(f"{k}={v!r}" for k, v in fields.items())
        logger.log(level, "%s %s", event, readable)
