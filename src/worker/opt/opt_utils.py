from __future__ import annotations

import numpy as np


def pdist(x: np.ndarray, metric: str = "euclidean") -> np.ndarray:
    """
    Pairwise Euclidean distances for rows in x (condensed form).
    Mirrors scipy.spatial.distance.pdist for metric='euclidean'.
    """
    if metric != "euclidean":
        raise ValueError(f"Unsupported metric '{metric}' for pdist.")
    x = np.asarray(x, dtype=float)
    n = x.shape[0]
    if n < 2:
        return np.array([], dtype=float)

    # Compute condensed distance matrix.
    dists = np.empty(n * (n - 1) // 2, dtype=float)
    k = 0
    for i in range(n - 1):
        diff = x[i + 1 :] - x[i]
        d = np.sqrt(np.sum(diff * diff, axis=1))
        dists[k : k + d.size] = d
        k += d.size
    return dists


def cdist(xa: np.ndarray, xb: np.ndarray, metric: str = "euclidean") -> np.ndarray:
    """
    Cross Euclidean distances between rows of xa and xb.
    Mirrors scipy.spatial.distance.cdist for metric='euclidean'.
    """
    if metric != "euclidean":
        raise ValueError(f"Unsupported metric '{metric}' for cdist.")
    xa = np.asarray(xa, dtype=float)
    xb = np.asarray(xb, dtype=float)
    if xa.size == 0 or xb.size == 0:
        return np.empty((xa.shape[0], xb.shape[0]), dtype=float)

    # (n,1,d) - (1,m,d) -> (n,m,d)
    diff = xa[:, None, :] - xb[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))
