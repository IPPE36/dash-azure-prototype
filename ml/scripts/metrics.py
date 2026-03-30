import numpy as np


def _check_reg_targets(y_true: np.ndarray, y_pred_like: np.ndarray):
    y_true = np.asarray(y_true, dtype=float)
    y_pred_like = np.asarray(y_pred_like, dtype=float)

    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)
    if y_pred_like.ndim == 1:
        y_pred_like = y_pred_like.reshape(-1, 1)

    if y_true.shape != y_pred_like.shape:
        raise ValueError(
            f"Shape mismatch: y_true.shape={y_true.shape}, "
            f"other.shape={y_pred_like.shape}"
        )

    return y_true, y_pred_like


def _aggregate_output(values: np.ndarray, multioutput="uniform_average"):
    values = np.asarray(values, dtype=float)

    if multioutput == "raw_values":
        return values

    if multioutput == "uniform_average":
        return float(np.mean(values))

    weights = np.asarray(multioutput, dtype=float)
    if weights.ndim != 1 or weights.shape[0] != values.shape[0]:
        raise ValueError(
            "multioutput must be 'raw_values', 'uniform_average', "
            "or an array-like of shape (n_outputs,)."
        )
    return float(np.average(values, weights=weights))


def mape(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    eps: float = 1e-8,
    multioutput="uniform_average",
) -> float | np.ndarray:
    """
    Mean Absolute Percentage Error.

    Uses a clipped denominator to avoid division by zero.

    Parameters
    ----------
    y_true : array-like of shape (n_samples,) or (n_samples, n_outputs)
    y_pred : array-like of shape (n_samples,) or (n_samples, n_outputs)
    eps : float, default=1e-8
        Minimum denominator value used in clipping.
    multioutput : {'uniform_average', 'raw_values'} or array-like, default='uniform_average'
        - 'raw_values': return MAPE for each output column
        - 'uniform_average': average across outputs
        - array-like: weighted average across outputs

    Returns
    -------
    float or np.ndarray
        Scalar if averaged, or array of shape (n_outputs,) if raw_values.
    """
    y_true, y_pred = _check_reg_targets(y_true, y_pred)

    denom = np.clip(np.abs(y_true), eps, None)
    per_output = np.mean(np.abs((y_true - y_pred) / denom), axis=0)

    return _aggregate_output(per_output, multioutput)


def picp(
    y_true: np.ndarray,
    *,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
    y_pred: np.ndarray | None = None,
    y_std: np.ndarray | None = None,
    z: float | None = None,
    coverage: float = 0.95,
    multioutput="uniform_average",
) -> float | np.ndarray:
    """
    Prediction Interval Coverage Probability.

    Provide either (lower, upper) bounds directly or (y_pred, y_std) to build
    symmetric normal intervals: y_pred ± z * y_std.

    Parameters
    ----------
    y_true : array-like of shape (n_samples,) or (n_samples, n_outputs)
    lower, upper : array-like, optional
        Direct interval bounds.
    y_pred, y_std : array-like, optional
        Mean prediction and std dev used to construct intervals.
    z : float, optional
        Normal critical value. If omitted, 1.96 is used for coverage=0.95.
    coverage : float, default=0.95
        Coverage level used only when z is None.
    multioutput : {'uniform_average', 'raw_values'} or array-like, default='uniform_average'
        - 'raw_values': return PICP for each output column
        - 'uniform_average': average across outputs
        - array-like: weighted average across outputs

    Returns
    -------
    float or np.ndarray
        Scalar if averaged, or array of shape (n_outputs,) if raw_values.
    """
    y_true = np.asarray(y_true, dtype=float)
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)

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

        if y_pred.ndim == 1:
            y_pred = y_pred.reshape(-1, 1)
        if y_std.ndim == 1:
            y_std = y_std.reshape(-1, 1)

        if y_true.shape != y_pred.shape or y_true.shape != y_std.shape:
            raise ValueError(
                f"Shape mismatch: y_true.shape={y_true.shape}, "
                f"y_pred.shape={y_pred.shape}, y_std.shape={y_std.shape}"
            )

        lower = y_pred - z * y_std
        upper = y_pred + z * y_std
    else:
        lower = np.asarray(lower, dtype=float)
        upper = np.asarray(upper, dtype=float)

        if lower.ndim == 1:
            lower = lower.reshape(-1, 1)
        if upper.ndim == 1:
            upper = upper.reshape(-1, 1)

        if y_true.shape != lower.shape or y_true.shape != upper.shape:
            raise ValueError(
                f"Shape mismatch: y_true.shape={y_true.shape}, "
                f"lower.shape={lower.shape}, upper.shape={upper.shape}"
            )

    covered = (y_true >= lower) & (y_true <= upper)
    per_output = np.mean(covered, axis=0)

    return _aggregate_output(per_output, multioutput)