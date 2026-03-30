from pathlib import Path

import numpy as np
import torch
import gpytorch
import warnings
from gpytorch.priors import GammaPrior
from gpytorch.utils.warnings import GPInputWarning

from .base import BaseTorchModel
from .registry import register_model
from .specs import ModelConfig, PreprocessConfig, AuxilaryData


@register_model("mlp_regressor")
class MLPRegressor(BaseTorchModel):
    """
    Plain feed-forward regressor.
    Supported model_kwargs
    ----------------------
    hidden_dims: list[int]
        Example: [128, 128, 64]
    dropout: float
        Example: 0.1
    """
    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux=aux)

        hidden_dims = spec.model_kwargs.get("hidden_dims", [128, 128, 64])
        dropout = float(spec.model_kwargs.get("dropout", 0.0))

        layers: list[torch.nn.Module] = []
        in_dim = spec.input_dim

        for hidden_dim in hidden_dims:
            layers.append(torch.nn.Linear(in_dim, hidden_dim))
            layers.append(torch.nn.ReLU())
            if dropout > 0:
                layers.append(torch.nn.Dropout(dropout))
            in_dim = hidden_dim

        layers.append(torch.nn.Linear(in_dim, spec.output_dim))
        self.model = torch.nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)

    def _predict_tensor(self, x: torch.Tensor, *, return_std: bool = False):
        return self(x).detach().cpu().numpy()

    def _format_prediction(
        self,
        raw,
        *,
        input_kind: str,
        return_std: bool = False,
        return_bounds: bool = False,
    ):
        mean = self._inv_transform_y(raw)
        return self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)


class _MultitaskExactGPModel(gpytorch.models.ExactGP):
    def __init__(self, train_x, train_y, likelihood, num_tasks: int, *, covar_rank: int = 1):
        super().__init__(train_x, train_y, likelihood)
        self.mean_module = gpytorch.means.MultitaskMean(
            gpytorch.means.LinearMean(input_size=train_x.shape[-1], bias=True),
            num_tasks=num_tasks,
        )
        self.covar_module = gpytorch.kernels.MultitaskKernel(
            gpytorch.kernels.RQKernel(),
            num_tasks=num_tasks,
            rank=covar_rank,
        )

    def forward(self, x):
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return gpytorch.distributions.MultitaskMultivariateNormal(mean_x, covar_x)


@register_model("multitask_gp")
class MultiOutputExactGP(BaseTorchModel):
    """
    Basic multi-output Exact GP model (gpytorch).
    Expects aux.train_x and aux.train_y.
    """
    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux=aux)

        if aux is None:
            raise ValueError("GPR requires train info in auxilary data!")

        train_x = self.aux.train_x
        train_y = self.aux.train_y

        if (train_x is None or train_y is None) and self.aux.extra:
            train_x_path = self.aux.extra.get("train_x_path")
            train_y_path = self.aux.extra.get("train_y_path")
            if train_x_path and train_y_path:
                train_x = torch.load(Path(train_x_path))
                train_y = torch.load(Path(train_y_path))

        if train_x is None or train_y is None:
            raise ValueError(
                "multitask_gp requires training data. "
                "Provide aux.train_x/train_y or aux.extra "
                "with train_x_path/train_y_path to load from disk."
            )

        train_x = _to_float_tensor(train_x)
        train_y = _to_float_tensor(train_y)

        num_tasks = self.spec.output_dim
        covar_rank = int(self.spec.model_kwargs.get(
            "covar_rank",
            1,
        ))
        has_task_noise = bool(self.spec.model_kwargs.get(
            "has_task_noise",
            num_tasks > 1,
        ))
        has_global_noise = bool(self.spec.model_kwargs.get(
            "has_global_noise",
            True,
        ))
        noise_rank = int(self.spec.model_kwargs.get(
            "noise_rank", 
            0 if num_tasks == 1 else 1,
        ))
        noise_prior = self.spec.model_kwargs.get(
            "noise_prior",
            GammaPrior(2.0, 100.0),  # for minmax targets
        )
        noise_constraint = self.spec.model_kwargs.get(
            "noise_constraint",
            gpytorch.constraints.GreaterThan(1e-5),  # for moderately noisy targets
        )

        self.likelihood = gpytorch.likelihoods.MultitaskGaussianLikelihood(
            num_tasks=num_tasks,
            has_global_noise=has_global_noise,
            has_task_noise=has_task_noise,
            rank=noise_rank,
            noise_prior=noise_prior,
            noise_constraint=noise_constraint,
        )
        self.gp_model = _MultitaskExactGPModel(
            train_x,
            train_y,
            self.likelihood,
            num_tasks=num_tasks,
            covar_rank=covar_rank,
        )

    def _predict_tensor(self, x: torch.Tensor, *, return_std: bool = False):
        self.gp_model.eval()
        self.likelihood.eval()
        with (
            torch.no_grad(),
            gpytorch.settings.fast_pred_var(),
            gpytorch.settings.observation_nan_policy("mask"),
            gpytorch.settings.cholesky_jitter(1e-5),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", GPInputWarning)
            preds = self.likelihood(self.gp_model(x))
            mean = preds.mean.detach().cpu().numpy()
            if return_std:
                std = preds.variance.sqrt().detach().cpu().numpy()
                return {"mean": mean, "std": std}
            return mean

    def _format_prediction(
        self,
        raw,
        *,
        input_kind: str,
        return_std: bool = False,
        return_bounds: bool = False,
    ):
        if isinstance(raw, dict):
            mean_raw = raw["mean"]
            mean = self._inv_transform_y(mean_raw)
            mean = self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)
            if return_std and "std" in raw:
                std_raw = raw["std"]
                std = self._inv_transform_y_std(std_raw)
                std = self._to_pandas(std, columns=self.spec.targets, input_kind=input_kind)
                result = {"mean": mean, "std": std}
                if return_bounds:
                    lower_raw = mean_raw - 1.96 * std_raw
                    upper_raw = mean_raw + 1.96 * std_raw
                    lower = self._inv_transform_y(lower_raw)
                    upper = self._inv_transform_y(upper_raw)
                    result["lower"] = self._to_pandas(lower, columns=self.spec.targets, input_kind=input_kind)
                    result["upper"] = self._to_pandas(upper, columns=self.spec.targets, input_kind=input_kind)
                return result
            return mean
        
        mean = self._inv_transform_y(raw)
        return self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)


def _to_float_tensor(value):
    if isinstance(value, torch.Tensor):
        if value.dtype != torch.float32:
            return value.to(dtype=torch.float32)
        return value
    if isinstance(value, np.ndarray):
        if not value.flags.writeable:
            value = value.copy()
        return torch.as_tensor(value, dtype=torch.float32)
    return torch.as_tensor(value, dtype=torch.float32)
