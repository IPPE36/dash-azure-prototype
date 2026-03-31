from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
import torch

from .specs import ModelConfig, PreprocessConfig, AuxilaryData


BoundsDict = dict[str, tuple[float, float]] | None
PandasType = pd.Series | pd.DataFrame
InputType = np.ndarray | list | pd.Series | pd.DataFrame


class PredictMixin(ABC):
    """Reusable inference logic shared by different model types."""
    spec: ModelConfig
    prep: PreprocessConfig
    aux: AuxilaryData
    task_type: str = "regression"

    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        self.spec = spec
        self.prep = prep or PreprocessConfig()
        self.aux = aux or AuxilaryData()

    @abstractmethod
    def _predict_tensor(self, x: torch.Tensor, *, return_std: bool = False):
        raise NotImplementedError

    @abstractmethod
    def _format_prediction(
        self,
        raw,
        *,
        input_kind: str,
        return_std: bool = False,
        return_bounds: bool = False,
        ordinal: bool = False,
    ):
        raise NotImplementedError

    def _coerce_x(self, x: InputType) -> tuple[np.ndarray, str]:
        """
        Convert supported user inputs into a 2D numpy array.
        Returns (x_array, input_kind), where input_kind is one of:
        "dataframe", "series", or "array".
        """

        input_kind = "array"

        if isinstance(x, pd.DataFrame):
            x = x[self.spec.features].to_numpy()
            input_kind = "dataframe"

        if isinstance(x, pd.Series):
            x = x[self.spec.features].to_numpy()
            input_kind = "series"

        if isinstance(x, list):
            x = np.asarray(x)

        if not isinstance(x, np.ndarray):
            x = np.asarray(x)

        if x.ndim == 1:
            x = x.reshape(1, -1)

        if x.shape[1] != len(self.spec.features):
            raise ValueError(
                f"Expected {len(self.spec.features)} features, got {x.shape[1]}."
            )

        return x, input_kind

    def _transform_x(self, x: np.ndarray) -> np.ndarray:
        p = self.prep
        if p.scaler_x is not None:
            x = p.scaler_x.transform(x)
        if p.pca_x is not None:
            x = p.pca_x.transform(x)
        return x

    def _inv_transform_y(self, y: np.ndarray) -> np.ndarray:
        p = self.prep
        y = np.asarray(y, dtype=np.float64)

        if p.scaler_y is not None:
            return p.scaler_y.inverse_transform(y)

        return y

    def _inv_transform_y_stats(
        self,
        mean: np.ndarray,
        std: np.ndarray,
        *,
        z: float = 1.96,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Inverse-transform Gaussian predictions from scaled space to original space.

        Instead of scaling std directly, compute Gaussian lower/upper bounds in
        scaled space, inverse-transform those bounds, and then recompute std in
        original space from the transformed interval.

        Returns
        -------
        mean_unscaled, std_unscaled, lower_unscaled, upper_unscaled
        """
        p = self.prep
        mean = np.asarray(mean, dtype=np.float64)
        std = np.asarray(std, dtype=np.float64)

        if p.scaler_y is not None:
            return _inverse_transform_gaussian_stats(mean, std, p.scaler_y, z=z)

        lower = mean - z * std
        upper = mean + z * std
        return mean, std, lower, upper

    @torch.inference_mode()
    def predict(
        self,
        x: InputType,
        *,
        device: str | torch.device = "cpu",
        clip_bounds: BoundsDict = None,
        return_std: bool = False,
        return_bounds: bool = False,
        ordinal: bool = False,
    ) -> Any:
        """
        High-level inference entry point.
        Parameters
        ----------
        x:
            One sample or many samples.
        device:
            Inference device. Keeping this explicit is cleaner than auto-moving
            the model to cuda on every call.
        clip_bounds:
            Optional dict like:
            {
                "target_a": (0.0, 100.0),
                "target_b": (-5.0, 5.0),
            }
        """

        if self.task_type != "classification":
            if ordinal:
                raise ValueError("'ordinal' is only supported for classification models.")
        if self.task_type != "regression":
            if clip_bounds is not None:
                raise ValueError("'clip_bounds' is only supported for regression models.")
            if return_bounds:
                raise ValueError("'return_bounds' is only supported for regression models.")
        
        x_np, input_kind = self._coerce_x(x)
        x_np = self._transform_x(x_np)
        x_tensor = torch.as_tensor(x_np, dtype=torch.float32, device=device)

        self.to(device)
        self.eval()

        raw = self._predict_tensor(x_tensor, return_std=return_std)
        pred = self._format_prediction(
            raw=raw,
            input_kind=input_kind,
            return_std=return_std,
            return_bounds=return_bounds,
            ordinal=ordinal,
        )

        if self.task_type == "regression" and clip_bounds:
            pred = self._clip_prediction(pred, clip_bounds)

        return pred

    def _clip_output(self, y: PandasType, clip_bounds: BoundsDict) -> PandasType:
        lower = {k: v[0] for k, v in clip_bounds.items()}
        upper = {k: v[1] for k, v in clip_bounds.items()}
        if isinstance(y, pd.DataFrame):
            return y.clip(lower=lower, upper=upper, axis=1)
        return y.clip(lower=pd.Series(lower), upper=pd.Series(upper))

    def _clip_prediction(self, pred, clip_bounds: BoundsDict):
        if isinstance(pred, (pd.Series, pd.DataFrame)):
            return self._clip_output(pred, clip_bounds)

        if isinstance(pred, dict):
            for key in ("mean", "lower", "upper"):
                value = pred.get(key)
                if isinstance(value, (pd.Series, pd.DataFrame)):
                    pred[key] = self._clip_output(value, clip_bounds)
            return pred

        return pred

    def _to_pandas(self, y: np.ndarray, *, columns: list[str], input_kind: str):
        if input_kind == "dataframe":
            return pd.DataFrame(y, columns=columns)
        if input_kind == "series":
            return pd.Series(y[0], index=columns)
        return y
    
    def _to_pandas_labels(self, y: np.ndarray, *, columns: list[str], input_kind: str):
        if input_kind == "dataframe":
            return pd.DataFrame(y, columns=columns)
        if input_kind == "series":
            return pd.Series(y[0], index=columns)
        return y


def _inverse_transform_gaussian_stats(
    mean: np.ndarray,
    std: np.ndarray,
    scaler,
    z: float = 1.96,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Transform Gaussian mean/std from scaled space to original space by:
      1. computing lower/upper bounds in scaled space
      2. inverse-transforming mean/lower/upper
      3. recomputing std in original space assuming Gaussian symmetry:
            std_unscaled = (upper_unscaled - lower_unscaled) / (2 * z)

    Returns
    -------
    mean_unscaled, std_unscaled, lower_unscaled, upper_unscaled
    """
    mean = np.asarray(mean, dtype=np.float64)
    std = np.asarray(std, dtype=np.float64)

    lower = mean - z * std
    upper = mean + z * std

    mean_unscaled = scaler.inverse_transform(mean)
    lower_unscaled = scaler.inverse_transform(lower)
    upper_unscaled = scaler.inverse_transform(upper)

    std_unscaled = (upper_unscaled - lower_unscaled) / (2.0 * z)
    std_unscaled = np.maximum(std_unscaled, 0.0)

    return mean_unscaled, std_unscaled, lower_unscaled, upper_unscaled


class BaseTorchModel(torch.nn.Module, PredictMixin):
    """Base class for a factory/registry approach."""
    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        torch.nn.Module.__init__(self)
        PredictMixin.__init__(self, spec=spec, prep=prep, aux=aux)
