import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.base import TransformerMixin, BaseEstimator


class LogTransformer(BaseEstimator, TransformerMixin):
    """
    Transforms the target variable by decadic logarithm.
    Has built-in standardization / normalization for machine learning.
    Parameters:
    - standardize: bool, set true if you apply gaussian process regression.
    """
    def __init__(self, standardize: bool = True, normalize: bool = False):
        self.std_out = StandardScaler()
        self.norm_out = MinMaxScaler()
        self.standardize = standardize
        self.normalize = normalize

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=np.float64)
        X = np.log1p(X)
        if self.standardize:
            self.std_out.fit(X)
        if self.normalize:
            self.norm_out.fit(X)
        return self

    def transform(self, X, y=None):
        X = np.asarray(X, dtype=np.float64)
        X = np.log1p(X)
        if self.standardize:
            X = self.std_out.transform(X)
        if self.normalize:
            X = self.norm_out.transform(X)
        return X

    def inverse_transform(self, X, y=None):
        if self.standardize:
            X = self.std_out.inverse_transform(X)
        if self.normalize:
            X = self.norm_out.inverse_transform(X)
        X = np.expm1(X)
        return X