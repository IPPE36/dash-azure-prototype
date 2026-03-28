from __future__ import annotations

from pathlib import Path
from typing import Any


def save_checkpoint(
    checkpoint_dir: str | Path,
    *,
    model,
    likelihood=None,
    optimizer=None,
    scheduler=None,
    extra: dict[str, Any] | None = None,
) -> Path:
    try:
        import torch
    except Exception as exc:
        raise RuntimeError(f"torch not available; cannot save checkpoint ({exc})") from exc

    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / "checkpoint.pt"

    payload: dict[str, Any] = {
        "model_state": model.state_dict(),
        "extra": extra or {},
    }
    if likelihood is not None:
        payload["likelihood_state"] = likelihood.state_dict()
    if optimizer is not None:
        payload["optimizer_state"] = optimizer.state_dict()
    if scheduler is not None:
        payload["scheduler_state"] = scheduler.state_dict()

    torch.save(payload, path)
    return path


def load_checkpoint(
    checkpoint_dir: str | Path,
    *,
    model,
    likelihood=None,
    optimizer=None,
    scheduler=None,
    map_location: str | None = None,
) -> dict[str, Any] | None:
    try:
        import torch
    except Exception as exc:
        raise RuntimeError(f"torch not available; cannot load checkpoint ({exc})") from exc

    checkpoint_dir = Path(checkpoint_dir)
    path = checkpoint_dir / "checkpoint.pt"
    if not path.exists():
        return None

    payload = torch.load(path, map_location=map_location)
    model.load_state_dict(payload["model_state"])

    if likelihood is not None and "likelihood_state" in payload:
        likelihood.load_state_dict(payload["likelihood_state"])
    if optimizer is not None and "optimizer_state" in payload:
        optimizer.load_state_dict(payload["optimizer_state"])
    if scheduler is not None and "scheduler_state" in payload:
        scheduler.load_state_dict(payload["scheduler_state"])

    return payload
