from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
from platypus import NSGAII, Problem, Real, nondominated
from platypus.operators import PCX, SBX, PMX

from worker.models.repo import ModelRepository
from worker.opt.utils import cdist, pdist


logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    x: dict[str, float]
    objectives: dict[str, float]
    loss: float


class BatchProblem(Problem):
    def __init__(self, nvars, nobjs, batch_function, **kwargs):
        super().__init__(nvars, nobjs, **kwargs)
        self.batch_function = batch_function
        self.pending: list[Any] = []

    def evaluate(self, solution):
        self.pending.append(solution)

    def evaluate_all(self, solutions):
        self.pending.extend(s for s in solutions if not s.evaluated)
        result = self.batch_function(self.pending)
        if isinstance(result, tuple):
            losses, constraints = result
        else:
            losses = result
            constraints = [[] for _ in losses]
        for sol, loss, constr in zip(self.pending, losses, constraints):
            sol.objectives[:] = loss
            if sol.constraints is not None:
                sol.constraints[:] = constr
            sol.evaluated = True
        self.pending.clear()


class BatchNSGAII(NSGAII):
    def evaluate_all(self, solutions):
        """Bypass evaluator and use batch evaluation."""
        self.problem.evaluate_all(solutions)
        self.nfe += len(solutions)


class ModelInversionAlgorithm:
    """
    Optimize model inputs to match desired outputs.
    Parameters
    ----------
    repo:
        ModelRepository instance used to load models.
    objectives:
        Dict of target_name -> desired value.
    strategies:
        Optional dict of target_name -> strategy string.
        Supported:
        - "minimize difference" (default)
        - "greater than"
        - "smaller than"
        - "maximize uncertainty"
        - "minimize uncertainty"
        - "maximize distance"
        - "minimize distance"
    bounds:
        Optional dict feature_name -> (min, max). If omitted, repo.bounds is used.
    fixed:
        Optional dict of feature_name -> fixed value (not optimized).
    """

    def __init__(
        self,
        *,
        repo: ModelRepository,
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
    ) -> None:
        self.repo = repo
        self.objectives = objectives
        self.strategies = strategies or {}
        self.bounds = bounds or dict(repo.bounds)
        self.fixed = fixed or {}
        self.fit_features = fit_features
        self.runs = runs
        self.population = population
        self.generations = max(1, runs // population)
        self.device = device

        self._rng = np.random.default_rng(seed)

        self.objective_keys = list(self.objectives.keys())
        self.objective_vals = [self.objectives[k] for k in self.objective_keys]

        self._target_models = self._resolve_target_models()
        self.models = self._load_models(self._target_models.values())
        self.features = self._resolve_features()
        self.targets = list(self.objective_keys)

        self.fit_features = self._resolve_fit_features(self.fit_features)
        self._feature_index = {name: idx for idx, name in enumerate(self.features)}

        self._min_, self._max_ = self._resolve_feature_bounds(self.fit_features)
        self._default = self._resolve_default_values()

        self._target_bounds = self._resolve_target_bounds()
        self._needs_std = any(
            "uncertainty" in self.strategies.get(k, "").lower()
            for k in self.objective_keys
        )
        self._needs_distance = any(
            "distance" in self.strategies.get(k, "").lower()
            for k in self.objective_keys
        )
        self._train_x = self._resolve_train_x()
        self._max_distance = self._compute_max_distance()
        self._n_constraints = 0

        self.optimization = None
        self.step = 0
        self._results: list[OptimizationResult] = []

        self.variator = {
            "SBX": SBX(distribution_index=20),
            "PCX": PCX(),
            "PMX": PMX(),
        }.get(crossover, SBX(distribution_index=20))

    def _resolve_fit_features(self, fit_features: list[str] | None) -> list[str]:
        if fit_features is None:
            return list(self.features)
        unknown = [f for f in fit_features if f not in self.features]
        if unknown:
            raise ValueError(f"Unknown feature(s) in fit_features: {unknown}")
        return list(fit_features)

    def _resolve_target_models(self) -> dict[str, str]:
        target_models: dict[str, str] = {}
        for target in self.objective_keys:
            matches = self.repo.find_by_targets([target])
            if not matches:
                raise ValueError(f"No served model provides target '{target}'.")
            target_models[target] = matches[0]
        return target_models

    def _load_models(self, names: Iterable[str]) -> dict[str, Any]:
        models: dict[str, Any] = {}
        for name in names:
            if name not in models:
                models[name] = self.repo.get(name)
        return models

    def _resolve_features(self) -> list[str]:
        features: list[str] | None = None
        for model in self.models.values():
            model_features = list(model.spec.features)
            if features is None:
                features = model_features
            elif features != model_features:
                raise ValueError(
                    "All models used for inversion must share the same feature order."
                )
        return features or []

    def _resolve_feature_bounds(self, fit_features: list[str]) -> tuple[np.ndarray, np.ndarray]:
        min_vals = []
        max_vals = []
        for name in fit_features:
            if name in self.bounds:
                low, high = self.bounds[name]
            else:
                low, high = 0.0, 1.0
                logger.warning("Missing bounds for %s, defaulting to (0, 1).", name)
            if low > high:
                low, high = high, low
            min_vals.append(low)
            max_vals.append(high)
        return np.asarray(min_vals, dtype=float), np.asarray(max_vals, dtype=float)

    def _resolve_default_values(self) -> dict[str, float]:
        defaults: dict[str, float] = {}
        for name in self.features:
            if name in self.fit_features:
                continue
            if name in self.fixed:
                defaults[name] = float(self.fixed[name])
                continue
            if name in self.bounds:
                defaults[name] = self.bounds[name][0]
                continue
            defaults[name] = 0.0
        return defaults

    def _resolve_target_bounds(self) -> dict[str, tuple[float, float]]:
        bounds = {}
        for key in self.objective_keys:
            if key in self.bounds:
                bounds[key] = self.bounds[key]
                continue
            logger.warning("Missing bounds for target %s, defaulting to (0, 1).", key)
            bounds[key] = (0.0, 1.0)
        return bounds

    def _resolve_train_x(self) -> np.ndarray | None:
        if not self._needs_distance:
            return None
        for target in self.objective_keys:
            if "distance" not in self.strategies.get(target, "").lower():
                continue
            model = self.models.get(self._target_models[target])
            train_x = self._extract_train_x(model)
            if train_x is not None:
                return train_x
        for model in self.models.values():
            train_x = self._extract_train_x(model)
            if train_x is not None:
                return train_x
        return None

    def _extract_train_x(self, model: Any) -> np.ndarray | None:
        if model is None:
            return None
        aux = getattr(model, "aux", None)
        train_x = getattr(aux, "train_x", None) if aux is not None else None
        if train_x is None:
            train_x = getattr(model, "train_x", None)
        if train_x is None:
            return None
        if hasattr(train_x, "detach"):
            train_x = train_x.detach().cpu().numpy()
        return np.asarray(train_x, dtype=float)

    def _compute_max_distance(self) -> float | None:
        if not self._needs_distance or self._train_x is None:
            return None
        try:
            return float(pdist(self._train_x, metric="euclidean").max())
        except Exception:
            logger.exception("Failed to compute max pairwise distance.")
            return None

    def initialize(self) -> None:
        n_losses = len(self.objective_keys)
        n_constraints = self._n_constraints
        problem = BatchProblem(
            nvars=len(self.fit_features),
            nobjs=n_losses,
            nconstrs=n_constraints,
            batch_function=self._optimize_fun,
        )
        problem.directions[:] = Problem.MINIMIZE
        if n_constraints:
            problem.constraints[:] = "<0"

        for i in range(len(self.fit_features)):
            problem.types[i] = Real(float(self._min_[i]), float(self._max_[i]))

        self.optimization = BatchNSGAII(
            problem,
            population_size=self.population,
            variator=self.variator,
        )

    def step_once(self) -> None:
        if self.optimization is None:
            self.initialize()
        self.step += 1
        self.optimization.run(self.population)
        if self.step == 1 or not self.step % 5 or self.step >= self.generations:
            self._update_results(gen=self.step)
        if hasattr(self.variator, "distribution_index"):
            if self.step >= int(self.generations / 2):
                self.variator.distribution_index = 15
            if self.step >= 3 * int(self.generations / 4):
                self.variator.distribution_index = 10

    def run(self) -> list[OptimizationResult]:
        for _ in range(self.generations):
            self.step_once()
        return list(self._results)

    def _update_results(self, gen: int = 0) -> None:
        results = nondominated(self.optimization.result)
        losses, outputs = self._optimize_fun(results, optimization=False)
        merged: list[OptimizationResult] = []
        for i, l in enumerate(losses):
            x = outputs[i]["x"]
            obj = {k: v for k, v in zip(self.objective_keys, l)}
            loss = math.sqrt(sum(v ** 2 for v in obj.values()))
            merged.append(OptimizationResult(x=x, objectives=obj, loss=loss))
        merged.sort(key=lambda r: r.loss)
        self._results = merged

    def _build_full_x(self, x_fit: Iterable[float]) -> np.ndarray:
        x_fit = list(x_fit)
        full = []
        fit_idx = {name: i for i, name in enumerate(self.fit_features)}
        for name in self.features:
            if name in fit_idx:
                full.append(float(x_fit[fit_idx[name]]))
            else:
                full.append(float(self._default[name]))
        return np.asarray(full, dtype=float)

    def _predict_batch(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
        mean = np.full((x.shape[0], len(self.objective_keys)), np.nan, dtype=float)
        std = (
            np.full((x.shape[0], len(self.objective_keys)), np.nan, dtype=float)
            if self._needs_std
            else None
        )

        for model_name, model in self.models.items():
            pred = model.predict(
                x,
                device=self.device,
                return_std=self._needs_std,
            )
            if isinstance(pred, dict):
                mean_pred = pred.get("mean", pred)
                std_pred = pred.get("std")
            else:
                mean_pred = pred
                std_pred = None

            mean_np = self._to_numpy(mean_pred)
            std_np = self._to_numpy(std_pred) if std_pred is not None else None
            model_targets = list(model.spec.targets)

            for key_idx, target in enumerate(self.objective_keys):
                if self._target_models[target] != model_name:
                    continue
                if target not in model_targets:
                    continue
                target_idx = model_targets.index(target)
                mean[:, key_idx] = mean_np[:, target_idx]
                if std is not None:
                    if std_np is not None:
                        std[:, key_idx] = std_np[:, target_idx]
                    else:
                        std[:, key_idx] = 0.0

        return mean, std

    def _to_numpy(self, value: Any) -> np.ndarray:
        if value is None:
            return None
        if hasattr(value, "to_numpy"):
            return value.to_numpy()
        if hasattr(value, "values"):
            return np.asarray(value.values)
        return np.asarray(value)

    def _optimize_fun(self, solutions, optimization: bool = True):
        x_fit = [s.variables for s in solutions]
        x_full = np.vstack([self._build_full_x(x_) for x_ in x_fit])

        mean, std = self._predict_batch(x_full)
        outputs = self._to_outputs(mean, std, x_full)

        losses = [self.loss_fun(o) for o in outputs]
        constraints = [[] for _ in outputs]

        if optimization:
            if self._n_constraints:
                return losses, constraints
            return losses
        return losses, outputs

    def _to_outputs(
        self,
        mean: np.ndarray,
        std: np.ndarray | None,
        x_full: np.ndarray,
    ) -> list[dict[str, Any]]:
        if mean.ndim == 1:
            mean = mean.reshape(-1, 1)
        std = None if std is None else np.asarray(std)

        outputs: list[dict[str, Any]] = []
        distances = self._distance_to_train(x_full)

        for i in range(mean.shape[0]):
            row = {
                "pred": {k: float(v) for k, v in zip(self.targets, mean[i])},
                "std": {k: float(v) for k, v in zip(self.targets, std[i])} if std is not None else {},
                "dist": float(distances[i]) if distances is not None else None,
                "x": {k: float(v) for k, v in zip(self.features, x_full[i])},
            }
            outputs.append(row)
        return outputs

    def _distance_to_train(self, x_full: np.ndarray) -> np.ndarray | None:
        if not self._needs_distance or self._train_x is None:
            return None
        try:
            distances = cdist(x_full, self._train_x, metric="euclidean")
            return distances.min(axis=1)
        except Exception:
            logger.exception("Failed to compute distances to training data.")
            return None

    def loss_fun(self, output: dict[str, Any]) -> list[float]:
        losses: list[float] = []
        for key, target in zip(self.objective_keys, self.objective_vals):
            pred = output["pred"].get(key)
            strat = self.strategies.get(key, "minimize difference").lower()
            lo, hi = self._target_bounds.get(key, (0.0, 1.0))
            denom = (hi - lo) if hi != lo else 1.0
            base = ((target - pred) / denom) ** 2

            if "greater than" in strat:
                losses.append(0.0 if pred >= target else base)
            elif "smaller than" in strat:
                losses.append(0.0 if pred <= target else base)
            elif "maximize uncertainty" in strat:
                std = output["std"].get(key, 0.0)
                losses.append(-float(std))
            elif "minimize uncertainty" in strat:
                std = output["std"].get(key, 0.0)
                losses.append(float(std))
            elif "maximize distance" in strat:
                dist = output.get("dist")
                if dist is None or not self._max_distance:
                    losses.append(0.0)
                else:
                    losses.append((self._max_distance - dist) / self._max_distance)
            elif "minimize distance" in strat:
                dist = output.get("dist")
                if dist is None or not self._max_distance:
                    losses.append(0.0)
                else:
                    losses.append(dist / self._max_distance)
            else:
                losses.append(base)
        return losses
