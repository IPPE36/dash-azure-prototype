import torch

from worker.models.base import BaseTorchModel
from worker.models.registry import register_model
from worker.models.specs import ModelConfig, PreprocessConfig, AuxilaryData


@register_model("mlp")
class MLP(BaseTorchModel):
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