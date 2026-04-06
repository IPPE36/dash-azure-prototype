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

    def get_bounds(self, targets: set[str] | list[str]) -> list[tuple[float, float]]:
        bounds_list: list[tuple[float, float]] = []
        for key in targets:
            bounds = self.model_repo.bounds.get(key)
            if bounds is None:
                bounds = (0.0, 1.0)
            bounds_list.append((float(bounds[0]), float(bounds[1])))
        return bounds_list

    def optimize(
        self,
        *,
        objectives: dict[str, float],
        strategies: dict[str, str] | None = None,
        bounds: dict[str, tuple[float, float]] | None = None,
        fixed: dict[str, float] | None = None,
        fit_features: list[str] | None = None,
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
        )
        return self.optimization

    def optimize_step(self):
        if self.optimization is None:
            raise RuntimeError("No active optimization. Call optimize() first.")
        self.optimization.step_once()
        return self.optimization.get_results()

    def optimize_run(self, steps: int | None = None):
        if self.optimization is None:
            raise RuntimeError("No active optimization. Call optimize() first.")
        if steps is None:
            return self.optimization.run()
        return self.optimization.run_steps(steps)

    def optimize_results(self):
        if self.optimization is None:
            return []
        return self.optimization.get_results()


def configure_runtime() -> WorkerRuntime:
    """One-time per-worker model runtime configuration.
    This function is called in shared.celery_app.py"""
    global _RUNTIME
    if _RUNTIME is None:
        with _LOCK:
            if _RUNTIME is None:
                _RUNTIME = WorkerRuntime()
    return _RUNTIME
