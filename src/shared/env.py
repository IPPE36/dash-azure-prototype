# src/shared/env.py

import logging
import os

logger = logging.getLogger(__name__)


def env_str(name: str, default: str = "") -> str:
    # Allow inline comment style values in .env (e.g., "dev  # note").
    return os.getenv(name, default).split("#", 1)[0].strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name, str(default)).lower()
    return raw in {"1", "true", "t", "yes", "y", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = env_str(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_int_env(name: str, *, default: int = None, amin: int = None, amax: int = None) -> int:
    raw = env_str(name, "")
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("invalid %s=%r; expected int", name, raw)
        return default
    if amin is not None and value < amin:
        logger.warning("invalid %s=%r; expected >= %s", name, raw, amin)
        return default
    if amax is not None and value > amax:
        logger.warning("invalid %s=%r; expected <= %s", name, raw, amax)
        return default
    return value
