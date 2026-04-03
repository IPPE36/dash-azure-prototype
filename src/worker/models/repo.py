import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections import defaultdict

import numpy as np
import torch

from .io_utils import ArtifactIO
from .specs import ModelConfig


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelRecord:
    """Metadata for one saved model artifact."""
    name: str
    path: Path
    spec: ModelConfig

    @property
    def model_type(self) -> str:
        return self.spec.model_type

    @property
    def features(self) -> list[str]:
        return self.spec.features

    @property
    def targets(self) -> list[str]:
        return self.spec.targets


class ModelRepository:
    """Discovers saved model artifacts under a root directory and loads them on demand."""

    def __init__(
        self,
        root: str | Path,
        served_artifacts: set[str] | list[str],
        *,
        device: str | torch.device = "cpu",
    ) -> None:
        self.root = Path(root)
        self.device = device
        self.served_artifacts = set(served_artifacts)

        if not self.served_artifacts:
            raise ValueError("served_artifacts must contain at least one artifact name")

        self._loaded: dict[str, Any] = {}
        self._targets_lookup: dict[str, list[str]] = self._build_targets_lookup()
        self.bounds: dict[str, tuple[float, float]] = {}

        for a in sorted(served_artifacts):
            logger.info("Served artifact %s | device=%s", a, self.device)

    def _iter_artifact_dirs(self):
        if not self.root.exists():
            logger.warning("Artifact root does not exist: %s", self.root)
            return

        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue

            if path.name not in self.served_artifacts:
                logger.debug("Skipping unserved artifact: %s", path.name)
                continue

            if not (path / ArtifactIO.CONFIG_FILENAME).exists():
                logger.debug("Skipping %s (missing config)", path.name)
                continue

            logger.debug("Discovered artifact: %s", path.name)
            yield path

    def _read_spec(self, artifact_dir: Path) -> ModelConfig:
        config_path = artifact_dir / ArtifactIO.CONFIG_FILENAME
        logger.debug("Reading spec from %s", config_path)

        with open(config_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        return ModelConfig(**payload)

    def list_available(self) -> list[str]:
        names = [path.name for path in self._iter_artifact_dirs()]
        logger.debug("Available artifacts: %s", names)
        return names

    def list_records(self) -> list[ModelRecord]:
        records: list[ModelRecord] = []

        for path in self._iter_artifact_dirs():
            try:
                spec = self._read_spec(path)
                records.append(ModelRecord(name=path.name, path=path, spec=spec))
            except Exception:
                logger.exception("Failed to read spec for %s", path)

        logger.debug("Built %d model records", len(records))
        return records

    def list_active(self) -> list[str]:
        active = list(self._loaded.keys())
        logger.debug("Active models: %s", active)
        return active

    def is_active(self, name: str) -> bool:
        return name in self._loaded

    def get(self, name: str):
        """Return a loaded model instance, loading and caching it on first access."""
        if name not in self.served_artifacts:
            logger.error("Attempt to access unserved artifact: %s", name)
            allowed = ", ".join(sorted(self.served_artifacts)) or "none"
            raise KeyError(
                f"Model artifact '{name}' is not configured to be served. "
                f"Served artifacts: {allowed}"
            )

        if name in self._loaded:
            logger.debug("Cache hit for model: %s", name)
            return self._loaded[name]

        artifact_dir = self.root / name

        if not artifact_dir.exists() or not (artifact_dir / ArtifactIO.CONFIG_FILENAME).exists():
            logger.error("Artifact not found or invalid: %s", name)
            available = ", ".join(self.list_available()) or "none"
            raise KeyError(
                f"Unknown or unloadable model artifact '{name}'. "
                f"Available served artifacts: {available}"
            )

        logger.info("Loading model artifact: %s", name)

        try:
            model = ArtifactIO.load(artifact_dir, device=self.device)
        except Exception:
            logger.exception("Failed to load model: %s", name)
            raise

        self._loaded[name] = model
        self._update_bounds_from_model(model)
        logger.info("Model loaded and cached: %s", name)

        return model

    def load_all(self) -> dict[str, Any]:
        logger.info("Eagerly loading all served artifacts")

        for name in self.list_available():
            self.get(name)

        logger.info("Loaded %d models", len(self._loaded))
        return dict(self._loaded)

    def unload(self, name: str) -> None:
        if name in self._loaded:
            logger.info("Unloading model: %s", name)
        else:
            logger.debug("Unload called for non-loaded model: %s", name)

        self._loaded.pop(name, None)

    def unload_all(self) -> None:
        logger.info("Unloading all models (%d total)", len(self._loaded))
        self._loaded.clear()

    def describe(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        active = set(self.list_active())

        for record in self.list_records():
            rows.append(
                {
                    "name": record.name,
                    "model_type": record.model_type,
                    "n_features": len(record.features),
                    "n_targets": len(record.targets),
                    "active": record.name in active,
                    "path": str(record.path),
                }
            )

        logger.debug("Generated description for %d models", len(rows))
        return rows
    
    def _as_numpy(self, value: Any) -> np.ndarray | None:
        if value is None:
            return None
        if torch.is_tensor(value):
            return value.detach().cpu().numpy()
        return np.asarray(value)

    def _inverse_scale_x(self, x: np.ndarray | None, prep) -> np.ndarray | None:
        if x is None:
            return None
        scaler = getattr(prep, "scaler_x", None) if prep is not None else None
        if scaler is None:
            return x
        try:
            return scaler.inverse_transform(x)
        except Exception:
            logger.exception("Failed to inverse-transform train_x for bounds.")
            return x

    def _inverse_scale_y(self, y: np.ndarray | None, prep) -> np.ndarray | None:
        if y is None:
            return None
        scaler = getattr(prep, "scaler_y", None) if prep is not None else None
        if scaler is None:
            return y
        try:
            if y.ndim == 1:
                y = y.reshape(-1, 1)
            return scaler.inverse_transform(y)
        except Exception:
            logger.exception("Failed to inverse-transform train_y for bounds.")
            return y

    def _compute_bounds(
        self,
        names: list[str],
        data: np.ndarray | None,
    ) -> dict[str, tuple[float, float]]:
        if data is None:
            return {}
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        bounds: dict[str, tuple[float, float]] = {}
        n_cols = data.shape[1]

        for idx, name in enumerate(names[:n_cols]):
            col = data[:, idx]
            if np.all(np.isnan(col)):
                continue
            bounds[name] = (float(np.nanmin(col)), float(np.nanmax(col)))

        return bounds

    def _merge_repo_bounds(self, bounds: dict[str, tuple[float, float]]) -> None:
        for key, (low, high) in bounds.items():
            if key in self.bounds:
                cur_low, cur_high = self.bounds[key]
                self.bounds[key] = (min(cur_low, low), max(cur_high, high))
            else:
                self.bounds[key] = (low, high)

    def _update_bounds_from_model(self, model: Any) -> None:
        aux = getattr(model, "aux", None)
        prep = getattr(model, "prep", None)
        spec = getattr(model, "spec", None)
        if spec is None:
            return

        train_x = getattr(aux, "train_x", None) if aux is not None else None
        train_y = getattr(aux, "train_y", None) if aux is not None else None
        if train_x is None:
            train_x = getattr(model, "train_x", None)
        if train_y is None:
            train_y = getattr(model, "train_y", None)

        if train_x is None and train_y is None:
            return

        x_np = self._as_numpy(train_x)
        y_np = self._as_numpy(train_y)

        x_np = self._inverse_scale_x(x_np, prep)
        y_np = self._inverse_scale_y(y_np, prep)

        if y_np is not None and y_np.ndim == 1:
            y_np = y_np.reshape(-1, 1)

        bounds = {}
        bounds.update(self._compute_bounds(spec.features, x_np))
        bounds.update(self._compute_bounds(spec.targets, y_np))

        if bounds:
            self._merge_repo_bounds(bounds)
            if aux is not None:
                aux.bounds = bounds

    def _build_targets_lookup(self) -> dict[str, list[str]]:
        lookup: dict[str, list[str]] = defaultdict(list)

        for record in self.list_records():
            for target in record.targets:
                lookup[target].append(record.name)

        return dict(lookup)
    
    def find_by_targets(self, targets: set[str] | list[str]) -> list[str]:
        matches: list[str] = []
        seen: set[str] = set()
        for target in targets:
            for name in self._targets_lookup.get(target, []):
                if name not in seen:
                    seen.add(name)
                    matches.append(name)
        return matches
