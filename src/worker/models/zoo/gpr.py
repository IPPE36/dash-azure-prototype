from pathlib import Path

import torch
import gpytorch
import warnings
from gpytorch.priors import GammaPrior, NormalPrior
from gpytorch.utils.warnings import GPInputWarning

from worker.models.base import BaseTorchModel
from worker.models.registry import register_model
from worker.models.specs import ModelConfig, PreprocessConfig, AuxilaryData
from worker.torch_utils import as_float_tensor


class _GPR(gpytorch.models.ExactGP):
    def __init__(self, train_x, train_y, likelihood, num_tasks: int, *, covar_rank: int = 1):
        super().__init__(train_x, train_y, likelihood)
        d = train_x.shape[-1]
        self.mean_module = gpytorch.means.MultitaskMean(
            gpytorch.means.LinearMean(input_size=d, bias=True),
            num_tasks=num_tasks,
        )
        base_kernel = gpytorch.kernels.RQKernel(
            ard_num_dims=d,
            lengthscale_prior=GammaPrior(2.0, 1.0),   # mean=2, mode=1
            alpha_prior=GammaPrior(2.0, 1.0),         # mild preference for alpha ~ 1-2
            lengthscale_constraint=gpytorch.constraints.GreaterThan(1e-4),
        )
        scaled_kernel = gpytorch.kernels.ScaleKernel(
            base_kernel,
            outputscale_prior=GammaPrior(2.0, 1.0),   # signal variance ~ O(1)
            outputscale_constraint=gpytorch.constraints.GreaterThan(1e-4),
        )
        self.covar_module = gpytorch.kernels.MultitaskKernel(
            scaled_kernel,
            num_tasks=num_tasks,
            rank=covar_rank,
        )
        # Optional: regularize linear mean a bit for standardized data
        # Uncomment if you want the mean to stay conservative on small datasets:
        self.mean_module.base_means[0].register_prior(
            "weights_prior",
            NormalPrior(0.0, 0.5),
            "weights",
        )
        self.mean_module.base_means[0].register_prior(
            "bias_prior",
            NormalPrior(0.0, 0.5),
            "bias",
        )


    def forward(self, x):
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return gpytorch.distributions.MultitaskMultivariateNormal(mean_x, covar_x)


class _GPRL(gpytorch.models.ExactGP):
    def __init__(self, train_x, train_y, likelihood, num_tasks: int, *, covar_rank: int = 1):
        super().__init__(train_x, train_y, likelihood)
        d = train_x.shape[-1]
        device = train_x.device
        self.mean_module = gpytorch.means.MultitaskMean(
            gpytorch.means.LinearMean(input_size=d, bias=True),
            num_tasks=num_tasks,
        )
        base_kernel = gpytorch.kernels.LinearKernel(
            variance_prior=GammaPrior(2.0, 1.0),   
            variance_constraint=gpytorch.constraints.GreaterThan(1e-4),
        )
        self.covar_module = gpytorch.kernels.MultitaskKernel(
            base_kernel,
            num_tasks=num_tasks,
            rank=covar_rank,
        )
        # Optional: regularize linear mean for standardized data
        # Uncomment if you want a more conservative mean on small datasets.
        self.mean_module.base_means[0].register_prior(
            "weights_prior",
            NormalPrior(0.0, 0.5),
            "weights",
        )
        self.mean_module.base_means[0].register_prior(
            "bias_prior",
            NormalPrior(0.0, 0.5),
            "bias",
        )

    def forward(self, x):
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return gpytorch.distributions.MultitaskMultivariateNormal(mean_x, covar_x)
    

class BaseGPR(BaseTorchModel):
    task_type = "regression"
    gp_model_cls = _GPR

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

        train_x = as_float_tensor(train_x)
        train_y = as_float_tensor(train_y)

        num_tasks = self.spec.output_dim
        covar_rank = int(self.spec.model_kwargs.get(
            "covar_rank",
            1
        ))
        has_task_noise = bool(self.spec.model_kwargs.get(
            "has_task_noise",
            num_tasks > 1
        ))
        has_global_noise = bool(self.spec.model_kwargs.get(
            "has_global_noise",
            True
        ))
        noise_rank = int(self.spec.model_kwargs.get(
            "noise_rank",
            0 if num_tasks == 1 else 1)
        )
        noise_prior = self.spec.model_kwargs.get(
            "noise_prior",
            GammaPrior(2.0, 50.0)
        )
        noise_constraint = self.spec.model_kwargs.get(
            "noise_constraint",
            gpytorch.constraints.GreaterThan(1e-4),
        )

        self.likelihood = gpytorch.likelihoods.MultitaskGaussianLikelihood(
            num_tasks=num_tasks,
            has_global_noise=has_global_noise,
            has_task_noise=has_task_noise,
            rank=noise_rank,
            noise_prior=noise_prior,
            noise_constraint=noise_constraint,
        )

        self.gp_model = self.gp_model_cls(
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
    

@register_model("gpr")
class GPR(BaseGPR):
    gp_model_cls = _GPR


@register_model("lin")
class LIN(BaseGPR):
    gp_model_cls = _GPRL
