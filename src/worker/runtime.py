# src/worker/runtime.py

from pathlib import Path
from threading import Lock

_RUNTIME = None
_LOCK = Lock()


class WorkerRuntime:
    def __init__(self):
        self.model_repo = self._load_model_repo()
        self.optimization = None

    def _load_model_repo(self):
        """Serves and eagerly loads all requested models from the image"""
        from worker.config import MODEL_REPOSITORY_ROOT_PATH
        from worker.torch_utils import get_default_device
        from worker.models import ModelRepository

        requested = {"demo_lin"}
        
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

    def optimize(
        self,
        *,
        objectives: dict[str, float],
        strategies: dict[str, str] | None = None,
        bounds: dict[str, tuple[float, float]] | None = None,
        fixed: dict[str, float] | None = None,
        fit_features: list[str] | None = None,
        runs: int = 200,
        population: int = 50,
        seed: int = 1,
        crossover: str = "SBX",
        device: str = "cpu",
    ):
        """Initialize and store a model inversion optimization."""
        from worker.opt import ModelInversionAlgorithm

        self.optimization = ModelInversionAlgorithm(
            repo=self.model_repo,
            objectives=objectives,
            strategies=strategies,
            bounds=bounds,
            fixed=fixed,
            fit_features=fit_features,
            runs=runs,
            population=population,
            seed=seed,
            crossover=crossover,
            device=device,
        )
        return self.optimization


def configure_runtime() -> WorkerRuntime:
    """One-time per-worker model runtime configuration.
    This function is called in shared.celery_app.py"""
    global _RUNTIME
    if _RUNTIME is None:
        with _LOCK:
            if _RUNTIME is None:
                _RUNTIME = WorkerRuntime()
    return _RUNTIME
