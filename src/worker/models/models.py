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
    task_type = "regression"
    
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
        ordinal: bool = False,
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
    task_type = "regression"

    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux=aux)

        if aux is None:
            raise ValueError(
                "multitask_gp requires training data. "
                "Provide aux.train_x/train_y or aux.extra "
            )

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
        ordinal: bool = False,
    ):
        if isinstance(raw, dict):
            mean_raw = raw["mean"]

            if return_std and "std" in raw:
                std_raw = raw["std"]
                mean, std, lower, upper = self._inv_transform_y_stats(mean_raw, std_raw)

                result = {
                    "mean": self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind),
                    "std": self._to_pandas(std, columns=self.spec.targets, input_kind=input_kind),
                }

                if return_bounds:
                    result["lower"] = self._to_pandas(lower, columns=self.spec.targets, input_kind=input_kind)
                    result["upper"] = self._to_pandas(upper, columns=self.spec.targets, input_kind=input_kind)

                return result

            mean = self._inv_transform_y(mean_raw)
            return self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)

        mean = self._inv_transform_y(raw)
        return self._to_pandas(mean, columns=self.spec.targets, input_kind=input_kind)


class _DirichletGPClassifier(gpytorch.models.ExactGP):
    def __init__(self, features, target, train_x, train_y, likelihood, num_classes):
        super().__init__(train_x, train_y, likelihood)
        self.features = features
        self.targets = [target]
        self.num_classes = num_classes
        self.batch_shape = torch.Size((self.num_classes,))
        self.mean_module = gpytorch.means.LinearMean(
            batch_shape=self.batch_shape, input_size=len(self.features)
        )
        self.covar_module = (
            gpytorch.kernels.RQKernel(batch_shape=self.batch_shape)
        )

    def forward(self, x):
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return gpytorch.distributions.MultivariateNormal(mean_x, covar_x)


class _MultitaskDirichletGPClassifier(gpytorch.models.IndependentModelList):
    def __init__(self, sub_models):
        super().__init__(*sub_models)
        self.sub_models = sub_models

    def _predict(self, x: torch.Tensor) -> tuple[np.ndarray, np.ndarray]:
        cls_list = []
        prob_list = []

        for model in self.sub_models:
            model.eval()
            model.likelihood.eval()
            with (
                torch.no_grad(),
                gpytorch.settings.fast_pred_var(),
                gpytorch.settings.observation_nan_policy("mask"),
                gpytorch.settings.cholesky_jitter(1e-5),
                warnings.catch_warnings(),
            ):
                warnings.simplefilter("ignore", GPInputWarning)
                latent_dist = model(x)
                alpha_samples = latent_dist.sample(torch.Size((256,))).exp()
                prob_samples = alpha_samples / alpha_samples.sum(dim=1, keepdim=True)
                prob = prob_samples.mean(dim=0).transpose(0, 1)
                cls = prob.argmax(dim=1)
                prob = prob.detach().cpu().numpy()
                cls = cls.detach().cpu().numpy()
                cls_list.append(cls)
                prob_list.append(prob)

        cls = np.stack(cls_list, axis=1)
        prob = np.stack(prob_list, axis=1)
        return cls, prob


@register_model("multitask_dirichlet")
class MultiOutputDirichlet(BaseTorchModel):
    """
    Independent Model List of Dirichlet Classifiers.
    Expects aux.train_x and aux.train_y.
    """
    task_type = "classification"

    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux=aux)

        if aux is None:
            raise ValueError(
                "multitask_gp requires training data. "
                "Provide aux.train_x/train_y or aux.extra "
            )

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
            )

        train_x = _to_float_tensor(train_x)
        train_y = _to_float_tensor(train_y)
        targets = self.spec.targets
        features = self.spec.features

        sub_models = []
        sub_likelihoods = []
        for i, target in enumerate(targets):
            mask_i = ~torch.isnan(train_y[:, i])
            xi = train_x[mask_i, :].clone()
            yi = train_y[mask_i, i].round().long().clone()
            lik_i = gpytorch.likelihoods.DirichletClassificationLikelihood(
                yi,
                learn_additional_noise=True
            )
            model_i = _DirichletGPClassifier(
                features,
                target,
                xi,
                lik_i.transformed_targets,
                lik_i,
                lik_i.num_classes
            )
            sub_models.append(model_i)
            sub_likelihoods.append(lik_i)

        self.likelihood = gpytorch.likelihoods.LikelihoodList(
            *sub_likelihoods
        )
        self.gp_model = _MultitaskDirichletGPClassifier(
            sub_models,
        )
    
    def _predict_tensor(self, x: torch.Tensor, *, return_std: bool = False):
        cls, prob = self.gp_model._predict(x)
        return {"cls": cls, "prob": prob}

    def _format_prediction(
        self,
        raw,
        *,
        input_kind: str,
        return_std: bool = False,
        return_bounds: bool = False,
        ordinal: bool = False,
    ):
        cls = raw["cls"]
        prob = raw["prob"]
        cls_pd = self._to_pandas(cls, columns=self.spec.targets, input_kind=input_kind)

        if not ordinal:
            return {
                "cls": cls_pd,
                "prob": prob,
            }

        prob = np.asarray(prob, dtype=np.float64)

        if prob.ndim != 3:
            raise ValueError(
                "ordinal=True expects raw['prob'] to have shape "
                "(n_samples, n_targets, n_classes)."
            )

        n_samples, n_targets, n_classes = prob.shape

        if n_classes != 2:
            raise ValueError(
                "ordinal=True requires binary one-vs-rest targets, "
                f"but got n_classes={n_classes}."
            )

        # Positive-class probabilities for each binary target/head.
        # Assumes columns/targets are ordered ascending and correspond to:
        # P(Y >= 1), P(Y >= 2), ..., P(Y >= K)
        cum_prob = prob[:, :, 1]

        # Numerical safety.
        cum_prob = np.clip(cum_prob, 0.0, 1.0)

        # Enforce monotone non-increasing cumulative probabilities across
        # ascending thresholds so that:
        # P(Y >= 1) >= P(Y >= 2) >= ... >= P(Y >= K)
        cum_prob = np.minimum.accumulate(cum_prob, axis=1)

        # Recover class probabilities:
        # P(Y=0)   = 1 - P(Y>=1)
        # P(Y=k)   = P(Y>=k) - P(Y>=k+1), k=1,...,K-1
        # P(Y=K)   = P(Y>=K)
        ordinal_prob = np.empty((n_samples, n_targets + 1), dtype=np.float64)
        ordinal_prob[:, 0] = 1.0 - cum_prob[:, 0]
        ordinal_prob[:, 1:-1] = cum_prob[:, :-1] - cum_prob[:, 1:]
        ordinal_prob[:, -1] = cum_prob[:, -1]

        # Final cleanup for numerical stability.
        ordinal_prob = np.clip(ordinal_prob, 0.0, 1.0)
        row_sums = ordinal_prob.sum(axis=1, keepdims=True)
        zero_rows = row_sums.squeeze(-1) <= 0.0
        row_sums[zero_rows] = 1.0
        ordinal_prob = ordinal_prob / row_sums

        ordinal_columns = [f"class_{i}" for i in range(n_targets + 1)]
        ordinal_prob_pd = self._to_pandas(
            ordinal_prob,
            columns=ordinal_columns,
            input_kind=input_kind,
        )

        ordinal_cls = ordinal_prob.argmax(axis=1)
        ordinal_cls_pd = self._to_pandas(
            ordinal_cls.reshape(-1, 1),
            columns=["cls_ordinal"],
            input_kind=input_kind,
        )

        return {
            "cls": cls_pd,
            "prob": prob,
            "cls_ordinal": ordinal_cls_pd,
            "prob_ordinal": ordinal_prob_pd,
        }
