from __future__ import annotations

import numpy as np
import torch


def as_float_tensor(value):
    """Convert input to a float32 torch.Tensor, preserving device when possible."""
    if isinstance(value, torch.Tensor):
        if value.dtype != torch.float32:
            return value.to(dtype=torch.float32)
        return value
    if isinstance(value, np.ndarray):
        if not value.flags.writeable:
            value = value.copy()
        return torch.as_tensor(value, dtype=torch.float32)
    return torch.as_tensor(value, dtype=torch.float32)
