from pathlib import Path

import torch
import gpytorch

from shared.env import env_str
from .base import BaseTorchModel
from .registry import register_model
from .specs import ModelConfig, PreprocessConfig, AuxilaryData

TRAIN_DATA_PATH = env_str("TRAIN_DATA_PATH", default="")


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
    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux_data: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux_data=aux_data)

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

    def _format_prediction(self, raw, *, input_kind: str, return_std: bool = False):
        mean = self._inv_transform_y(raw)
        return self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)


class _MultitaskExactGPModel(gpytorch.models.ExactGP):
    def __init__(self, train_x, train_y, likelihood, num_tasks: int):
        super().__init__(train_x, train_y, likelihood)
        self.mean_module = gpytorch.means.MultitaskMean(
            gpytorch.means.ConstantMean(),
            num_tasks=num_tasks,
        )
        self.covar_module = gpytorch.kernels.MultitaskKernel(
            gpytorch.kernels.ScaleKernel(gpytorch.kernels.RBFKernel()),
            num_tasks=num_tasks,
            rank=1,
        )

    def forward(self, x):
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return gpytorch.distributions.MultitaskMultivariateNormal(mean_x, covar_x)


@register_model("multitask_gp")
class MultiOutputExactGP(BaseTorchModel):
    """
    Basic multi-output Exact GP model (gpytorch).
    Expects aux_data.train_x and aux_data.train_y.
    """
    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux_data: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux_data=aux_data)

        train_x = None
        train_y = None

        if self.aux_data is not None:
            train_x = self.aux_data.train_x
            train_y = self.aux_data.train_y

            if (train_x is None or train_y is None) and self.aux_data.extra:
                train_x_path = self.aux_data.extra.get("train_x_path")
                train_y_path = self.aux_data.extra.get("train_y_path")
                if train_x_path and train_y_path:
                    train_x = torch.load(Path(train_x_path))
                    train_y = torch.load(Path(train_y_path))

        if train_x is None or train_y is None:
            if TRAIN_DATA_PATH:
                train_x_path = Path(TRAIN_DATA_PATH) / "train_x.pt"
                train_y_path = Path(TRAIN_DATA_PATH) / "train_y.pt"
                if train_x_path.exists() and train_y_path.exists():
                    train_x = torch.load(train_x_path)
                    train_y = torch.load(train_y_path)

        if train_x is None or train_y is None:
            raise ValueError(
                "multitask_gp requires training data. "
                "Provide aux_data.train_x/train_y or aux_data.extra "
                "with train_x_path/train_y_path to load from disk."
            )

        train_x = torch.as_tensor(train_x, dtype=torch.float32)
        train_y = torch.as_tensor(train_y, dtype=torch.float32)

        num_tasks = self.spec.output_dim
        self.likelihood = gpytorch.likelihoods.MultitaskGaussianLikelihood(num_tasks=num_tasks)
        self.gp_model = _MultitaskExactGPModel(train_x, train_y, self.likelihood, num_tasks=num_tasks)

    def _predict_tensor(self, x: torch.Tensor, *, return_std: bool = False):
        self.gp_model.eval()
        self.likelihood.eval()
        with torch.no_grad(), gpytorch.settings.fast_pred_var():
            preds = self.likelihood(self.gp_model(x))
            mean = preds.mean.detach().cpu().numpy()
            if return_std:
                std = preds.variance.sqrt().detach().cpu().numpy()
                return {"mean": mean, "std": std}
            return mean

    def _format_prediction(self, raw, *, input_kind: str, return_std: bool = False):
        if isinstance(raw, dict):
            mean = self._inv_transform_y(raw["mean"])
            mean = self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)
            if return_std and "std" in raw:
                std = self._to_pandas(raw["std"], columns=self.spec.targets, input_kind=input_kind)
                return {"mean": mean, "std": std}
            return mean

        mean = self._inv_transform_y(raw)
        return self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)
