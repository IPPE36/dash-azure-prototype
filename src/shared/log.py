# src/shared/logs.py
# Design note: logging is configured once per process with a lightweight JSON option.
# Helpers here keep timing/error logs consistent and avoid noisy ad-hoc patterns.

import json
import logging
import sys
from datetime import datetime, timezone
from functools import wraps
import threading
import time
from contextlib import contextmanager

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


def configure_logs() -> None:
    """
    One-time log configuration. This function is called in:
    - shared/db/bootstrapping.py
    - shared/celery_app.py
    - web/app.py
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    with _LOCK:
        if _CONFIGURED:
            return
        _init_log()
        _CONFIGURED = True


def _init_log() -> None:
    """make loggers propagate to root"""

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stdout)
    if LOG_FORMAT == "console":
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(processName)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        ))
    elif LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        raise ValueError("LOG_FORMAT needs to be either 'console' or 'json'")

    root.handlers[:] = [handler]
    for name in ("celery", "celery.app.trace", "kombu"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def log_timed(
    logger: logging.Logger | None = None,
    *,
    success_level: int = logging.INFO,
    failure_level: int = logging.ERROR,
    label: str | None = None,
    message: str | None = None,
):
    """
    Decorator to log success/failure and elapsed time for a function. Use as...
    @log_timed(label="do stuff")
    def do_work():
        your code...
    """
    log = logger or logging.getLogger(__name__)

    def decorator(func):
        name = label or message or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception:
                elapsed = (time.perf_counter() - start) * 1000.0
                log.log(failure_level, "failed %s (%.2f ms)", name, elapsed, exc_info=True)
                raise
            elapsed = (time.perf_counter() - start) * 1000.0
            log.log(success_level, "completed %s (%.2f ms)", name, elapsed)
            return result

        return wrapper

    return decorator


@contextmanager
def log_timed_block(
    label: str,
    logger: logging.Logger | None = None,
    *,
    success_level: int = logging.INFO,
    failure_level: int = logging.ERROR,
):
    """
    Context manager to log success/failure and elapsed time for a code block. Use as...
    with log_timed_block("do stuff"):
        your code...
    """
    log = logger or logging.getLogger(__name__)
    start = time.perf_counter()
    try:
        yield
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000.0
        log.log(failure_level, "failed %s (%.2f ms)", label, elapsed, exc_info=True)
        raise
    elapsed = (time.perf_counter() - start) * 1000.0
    log.log(success_level, "completed %s (%.2f ms)", label, elapsed)
