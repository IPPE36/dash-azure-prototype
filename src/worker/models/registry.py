from typing import Type
import torch.nn as nn

from .specs import ModelConfig, PreprocessConfig, AuxilaryData


MODEL_REGISTRY: dict[str, Type[nn.Module]] = {}


def register_model(name: str):
    """Decorator-based registry for model classes."""
    def decorator(cls: Type[nn.Module]) -> Type[nn.Module]:
        if name in MODEL_REGISTRY:
            raise ValueError(f"Model type '{name}' is already registered.")
        MODEL_REGISTRY[name] = cls
        cls.model_type = name
        return cls
    return decorator


def get_model_class(name: str) -> Type[nn.Module]:
    try:
        return MODEL_REGISTRY[name]
    except KeyError as e:
        available = ", ".join(sorted(MODEL_REGISTRY))
        raise KeyError(
            f"Unknown model type '{name}'. Available model types: {available or 'none'}"
        ) from e


def create_model(spec: ModelConfig, prep: PreprocessConfig = None, aux_data: AuxilaryData = None):
    """Construct a model instance from its config and artifacts."""
    cls = get_model_class(spec.model_type)
    return cls(spec=spec, prep=prep, aux_data=aux_data)
