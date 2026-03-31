import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.base import TransformerMixin, BaseEstimator


class ALRTransformer(BaseEstimator, TransformerMixin):
    """
    Applies the additive log-ratio (ALR) transform to compositional data.

    Pipeline:
    1. Ensure input is 2D
    2. Replace very small / zero values with `pseudocount`
    3. Close each row to sum to 1
    4. Apply ALR transform using one component as reference
    5. Optionally standardize
    6. Optionally normalize

    Inverse pipeline:
    1. Undo normalization
    2. Undo standardization
    3. Apply inverse ALR
    4. Close rows back to sum to 1

    Parameters
    ----------
    reference_idx : int, default=-1
        Index of the reference component used in the denominator.
    pseudocount : float, default=1e-12
        Small positive value used to replace zeros before log transform.
    standardize : bool, default=False
        Whether to apply StandardScaler after ALR.
    normalize : bool, default=True
        Whether to apply MinMaxScaler after ALR / standardization.
    """

    def __init__(
        self,
        reference_idx: int = -1,
        pseudocount: float = 1e-12,
        standardize: bool = False,
        normalize: bool = True,
    ):
        self.reference_idx = reference_idx
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

    def _validate_params(self, n_features=None):
        if self.pseudocount <= 0:
            raise ValueError(f"pseudocount must be > 0, got {self.pseudocount}")

        if n_features is not None:
            ref = self.reference_idx
            if ref < 0:
                ref = n_features + ref
            if not (0 <= ref < n_features):
                raise ValueError(
                    f"reference_idx={self.reference_idx} is out of bounds for "
                    f"{n_features} features"
                )
            self.reference_idx_ = ref

    def _close(self, X):
        row_sums = np.sum(X, axis=1, keepdims=True)
        if np.any(row_sums <= 0):
            raise ValueError("Each row must have positive sum to form a composition.")
        return X / row_sums

    def _alr(self, X):
        ref = X[:, [self.reference_idx_]]
        mask = np.ones(X.shape[1], dtype=bool)
        mask[self.reference_idx_] = False
        num = X[:, mask]
        return np.log(num / ref)

    def _inverse_alr(self, Z):
        n_samples = Z.shape[0]
        D = self.n_features_in_

        X = np.ones((n_samples, D), dtype=np.float64)

        mask = np.ones(D, dtype=bool)
        mask[self.reference_idx_] = False
        X[:, mask] = np.exp(Z)
        X[:, self.reference_idx_] = 1.0

        return self._close(X)

    def fit(self, X, y=None):
        self._validate_params()
        X = self._validate_input(X)

        if X.shape[1] < 2:
            raise ValueError("ALR requires at least 2 components.")

        if np.any(X < 0):
            raise ValueError("ALRTransformer requires non-negative inputs.")

        self.n_features_in_ = X.shape[1]
        self._validate_params(self.n_features_in_)

        X = np.clip(X, self.pseudocount, None)
        X = self._close(X)
        X_t = self._alr(X)

        if self.standardize:
            self.std_out.fit(X_t)

        if self.normalize:
            X_fit = self.std_out.transform(X_t) if self.standardize else X_t
            self.norm_out.fit(X_fit)

        return self

    def transform(self, X, y=None):
        X = self._validate_input(X)

        if X.shape[1] != self.n_features_in_:
            raise ValueError(
                f"Expected {self.n_features_in_} features, got {X.shape[1]}"
            )

        if np.any(X < 0):
            raise ValueError("ALRTransformer requires non-negative inputs.")

        X = np.clip(X, self.pseudocount, None)
        X = self._close(X)
        X_t = self._alr(X)

        if self.standardize:
            X_t = self.std_out.transform(X_t)

        if self.normalize:
            X_t = self.norm_out.transform(X_t)

        return X_t

    def inverse_transform(self, X, y=None):
        X = self._validate_input(X)

        expected_dim = self.n_features_in_ - 1
        if X.shape[1] != expected_dim:
            raise ValueError(
                f"Expected {expected_dim} ALR coordinates, got {X.shape[1]}"
            )

        if self.normalize:
            X = self.norm_out.inverse_transform(X)

        if self.standardize:
            X = self.std_out.inverse_transform(X)

        X = self._inverse_alr(X)
        return X