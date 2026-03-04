# src/shared/logs.py

import json
import logging
import os
import sys
from datetime import datetime, timezone
import threading


_CONFIGURED = False
_CONFIG_LOCK = threading.Lock()
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_FORMAT = os.getenv("LOG_FORMAT", "console").lower()


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
    with _CONFIG_LOCK:
        level = getattr(logging, _LOG_LEVEL, logging.INFO)

        root = logging.getLogger()
        root.setLevel(level)

        handler = logging.StreamHandler(stream=sys.stdout)
        if _LOG_FORMAT == "console":
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            ))
        elif _LOG_FORMAT == "json":
            handler.setFormatter(JsonFormatter())
        else:
            raise ValueError("LOG_FORMAT needs to be either 'console' or 'json'")

        root.handlers.clear()
        root.addHandler(handler)
        _CONFIGURED = True