from typing import Any
from abc import ABC, abstractmethod

import torch


class BaseTrainer(ABC):
    """Base class for a factory/registry approach."""
    def __init__(self, model, *, device: str | torch.device = "cpu") -> None:
        self.model = model
        self.device = torch.device(device)

    @abstractmethod
    def train(self, train_x, train_y, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

