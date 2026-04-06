
import logging

import torch


logger = logging.getLogger(__name__)


def get_default_device() -> object:
    """Prefer CUDA when available, otherwise fall back to CPU"""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
