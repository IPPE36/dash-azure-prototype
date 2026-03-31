import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.base import TransformerMixin, BaseEstimator


class ILRTransformer(BaseEstimator, TransformerMixin):
    """
    Applies the isometric log-ratio (ILR) transform to compositional data.

    Pipeline:
    1. Ensure input is 2D
    2. Replace very small / zero values with `pseudocount`
    3. Close each row to sum to 1
    4. Apply ILR transform using a Helmert sub-matrix basis
    5. Optionally standardize
    6. Optionally normalize

    Inverse pipeline:
    1. Undo normalization
    2. Undo standardization
    3. Apply inverse ILR
    4. Close rows back to sum to 1

    Parameters
    ----------
    pseudocount : float, default=1e-12
        Small positive value used to replace zeros before log transform.
    standardize : bool, default=False
        Whether to apply StandardScaler after ILR.
    normalize : bool, default=True
        Whether to apply MinMaxScaler after ILR / standardization.
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
            raise ValueError(f"pseudocount must be > 0, got {self.pseudocount}")

    def _close(self, X):
        row_sums = np.sum(X, axis=1, keepdims=True)
        if np.any(row_sums <= 0):
            raise ValueError("Each row must have positive sum to form a composition.")
        return X / row_sums

    def _helmert_submatrix(self, D):
        """
        Returns a (D, D-1) orthonormal basis for the simplex.
        """
        if D < 2:
            raise ValueError("ILR requires at least 2 components.")

        H = np.zeros((D, D - 1), dtype=np.float64)
        for j in range(D - 1):
            H[: j + 1, j] = 1.0 / np.sqrt((j + 1) * (j + 2))
            H[j + 1, j] = -(j + 1) / np.sqrt((j + 1) * (j + 2))
        return H

    def _ilr(self, X):
        logX = np.log(X)
        return logX @ self.basis_

    def _inverse_ilr(self, Z):
        logX = Z @ self.basis_.T
        X = np.exp(logX)
        return self._close(X)

    def fit(self, X, y=None):
        self._validate_params()
        X = self._validate_input(X)

        if np.any(X < 0):
            raise ValueError("ILRTransformer requires non-negative inputs.")

        X = np.clip(X, self.pseudocount, None)
        X = self._close(X)

        self.n_features_in_ = X.shape[1]
        self.basis_ = self._helmert_submatrix(self.n_features_in_)

        X_t = self._ilr(X)

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
            raise ValueError("ILRTransformer requires non-negative inputs.")

        X = np.clip(X, self.pseudocount, None)
        X = self._close(X)
        X_t = self._ilr(X)

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
                f"Expected {expected_dim} ILR coordinates, got {X.shape[1]}"
            )

        if self.normalize:
            X = self.norm_out.inverse_transform(X)

        if self.standardize:
            X = self.std_out.inverse_transform(X)

        X = self._inverse_ilr(X)
        return X
    

# TODO generate residual ingredient (missing fraction column)
# TDOO fit ilr system with ABC-DEF
# TODO add pure DEF observations
# TODO refit regression model in that ilr space