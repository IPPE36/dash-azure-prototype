import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.base import TransformerMixin, BaseEstimator


class TanhTransformer(BaseEstimator, TransformerMixin):
    """
    Applies a bounded min-max scaling followed by arctanh.

    Pipeline:
    1. Scale each feature into `feature_range` using per-feature quantiles
    2. Apply arctanh
    3. Optionally standardize
    4. Optionally normalize

    Parameters
    ----------
    feature_range : tuple, default=(-0.99, 0.99)
        Range used before arctanh. Must lie strictly inside (-1, 1).
    quantile_range : tuple, default=(1, 99)
        Lower and upper quantiles used to fit the internal MinMaxScaler.
    standardize : bool, default=False
        Whether to apply StandardScaler after arctanh.
    normalize : bool, default=True
        Whether to apply MinMaxScaler after arctanh / standardization.
    """

    def __init__(
        self,
        feature_range: tuple = (-0.99, 0.99),
        quantile_range: tuple = (1, 99),
        standardize: bool = False,
        normalize: bool = True,
    ):
        self.feature_range = feature_range
        self.quantile_range = quantile_range
        self.standardize = standardize
        self.normalize = normalize

        self.norm_ = MinMaxScaler(feature_range=self.feature_range, clip=True)
        self.std_out = StandardScaler()
        self.norm_out = MinMaxScaler()

    def _validate_input(self, X):
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X

    def _validate_params(self):
        low, high = self.feature_range
        if not (-1 < low < high < 1):
            raise ValueError(
                f"feature_range must satisfy -1 < low < high < 1, got {self.feature_range}"
            )

        q_low, q_high = self.quantile_range
        if not (0 <= q_low < q_high <= 100):
            raise ValueError(
                f"quantile_range must satisfy 0 <= q_low < q_high <= 100, got {self.quantile_range}"
            )

    def fit(self, X, y=None):
        self._validate_params()
        X = self._validate_input(X)

        q_low, q_high = self.quantile_range

        # Compute per-feature quantiles while ignoring NaNs
        lo = np.nanpercentile(X, q_low, axis=0)
        hi = np.nanpercentile(X, q_high, axis=0)

        # Guard against constant or near-constant columns
        same = np.isclose(lo, hi, equal_nan=False)
        if np.any(same):
            hi = hi.copy()
            hi[same] = lo[same] + 1.0

        q_mat = np.vstack([lo, hi])
        self.norm_.fit(q_mat)

        X_t = self.norm_.transform(X)
        X_t = np.arctanh(X_t)

        if self.standardize:
            self.std_out.fit(X_t)

        if self.normalize:
            X_fit = self.std_out.transform(X_t) if self.standardize else X_t
            self.norm_out.fit(X_fit)

        return self

    def transform(self, X, y=None):
        X = self._validate_input(X)

        X_t = self.norm_.transform(X)
        X_t = np.arctanh(X_t)

        if self.standardize:
            X_t = self.std_out.transform(X_t)

        if self.normalize:
            X_t = self.norm_out.transform(X_t)

        return X_t

    def inverse_transform(self, X, y=None):
        X = self._validate_input(X)

        if self.normalize:
            X = self.norm_out.inverse_transform(X)

        if self.standardize:
            X = self.std_out.inverse_transform(X)

        X = np.tanh(X)
        X = self.norm_.inverse_transform(X)

        return X