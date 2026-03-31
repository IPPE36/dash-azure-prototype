from pathlib import Path
import logging

import numpy as np
from sklearn.metrics import (
    r2_score,
    accuracy_score,
    balanced_accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
    average_precision_score,
)
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
        "%s: n_obs=%d n_features=%d n_targets=%d non_nan_targets=%d",
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


def log_classification_summary(
    logger: logging.Logger,
    y_true,
    *,
    phase: str = "Test",
    y_pred=None,
    y_score=None,
    target_cols: list[str] = None,
    average: str = "binary",
    zero_division: float = 0.0,
) -> dict[str, np.ndarray]:
    """
    Log per-target classification metrics plus dataset summary.

    Parameters
    ----------
    y_true : array-like of shape (n_samples,) or (n_samples, n_targets)
        Ground-truth labels.
    y_pred : array-like of shape (n_samples,) or (n_samples, n_targets), optional
        Predicted class labels.
    y_score : array-like of shape (n_samples,) or (n_samples, n_targets), optional
        Predicted probabilities / confidence scores for the positive class.
        Used for ROC AUC and Average Precision when available.
    average : {"binary", "macro", "micro", "weighted"}, default="binary"
        Averaging mode passed to precision_recall_fscore_support.
        Use "binary" for independent binary targets, "macro" for multiclass targets.
    zero_division : {0.0, 1.0}, default=0.0
        Passed to precision_recall_fscore_support.

    Returns
    -------
    dict[str, np.ndarray]
        Per-target metric arrays for downstream use.
    """
    y_true = np.asarray(y_true)
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)

    if y_pred is not None:
        y_pred = np.asarray(y_pred)
        if y_pred.ndim == 1:
            y_pred = y_pred.reshape(-1, 1)

    if y_score is not None:
        y_score = np.asarray(y_score, dtype=float)
        if y_score.ndim == 1:
            y_score = y_score.reshape(-1, 1)

    n_targets = y_true.shape[1]
    labels = target_cols or [f"y{i}" for i in range(n_targets)]
    n_obs = int(y_true.shape[0]) if y_true.ndim >= 1 else 0
    non_nan_targets = int(np.sum(~np.isnan(y_true))) if y_true.size else 0

    logger.info(
        "%s: n_obs=%d n_targets=%d non_nan_targets=%d",
        phase,
        n_obs,
        n_targets,
        non_nan_targets,
    )

    if y_pred is None:
        return {
            "accuracy": None,
            "balanced_accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "support": None,
            "roc_auc": None,
            "avg_precision": None,
        }

    acc_vals = np.full(n_targets, np.nan, dtype=float)
    bal_acc_vals = np.full(n_targets, np.nan, dtype=float)
    prec_vals = np.full(n_targets, np.nan, dtype=float)
    rec_vals = np.full(n_targets, np.nan, dtype=float)
    f1_vals = np.full(n_targets, np.nan, dtype=float)
    support_vals = np.full(n_targets, np.nan, dtype=float)
    roc_auc_vals = np.full(n_targets, np.nan, dtype=float)
    avg_prec_vals = np.full(n_targets, np.nan, dtype=float)

    logger.info("%s classification metrics per target:", phase)

    for i, name in enumerate(labels):
        yt = y_true[:, i]
        yp = y_pred[:, i]

        mask = ~np.isnan(yt)
        if np.issubdtype(yp.dtype, np.floating):
            mask &= ~np.isnan(yp)

        yt = yt[mask]
        yp = yp[mask]

        if yt.size == 0:
            logger.info("  %s | no valid rows", name)
            continue

        try:
            acc_vals[i] = accuracy_score(yt, yp)
        except Exception:
            pass

        try:
            bal_acc_vals[i] = balanced_accuracy_score(yt, yp)
        except Exception:
            pass

        try:
            p, r, f1, s = precision_recall_fscore_support(
                yt,
                yp,
                average=average,
                zero_division=zero_division,
            )
            prec_vals[i] = p
            rec_vals[i] = r
            f1_vals[i] = f1
            support_vals[i] = float(s) if np.isscalar(s) else np.sum(s)
        except Exception:
            pass

        if y_score is not None:
            ys = y_score[:, i][mask]
            if ys.size == yt.size and np.unique(yt).size >= 2:
                try:
                    roc_auc_vals[i] = roc_auc_score(yt, ys)
                except Exception:
                    pass
                try:
                    avg_prec_vals[i] = average_precision_score(yt, ys)
                except Exception:
                    pass

        extra = ""
        if not np.isnan(roc_auc_vals[i]):
            extra += f" ROC_AUC={roc_auc_vals[i]:.4f}"
        if not np.isnan(avg_prec_vals[i]):
            extra += f" AP={avg_prec_vals[i]:.4f}"

        logger.info(
            "  %s | Acc=%.4f BalAcc=%.4f Precision=%.4f Recall=%.4f F1=%.4f Support=%.0f%s",
            name,
            acc_vals[i],
            bal_acc_vals[i],
            prec_vals[i],
            rec_vals[i],
            f1_vals[i],
            support_vals[i],
            extra,
        )

    return {
        "accuracy": acc_vals,
        "balanced_accuracy": bal_acc_vals,
        "precision": prec_vals,
        "recall": rec_vals,
        "f1": f1_vals,
        "support": support_vals,
        "roc_auc": roc_auc_vals if y_score is not None else None,
        "avg_precision": avg_prec_vals if y_score is not None else None,
    }