from pathlib import Path
import logging

import numpy as np
from sklearn.metrics import r2_score
from .metrics import mape, picp


def init_ml_logger(
    log_dir: str | Path,
    name: str,
    *,
    log_to_console: bool = True,
):
    if log_dir is None:
        return None, None
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = log_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    log_path = reports_dir / "train.log"

    logger = logging.getLogger(f"{name}.{id(log_dir)}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
    return logger, log_path


def log_data_summary(
    logger: logging.Logger,
    y_true,
    *,
    phase: str = "Test",
    y_pred=None,
    y_std=None,
    feature_cols: list[str] = None,
    target_cols: list[str] = None,
    coverage: float = 0.95,
) -> dict[str, np.ndarray]:
    """
    Log per-target metrics (R2, MAPE, PICP) plus dataset summary.
    Returns a dict with raw arrays for downstream use.
    """
    y_true = np.asarray(y_true, dtype=float)
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)

    if y_pred is not None:
        y_pred = np.asarray(y_pred, dtype=float)
        if y_pred.ndim == 1:
            y_pred = y_pred.reshape(-1, 1)

    n_features = len(feature_cols)
    n_targets = len(target_cols)
    labels = target_cols or [f"y{i}" for i in range(n_targets)]

    n_obs = int(y_true.shape[0]) if y_true.ndim >= 1 else 0
    non_nan_targets = int(np.sum(~np.isnan(y_true))) if y_true.size else 0
    logger.info(
        "%s start: n_obs=%d n_features=%d n_targets=%d non_nan_targets=%d",
        phase,
        n_obs,
        n_features,
        n_targets,
        non_nan_targets,
    )

    if y_pred is None:
        return {"r2": None, "mape": None, "picp": None}

    r2_vals = r2_score(y_true, y_pred, multioutput="raw_values")
    mape_vals = mape(y_true, y_pred=y_pred, multioutput="raw_values")

    picp_vals = None
    if y_std is not None:
        picp_vals = picp(y_true, y_pred=y_pred, y_std=y_std, multioutput="raw_values")

    logger.info("%s metrics per target:", phase)
    for i, name in enumerate(labels):
        if picp_vals is not None:
            logger.info(
                "  %s | R2=%.4f MAPE=%.4f PICP(%.0f%%)=%.4f",
                name,
                r2_vals[i],
                mape_vals[i],
                coverage * 100.0,
                picp_vals[i],
            )
        else:
            logger.info(
                "  %s | R2=%.4f MAPE=%.4f",
                name,
                r2_vals[i],
                mape_vals[i],
            )

    return {"r2": r2_vals, "mape": mape_vals, "picp": picp_vals}
