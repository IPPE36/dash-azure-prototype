import json
from dataclasses import asdict
from pathlib import Path

import joblib
import torch

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
        
        torch.save(model.state_dict(), artifact_dir / cls.STATE_FILENAME)
        torch.save(aux, artifact_dir / cls.AUX_FILENAME)

        return None

    @classmethod
    def load(
        cls,
        artifact_dir: str | Path,
        *,
        device: str | torch.device = "cpu"
    ):
        
        artifact_dir = Path(artifact_dir)

        with open(artifact_dir / cls.CONFIG_FILENAME, "r", encoding="utf-8") as f:
            spec = ModelConfig(**json.load(f))

        prep = joblib.load(artifact_dir / cls.PREP_FILENAME)

        aux = torch.load(artifact_dir / cls.AUX_FILENAME, map_location=device)
        state_dict = torch.load(artifact_dir / cls.STATE_FILENAME, map_location=device)

        model = create_model(spec=spec, prep=prep, aux=aux)
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()

        return model
