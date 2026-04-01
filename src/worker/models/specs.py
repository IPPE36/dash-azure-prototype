from dataclasses import dataclass, field
from typing import Any

import torch


@dataclass
class ModelConfig:
    """Metadata needed to rebuild a model instance."""
    model_type: str
    features: list[str]
    targets: list[str]
    requires_aux: bool
    model_kwargs: dict[str, Any] = field(default_factory=dict)

    @property
    def input_dim(self) -> int:
        return len(self.features)

    @property
    def output_dim(self) -> int:
        return len(self.targets)


@dataclass
class PreprocessConfig:
    """Container for preprocessors used before/after inference.
    Store sklearn-compatible transformers or similar objects.
    Anything placed here should be joblib-serializable.
    """
    scaler_x: Any = None
    scaler_y: Any = None
    poly_x: Any = None
    pca_x: Any = None
    scaler_y_list: list[Any] = None


@dataclass
class AuxilaryData:
    """Optional extra data tied to a model instance."""
    train_x: torch.Tensor = None
    train_y: torch.Tensor = None
    extra: dict[str, Any] = None
