# src/worker/runtime.py

from pathlib import Path
from threading import Lock
import logging

logger = logging.getLogger(__name__)

_RUNTIME = None
_LOCK = Lock()


class WorkerRuntime:
    def __init__(self):
        logger.info("initializing runtime...")
        self.model = self._load_models()
        logger.info("...runtime initialized")

    def _load_models(self):
        from worker.config import MODEL_REPOSITORY_ROOT_PATH
        from worker.torch_utils import get_default_device
        from worker.models import ModelRepository

        ModelRepository(
            root=Path(MODEL_REPOSITORY_ROOT_PATH),
            served_artifacts={"demo_gpr"},
            device=get_default_device(),
        )

        return "model-loaded"

    def predict(self, x: int) -> str:
        return f"processed click #{x} ({self.model})"


def configure_runtime() -> WorkerRuntime:
    """One-time per-worker model runtime configuration.
    This function is called in shared.celery_app.py"""
    global _RUNTIME
    if _RUNTIME is None:
        with _LOCK:
            if _RUNTIME is None:
                _RUNTIME = WorkerRuntime()
    return _RUNTIME