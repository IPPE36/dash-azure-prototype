# src/shared/logs.py

import json
import logging
import sys
from datetime import datetime, timezone
import threading

from shared.config import LOG_FORMAT, LOG_LEVEL

_CONFIGURED = False
_LOCK = threading.Lock()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("trace_id", "request_id", "task_id", "task_name"):
            value = getattr(record, key, None)
            if value:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def init_logs() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    with _LOCK:
        level = getattr(logging, LOG_LEVEL, logging.INFO)

        root = logging.getLogger()
        root.setLevel(level)

        handler = logging.StreamHandler(stream=sys.stdout)
        if LOG_FORMAT == "console":
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            ))
        elif LOG_FORMAT == "json":
            handler.setFormatter(JsonFormatter())
        else:
            raise ValueError("LOG_FORMAT needs to be either 'console' or 'json'")

        root.handlers.clear()
        root.addHandler(handler)
        _CONFIGURED = True
