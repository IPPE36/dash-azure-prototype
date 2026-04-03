from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def _as_2d(arr, *, dtype=float) -> np.ndarray:
    if arr is None:
        return None
    arr = np.asarray(arr, dtype=dtype)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    return arr


def _default_labels(prefix: str, n: int) -> list[str]:
    return [f"{prefix}{i}" for i in range(n)]


def interval_bounds(
    *,
    y_pred=None,
    y_std=None,
    lower=None,
    upper=None,
    z: float | None = None,
    coverage: float = 0.95,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Resolve prediction interval bounds.

    Provide either (lower, upper) or (y_pred, y_std). When using y_pred/y_std,
    symmetric normal intervals are used: y_pred ± z * y_std.
    """
    if lower is None or upper is None:
        if y_pred is None or y_std is None:
            raise ValueError("Provide lower/upper or y_pred/y_std.")
        if z is None:
            if np.isclose(coverage, 0.95):
                z = 1.96
            else:
                raise ValueError("Provide z for coverage values other than 0.95.")
        y_pred = _as_2d(y_pred)
        y_std = _as_2d(y_std)
        lower = y_pred - z * y_std
        upper = y_pred + z * y_std
    else:
        lower = _as_2d(lower)
        upper = _as_2d(upper)
    return lower, upper


def picp_outlier_mask(
    y_true,
    *,
    y_pred=None,
    y_std=None,
    lower=None,
    upper=None,
    z: float | None = None,
    coverage: float = 0.95,
    reduce: str | None = "any",
) -> np.ndarray:
    """
    Return a mask for datapoints that fall outside the prediction interval.

    Parameters
    ----------
    reduce : {"any", "all", None}
        - "any": mark a row as outlier if any target is outside its interval.
        - "all": mark a row as outlier if all targets are outside their intervals.
        - None: return the per-target boolean mask.
    """
    y_true = _as_2d(y_true)
    lower, upper = interval_bounds(
        y_pred=y_pred,
        y_std=y_std,
        lower=lower,
        upper=upper,
        z=z,
        coverage=coverage,
    )

    if y_true.shape != lower.shape or y_true.shape != upper.shape:
        raise ValueError(
            f"Shape mismatch: y_true.shape={y_true.shape}, "
            f"lower.shape={lower.shape}, upper.shape={upper.shape}"
        )

    valid = ~np.isnan(y_true) & ~np.isnan(lower) & ~np.isnan(upper)
    outside = valid & ((y_true < lower) | (y_true > upper))

    if reduce is None:
        return outside
    if reduce == "any":
        return np.any(outside, axis=1)
    if reduce == "all":
        return np.all(outside, axis=1)
    raise ValueError("reduce must be 'any', 'all', or None.")


def build_outliers_dataframe(
    x,
    y_true,
    *,
    y_pred=None,
    y_std=None,
    lower=None,
    upper=None,
    z: float | None = None,
    coverage: float = 0.95,
    feature_cols: Iterable[str] | None = None,
    target_cols: Iterable[str] | None = None,
    phase: str | None = None,
    reduce: str | None = "any",
    include_all: bool = False,
    include_errors: bool = True,
    eps: float = 1e-8,
) -> pd.DataFrame:
    """
    Build a dataframe of outliers (or all rows) with inputs, targets, and intervals.
    """
    x = _as_2d(x)
    y_true = _as_2d(y_true)
    y_pred = _as_2d(y_pred) if y_pred is not None else None
    y_std = _as_2d(y_std) if y_std is not None else None

    n_samples = int(x.shape[0]) if x is not None else int(y_true.shape[0])
    n_features = int(x.shape[1]) if x is not None else 0
    n_targets = int(y_true.shape[1]) if y_true is not None else 0

    feature_cols = list(feature_cols) if feature_cols is not None else _default_labels("X", n_features)
    target_cols = list(target_cols) if target_cols is not None else _default_labels("Y", n_targets)

    data = {}
    data["row_index"] = np.arange(n_samples, dtype=int)
    if phase is not None:
        data["phase"] = [phase] * n_samples

    if x is not None and n_features:
        for idx, name in enumerate(feature_cols):
            data[name] = x[:, idx]

    if y_true is not None and n_targets:
        for idx, name in enumerate(target_cols):
            data[f"y_true_{name}"] = y_true[:, idx]

    if y_pred is not None:
        for idx, name in enumerate(target_cols):
            data[f"y_pred_{name}"] = y_pred[:, idx]

    if y_std is not None:
        for idx, name in enumerate(target_cols):
            data[f"y_std_{name}"] = y_std[:, idx]

    has_bounds = False
    lower_arr = None
    upper_arr = None
    if (lower is not None and upper is not None) or (y_pred is not None and y_std is not None):
        lower_arr, upper_arr = interval_bounds(
            y_pred=y_pred,
            y_std=y_std,
            lower=lower,
            upper=upper,
            z=z,
            coverage=coverage,
        )
        has_bounds = True
        for idx, name in enumerate(target_cols):
            data[f"lower_{name}"] = lower_arr[:, idx]
            data[f"upper_{name}"] = upper_arr[:, idx]

    if include_errors and y_pred is not None:
        abs_err = np.abs(y_true - y_pred)
        denom = np.clip(np.abs(y_true), eps, None)
        pct_err = abs_err / denom
        for idx, name in enumerate(target_cols):
            data[f"abs_err_{name}"] = abs_err[:, idx]
            data[f"pct_err_{name}"] = pct_err[:, idx]

    outlier_any = np.zeros(n_samples, dtype=bool)
    outlier_count = np.zeros(n_samples, dtype=int)
    if has_bounds:
        outside = picp_outlier_mask(
            y_true,
            y_pred=y_pred,
            y_std=y_std,
            lower=lower_arr,
            upper=upper_arr,
            z=z,
            coverage=coverage,
            reduce=None,
        )
        for idx, name in enumerate(target_cols):
            data[f"outside_{name}"] = outside[:, idx]
        outlier_any = picp_outlier_mask(
            y_true,
            y_pred=y_pred,
            y_std=y_std,
            lower=lower_arr,
            upper=upper_arr,
            z=z,
            coverage=coverage,
            reduce="any" if reduce is None else reduce,
        )
        outlier_count = np.sum(outside, axis=1)

    data["outlier_any"] = outlier_any
    data["outlier_count"] = outlier_count

    df = pd.DataFrame(data)
    if include_all:
        return df
    return df[df["outlier_any"]].reset_index(drop=True)


def save_outliers_csv(path: str | Path, df: pd.DataFrame) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
