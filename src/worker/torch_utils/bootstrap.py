# src/worker/torch_utils/bootstrap.py

import logging

from worker.config import (
    TORCH_DEVICE,
    TORCH_MATMUL_PRECISION,
    TORCH_NUM_INTEROP_THREADS,
    TORCH_NUM_THREADS,
)

_DEVICE: str | None = None


def get_device() -> str:
    # Default if configure_torch hasn't run yet.
    return _DEVICE or "cpu"


logger = logging.getLogger(__name__)


def configure_torch() -> None:
    """
    One-time per-worker torch configuration.
    Keep this safe: no hard dependency if torch is not installed.
    """
    global _DEVICE
    try:
        import torch
    except Exception as exc:
        _DEVICE = "cpu"
        logger.info("torch not available; skipping torch bootstrap (%s)", exc)
        return

    requested = TORCH_DEVICE.strip()
    if requested:
        _DEVICE = requested
    else:
        _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    # Thread controls (align with Celery concurrency to avoid oversubscription).
    if TORCH_NUM_THREADS is not None:
        torch.set_num_threads(TORCH_NUM_THREADS)

    if TORCH_NUM_INTEROP_THREADS is not None:
        torch.set_num_interop_threads(TORCH_NUM_INTEROP_THREADS)

    # Optional: matmul precision (PyTorch 2+). Safe-guard in older versions.
    if TORCH_MATMUL_PRECISION:
        try:
            torch.set_float32_matmul_precision(TORCH_MATMUL_PRECISION)
        except Exception:
            logger.info("torch.set_float32_matmul_precision not supported")

    logger.info(
        "torch bootstrap complete (device=%s threads=%s interop=%s)",
        _DEVICE,
        TORCH_NUM_THREADS,
        TORCH_NUM_INTEROP_THREADS,
    )
