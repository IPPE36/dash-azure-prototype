import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.base import TransformerMixin, BaseEstimator


class CLRTransformer(BaseEstimator, TransformerMixin):
    """
    Applies the centered log-ratio (CLR) transform to compositional data.

    Pipeline:
    1. Ensure input is 2D
    2. Replace very small / zero values with `pseudocount`
    3. Close each row to sum to 1
    4. Apply CLR transform
    5. Optionally standardize
    6. Optionally normalize

    Inverse pipeline:
    1. Undo normalization
    2. Undo standardization
    3. Apply inverse CLR
    4. Close rows back to sum to 1

    Parameters
    ----------
    pseudocount : float, default=1e-12
        Small positive value used to replace zeros before log transform.
    standardize : bool, default=False
        Whether to apply StandardScaler after CLR.
    normalize : bool, default=True
        Whether to apply MinMaxScaler after CLR / standardization.
    """

    def __init__(
        self,
        pseudocount: float = 1e-12,
        standardize: bool = False,
        normalize: bool = True,
    ):
        self.pseudocount = pseudocount
        self.standardize = standardize
        self.normalize = normalize

        self.std_out = StandardScaler()
        self.norm_out = MinMaxScaler()

    def _validate_input(self, X):
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X

    def _validate_params(self):
        if self.pseudocount <= 0:
            raise ValueError(
                f"pseudocount must be > 0, got {self.pseudocount}"
            )

    def _close(self, X):
        row_sums = np.sum(X, axis=1, keepdims=True)
        if np.any(row_sums <= 0):
            raise ValueError("Each row must have positive sum to form a composition.")
        return X / row_sums

    def _clr(self, X):
        logX = np.log(X)
        mean_log = np.mean(logX, axis=1, keepdims=True)
        return logX - mean_log

    def _inverse_clr(self, X):
        Y = np.exp(X)
        return self._close(Y)

    def fit(self, X, y=None):
        self._validate_params()
        X = self._validate_input(X)

        if np.any(X < 0):
            raise ValueError("CLRTransformer requires non-negative inputs.")

        X = np.clip(X, self.pseudocount, None)
        X = self._close(X)
        X_t = self._clr(X)

        if self.standardize:
            self.std_out.fit(X_t)

        if self.normalize:
            X_fit = self.std_out.transform(X_t) if self.standardize else X_t
            self.norm_out.fit(X_fit)

        return self

    def transform(self, X, y=None):
        X = self._validate_input(X)

        if np.any(X < 0):
            raise ValueError("CLRTransformer requires non-negative inputs.")

        X = np.clip(X, self.pseudocount, None)
        X = self._close(X)
        X_t = self._clr(X)

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

        X = self._inverse_clr(X)
        return X