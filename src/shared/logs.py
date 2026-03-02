import json
import logging
import os
import sys
import time
from functools import wraps
from datetime import datetime, timezone


_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.getenv("LOG_SERVICE", "local"),
            "env": os.getenv("APP_ENV", "local"),
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

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stdout)
    if fmt == "console":
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
        )
    else:
        handler.setFormatter(JsonFormatter())

    root.handlers.clear()
    root.addHandler(handler)
    _CONFIGURED = True


def log_execution(
    logger_name: str | None = None,
    level: int = logging.INFO,
    include_args: bool = False,
):
    """
    Decorator that logs function start/end/failure and runtime in milliseconds.
    Example:
        @log_execution()
        def my_func(...):
            ...
    """
    def decorator(func):
        log = logging.getLogger(logger_name or func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            extra = {"function": func.__name__}
            if include_args:
                extra["args"] = repr(args)
                extra["kwargs"] = repr(kwargs)

            log.log(level, "function started", extra=extra)
            try:
                result = func(*args, **kwargs)
            except Exception:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                error_extra = dict(extra)
                error_extra["runtime_ms"] = round(elapsed_ms, 2)
                log.exception("function failed", extra=error_extra)
                raise

            elapsed_ms = (time.perf_counter() - start) * 1000.0
            done_extra = dict(extra)
            done_extra["runtime_ms"] = round(elapsed_ms, 2)
            log.log(level, "function completed", extra=done_extra)
            return result

        return wrapper

    return decorator
