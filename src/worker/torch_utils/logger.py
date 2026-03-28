from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(name: str, log_dir: str | Path, level: int = logging.INFO) -> logging.Logger:
    """
    Create a logger that writes to console and a file under log_dir.
    Safe to call multiple times (won't duplicate handlers).
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = logging.FileHandler(log_dir / f"{name}.log")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
