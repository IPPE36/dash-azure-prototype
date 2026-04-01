import json
from dataclasses import asdict
from pathlib import Path

import joblib
import torch
from torch.serialization import safe_globals

from .registry import create_model
from .specs import ModelConfig, PreprocessConfig, AuxilaryData


class ArtifactIO:
    """
    Save/load inference artifacts in a stable layout.
    Layout:
    ------
    artifact_dir/
        config.json
        model_state.pt
        preprocessors.joblib
        aux.pt
    """
    CONFIG_FILENAME = "config.json"
    STATE_FILENAME = "model_state.pt"
    PREP_FILENAME = "preprocessors.joblib"
    AUX_FILENAME = "aux.pt"

    @classmethod
    def save(
        cls,
        artifact_dir: str | Path, 
        *,
        model, 
        spec: ModelConfig, 
        prep: PreprocessConfig = None,
        aux: AuxilaryData = None,
    ) -> None:
        
        artifact_dir = Path(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        with open(artifact_dir / cls.CONFIG_FILENAME, "w", encoding="utf-8") as f:
            json.dump(asdict(spec), f, indent=2)

        joblib.dump(prep or PreprocessConfig(), artifact_dir / cls.PREP_FILENAME)
        
        # Avoid storing training data for ExactGP models; keep it only in aux.
        state_dict = model.state_dict()
        state_dict = {
            k: v
            for k, v in state_dict.items()
            if "train_inputs" not in k and "train_targets" not in k
        }
        torch.save(state_dict, artifact_dir / cls.STATE_FILENAME)
        
        if aux is None or aux.train_x is None or aux.train_y is None:
            if spec.requires_aux:
                raise ValueError(
                    "AuxilaryData with train_x/train_y is required to save artifacts. "
                    "Set allow_missing_aux=True to skip saving aux."
                )
        else:
            torch.save(aux, artifact_dir / cls.AUX_FILENAME)

        return None

    @classmethod
    def load(
        cls,
        artifact_dir: str | Path,
        *,
        device: str | torch.device = "cpu",
    ):
        
        artifact_dir = Path(artifact_dir)

        with open(artifact_dir / cls.CONFIG_FILENAME, "r", encoding="utf-8") as f:
            spec = ModelConfig(**json.load(f))

        prep = joblib.load(artifact_dir / cls.PREP_FILENAME)

        aux_path = artifact_dir / cls.AUX_FILENAME
        aux = None
        if aux_path.exists():
            with safe_globals([AuxilaryData]):
                aux = torch.load(aux_path, map_location=device, weights_only=False)

        elif spec.requires_aux:
            raise FileNotFoundError(f"Missing aux file: {aux_path}")
        state_dict = torch.load(artifact_dir / cls.STATE_FILENAME, map_location=device)

        model = create_model(spec=spec, prep=prep, aux=aux)
        expected_keys = set(model.state_dict().keys())
        saved_keys = set(state_dict.keys())
        missing = expected_keys - saved_keys
        if missing and all(
            ("train_inputs" in key or "train_targets" in key) for key in missing
        ):
            model.load_state_dict(state_dict, strict=False)
        else:
            model.load_state_dict(state_dict)
        model.to(device)
        model.eval()

        return model
