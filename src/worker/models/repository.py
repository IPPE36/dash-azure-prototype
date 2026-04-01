import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

        logger.info(
            "Initialized ModelRepository | root=%s | served=%s | device=%s",
            self.root,
            sorted(self.served_artifacts),
            self.device,
        )

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