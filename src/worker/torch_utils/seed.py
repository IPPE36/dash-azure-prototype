from __future__ import annotations

import logging
import random

import numpy as np


logger = logging.getLogger(__name__)


def seed_all(seed: int, *, deterministic: bool = False) -> None:
    """
    Seed python, numpy, and torch RNGs for reproducibility.
    """
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except Exception as exc:
        logger.info("torch not available; skipped torch seeding (%s)", exc)
        return

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    if deterministic:
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
