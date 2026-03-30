from typing import Callable

from .base import BaseTrainer


TRAINER_REGISTRY: dict[str, type["BaseTrainer"]] = {}


def register_trainer(name: str) -> Callable[[type["BaseTrainer"]], type["BaseTrainer"]]:
    """Decorator-based registry for trainer classes."""
    def decorator(cls: type[BaseTrainer]) -> type[BaseTrainer]:
        if name in TRAINER_REGISTRY:
            raise ValueError(f"Trainer for '{name}' already registered")
        TRAINER_REGISTRY[name] = cls
        return cls
    return decorator


def get_trainer(name: str) -> type["BaseTrainer"]:
    try:
        return TRAINER_REGISTRY[name]
    except KeyError as e:
        available = ", ".join(sorted(TRAINER_REGISTRY))
        raise KeyError(
            f"Unknown trainer for '{name}'. Available: {available or 'none'}"
        ) from e


def create_trainer(name: str, model, **kwargs) -> "BaseTrainer":
    """Construct a model training procedure."""
    cls = get_trainer(name)
    return cls(model, **kwargs)