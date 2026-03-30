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
        if p.scaler_y is not None:
            return p.scaler_y.inverse_transform(y)
        if p.scaler_y_list is not None:
            y = y.copy()
            for i, scaler in enumerate(p.scaler_y_list):
                y[:, i:i + 1] = scaler.inverse_transform(y[:, i:i + 1])
        return y

    def _inv_transform_y_std(self, std: np.ndarray) -> np.ndarray:
        p = self.prep
        if p.scaler_y is not None:
            return _scale_std(std, p.scaler_y)
        if p.scaler_y_list is not None:
            std = std.copy()
            for i, scaler in enumerate(p.scaler_y_list):
                std[:, i:i + 1] = _scale_std(std[:, i:i + 1], scaler)
        return std

    @torch.inference_mode()
    def predict(
        self,
        x: InputType,
        *,
        device: str | torch.device = "cpu",
        clip_bounds: BoundsDict = None,
        return_std: bool = False,
        return_bounds: bool = False,
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
        )

        if clip_bounds:
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


def _scale_std(std: np.ndarray, scaler) -> np.ndarray:
    if hasattr(scaler, "min_") and hasattr(scaler, "scale_"):
        return std / scaler.scale_
    if hasattr(scaler, "scale_"):
        return std * scaler.scale_
    return std


class BaseTorchModel(torch.nn.Module, PredictMixin):
    """Base class for a factory/registry approach."""
    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        torch.nn.Module.__init__(self)
        PredictMixin.__init__(self, spec=spec, prep=prep, aux=aux)
