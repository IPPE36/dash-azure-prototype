# src/worker/runtime.py

from pathlib import Path
from threading import Lock

_RUNTIME = None
_LOCK = Lock()


class WorkerRuntime:
    def __init__(self):
        self.model_repo = self._load_model_repo()

    def _load_model_repo(self):
        """Serves and eagerly loads all requested models from the image"""
        from worker.config import MODEL_REPOSITORY_ROOT_PATH
        from worker.torch_utils import get_default_device
        from worker.models import ModelRepository

        requested = {"demo_gpr", "demo_gpc", "demo_lin", "demo_mlp"}
        
        model_repo = ModelRepository(
            root=Path(MODEL_REPOSITORY_ROOT_PATH),
            served_artifacts=requested,
            device=get_default_device(),
        )
        model_repo.load_all()  # load eagerly
        return model_repo

    def predict(self, x, targets: set[str] | list[str]):
        # artifacts = self.model_repo.find_by_targets(targets)
        return f"processed click #{x}"


def configure_runtime() -> WorkerRuntime:
    """One-time per-worker model runtime configuration.
    This function is called in shared.celery_app.py"""
    global _RUNTIME
    if _RUNTIME is None:
        with _LOCK:
            if _RUNTIME is None:
                _RUNTIME = WorkerRuntime()
    return _RUNTIME