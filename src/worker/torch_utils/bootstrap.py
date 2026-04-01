# src/worker/torch_utils/bootstrap.py

import logging

from worker.config import (
    TORCH_MATMUL_PRECISION,
    TORCH_NUM_INTEROP_THREADS,
    TORCH_NUM_THREADS,
)


logger = logging.getLogger(__name__)


def configure_torch() -> None:
    """One-time per-worker torch configuration.
    This function is called in shared.celery_app.py"""


    try:
        # Keep this safe: no hard dependency if torch is not installed
        import torch

        """Prefer CUDA when available, otherwise fall back to CPU"""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"torch.default_device={device}")

    except Exception as exc:
        logger.info("torch not available; skipping torch bootstrap (%s)", exc)
        return None

    
    if TORCH_NUM_THREADS is not None:
        try:
            # align with Celery concurrency to avoid oversubscription...
            torch.set_num_threads(TORCH_NUM_THREADS)
            logger.info(f"torch.set_num_threads={TORCH_NUM_THREADS}")
        except Exception:
            logger.info("torch.set_num_threads not supported")

    if TORCH_NUM_INTEROP_THREADS is not None:
        try:
            torch.set_num_interop_threads(TORCH_NUM_INTEROP_THREADS)
            logger.info(f"torch.set_num_interop_threads={TORCH_NUM_INTEROP_THREADS}")
        except Exception:
            logger.info("torch.set_num_interop_threads not supported")

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
                logger.info(f"torch.set_float32_matmul_precision={precision}")
            except Exception:
                logger.info("torch.set_float32_matmul_precision not supported")

    return None
