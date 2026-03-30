import numpy as np


def mape(
        y_true: np.ndarray,
        y_pred: np.ndarray, *,
        eps: float = 1e-8
) -> float:
    """
    Mean Absolute Percentage Error.

    Uses a clipped denominator to avoid division by zero.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.clip(np.abs(y_true), eps, None)
    return float(np.mean(np.abs((y_true - y_pred) / denom)))


def picp(
    y_true: np.ndarray,
    *,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
    y_pred: np.ndarray | None = None,
    y_std: np.ndarray | None = None,
    z: float | None = None,
    coverage: float = 0.95,
) -> float:
    """
    Prediction Interval Coverage Probability.

    Provide either (lower, upper) bounds directly or (y_pred, y_std) to build
    symmetric normal intervals: y_pred ± z * y_std.
    """
    y_true = np.asarray(y_true, dtype=float)

    if lower is None or upper is None:
        if y_pred is None or y_std is None:
            raise ValueError("Provide lower/upper or y_pred/y_std.")
        if z is None:
            if np.isclose(coverage, 0.95):
                z = 1.96
            else:
                raise ValueError("Provide z for coverage values other than 0.95.")
        y_pred = np.asarray(y_pred, dtype=float)
        y_std = np.asarray(y_std, dtype=float)
        lower = y_pred - z * y_std
        upper = y_pred + z * y_std
    else:
        lower = np.asarray(lower, dtype=float)
        upper = np.asarray(upper, dtype=float)

    covered = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(covered))
