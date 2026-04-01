# src/worker/runtime.py

from threading import Lock
import logging

from worker.config import (
    TORCH_DEVICE,
    MODEL_PATH,
)


logger = logging.getLogger(__name__)

_RUNTIME = None
_LOCK = Lock()


class WorkerRuntime:
    def __init__(self):
        logger.info("initializing runtime...")
        self.model = self._load_model()
        logger.info("...runtime initialized")

    def _load_model(self):
        # Replace with real model load, e.g. torch/transformers pipeline.
        try:
            logger.info("loading model on device=%s path=%s", TORCH_DEVICE, MODEL_PATH)
        except Exception:
            pass
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