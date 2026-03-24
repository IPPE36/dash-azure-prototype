# src/worker/runtime.py

from threading import Lock
import logging

logger = logging.getLogger(__name__)

_RUNTIME = None
_LOCK = Lock()


class ModelRuntime:
    def __init__(self):
        logger.info("initializing model runtime")
        self.model = self._load_model()
        logger.info("model runtime initialized")

    def _load_model(self):
        # Replace with real model load, e.g. torch/transformers pipeline.
        # For torch, use device decided in bootstrap.
        try:
            from worker.config import TORCH_DEVICE, MODEL_PATH
            logger.info("loading model on device=%s path=%s", TORCH_DEVICE, MODEL_PATH)
        except Exception:
            pass
        return "model-loaded"

    def predict(self, x: int) -> str:
        return f"processed click #{x} ({self.model})"


def get_runtime() -> ModelRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        with _LOCK:
            if _RUNTIME is None:
                logger.info("creating singleton runtime instance")
                _RUNTIME = ModelRuntime()
    return _RUNTIME


def configure_runtime() -> None:
    logger.info("warm_up called")
    get_runtime()
