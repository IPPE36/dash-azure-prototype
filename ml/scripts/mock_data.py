from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.datasets import make_regression


def make_mock_df(
    n_features: int,
    n_targets: int,
    n_samples: int = 1000,
    feature_prefix: str = "x",
    target_prefix: str = "y",
    noise: float = 0.0,
    random_state: int = 42,
) -> pd.DataFrame:
    """Create a mock dataset using sklearn.datasets.make_regression."""

    if n_features <= 0:
        raise ValueError("n_features must be > 0")
    if n_targets <= 0:
        raise ValueError("n_targets must be > 0")
    if n_samples <= 0:
        raise ValueError("n_rows must be > 0")

    x, y = make_regression(
        n_features=n_features,
        n_targets=n_targets,
        n_samples=n_samples,
        noise=noise,
        random_state=random_state,
    )

    x = x.astype(np.float32)
    y = y.astype(np.float32)
    if n_targets == 1:
        y = y.reshape(-1, 1)

    feature_cols = _col_names(feature_prefix, n_features)
    target_cols = _col_names(target_prefix, n_targets)
    data = np.concatenate([x, y], axis=1)
    columns = list(feature_cols) + list(target_cols)
    return pd.DataFrame(data=data, columns=columns)


def _col_names(prefix: str, count: int) -> Iterable[str]:
    return [f"{prefix}{i}" for i in range(count)]
