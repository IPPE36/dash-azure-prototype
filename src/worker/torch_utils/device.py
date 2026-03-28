from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def resolve_device(preferred: str | None = None):
    """
    Resolve a torch device string to an actual device, with safe CUDA fallback.
    """
    try:
        import torch
    except Exception as exc:
        logger.info("torch not available; defaulting to cpu (%s)", exc)
        return "cpu"

    device = (preferred or "cpu").strip().lower()
    if device.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("CUDA requested but not available; falling back to cpu")
        return torch.device("cpu")
    return torch.device(device)
