# src/worker/torch_utils/bootstrap.py

import logging

from worker.config import (
    TORCH_DEVICE,
    TORCH_MATMUL_PRECISION,
    TORCH_NUM_INTEROP_THREADS,
    TORCH_NUM_THREADS,
)


logger = logging.getLogger(__name__)


def configure_torch() -> None:
    """
    One-time per-worker torch configuration.
    Keep this safe: no hard dependency if torch is not installed.
    """
    try:
        import torch
    except Exception as exc:
        logger.info("torch not available; skipping torch bootstrap (%s)", exc)
        return

    device = TORCH_DEVICE.strip()
    if device.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("TORCH_DEVICE=%s but CUDA not available; falling back to cpu", device)
        device = "cpu"

    # Thread controls (align with Celery concurrency to avoid oversubscription).
    if TORCH_NUM_THREADS is not None:
        torch.set_num_threads(TORCH_NUM_THREADS)

    if TORCH_NUM_INTEROP_THREADS is not None:
        torch.set_num_interop_threads(TORCH_NUM_INTEROP_THREADS)

    # Optional: matmul precision (PyTorch 2+). Safe-guard in older versions.
    if TORCH_MATMUL_PRECISION:
        precision = TORCH_MATMUL_PRECISION.strip().lower()
        allowed = {"highest", "high", "medium"}
        if precision not in allowed:
            logger.warning(
                "invalid TORCH_MATMUL_PRECISION=%r; expected one of %s",
                TORCH_MATMUL_PRECISION,
                ", ".join(sorted(allowed)),
            )
        else:
            try:
                torch.set_float32_matmul_precision(precision)
            except Exception:
                logger.info("torch.set_float32_matmul_precision not supported")

    logger.info(
        "torch bootstrap complete (device=%s threads=%s interop=%s)",
        device,
        TORCH_NUM_THREADS,
        TORCH_NUM_INTEROP_THREADS,
    )
