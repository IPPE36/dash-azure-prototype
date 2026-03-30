from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt


def plot_pca_cumulative_variance(
    explained_variance_ratio: np.ndarray = None,
    *,
    pca: object = None,
    ax: plt.Axes = None,
    title: str = "PCA Cumulative Explained Variance",
    show: bool = True,
    filepath: str = None,
):
    """
    Plot cumulative explained variance over PCA components.

    Provide either explained_variance_ratio directly or a fitted PCA-like object
    with an explained_variance_ratio_ attribute.
    """
    if explained_variance_ratio is None:
        if pca is None or not hasattr(pca, "explained_variance_ratio_"):
            raise ValueError("Provide explained_variance_ratio or a fitted PCA object.")
        explained_variance_ratio = np.asarray(pca.explained_variance_ratio_, dtype=float)
    else:
        explained_variance_ratio = np.asarray(explained_variance_ratio, dtype=float)

    if explained_variance_ratio.ndim != 1:
        raise ValueError("explained_variance_ratio must be a 1D array.")

    cumulative = np.cumsum(explained_variance_ratio)
    cumulative = np.concatenate(([0.0], cumulative))
    components = np.arange(0, len(cumulative))

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    else:
        fig = ax.figure

    ax.plot(components, cumulative, marker=".", linewidth=1.5)
    ax.set_ylim(0.0, 1.05)
    ax.set_xlim(0, len(components) - 1)
    ax.grid(True, alpha=0.2, linewidth=0.6)
    ax.set_xlabel("Number of Components")
    ax.set_ylabel("Cumulative Explained Variance")
    ax.set_title(title)

    if show or filepath is not None:
        plt.tight_layout()
    if filepath is not None:
        fig.savefig(filepath, bbox_inches="tight")
    if show:
        plt.show()

    return fig, ax


def plot_pca_loadings(
    loadings: np.ndarray = None,
    *,
    pca: object = None,
    feature_names: list[str] = None,
    component_labels: list[str] = None,
    ax: plt.Axes = None,
    cmap: str = "viridis",
    show: bool = True,
    colorbar: bool = True,
    filepath: str = None,
):
    """
    Plot PCA loadings as a heatmap (features on y, components on x).

    Provide either `loadings` directly (shape: n_features x n_components) or a
    fitted PCA-like object with `components_` and `explained_variance_`.
    The PCA-derived loadings are computed as components_.T * sqrt(explained_variance_),
    which corresponds to correlations for standardized inputs.
    """
    if loadings is None:
        if (
            pca is None
            or not hasattr(pca, "components_")
            or not hasattr(pca, "explained_variance_")
        ):
            raise ValueError("Provide loadings or a fitted PCA object with components_.")
        components = np.asarray(pca.components_, dtype=float)
        explained_variance = np.asarray(pca.explained_variance_, dtype=float)
        loadings = components.T * np.sqrt(explained_variance)
    else:
        loadings = np.asarray(loadings, dtype=float)

    if loadings.ndim != 2:
        raise ValueError("loadings must be a 2D array (n_features x n_components).")

    n_features, n_components = loadings.shape
    feature_labels = feature_names or [f"x{i}" for i in range(n_features)]
    component_labels = component_labels or [f"PC{i+1}" for i in range(n_components)]

    if len(feature_labels) != n_features:
        raise ValueError("feature_names length must match number of features.")
    if len(component_labels) != n_components:
        raise ValueError("component_labels length must match number of components.")

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(1 + 0.6 * n_components, 1 + 0.35 * n_features))
    else:
        fig = ax.figure

    max_abs = np.nanmax(np.abs(loadings)) if loadings.size else 1.0
    im = ax.imshow(loadings, aspect="auto", cmap=cmap, vmin=-max_abs, vmax=max_abs)
    ax.set_xticks(np.arange(n_components))
    ax.set_yticks(np.arange(n_features))
    ax.set_xticklabels(component_labels, rotation=0)
    ax.set_yticklabels(feature_labels)
    ax.set_xlabel("Components")
    ax.set_ylabel("Features")
    ax.set_title("PCA Loadings")

    if colorbar:
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    if show or filepath is not None:
        plt.tight_layout()
    if filepath is not None:
        fig.savefig(filepath, bbox_inches="tight")
    if show:
        plt.show()

    return fig, ax


def plot_true_vs_predicted(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    y_std: np.ndarray = None,
    y_true_test: np.ndarray = None,
    y_pred_test: np.ndarray = None,
    y_std_test: np.ndarray = None,
    target_cols: list[str] = None,
    show_std: bool = True,
    show: bool = True,
    filepath: str = None,
):
    """
    Plot true vs predicted scatter for each target.
    If y_std is provided and show_std is True, plot error bars.
    """
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)
    if y_true_test is not None and y_true_test.ndim == 1:
        y_true_test = y_true_test.reshape(-1, 1)
    if y_pred_test is not None and y_pred_test.ndim == 1:
        y_pred_test = y_pred_test.reshape(-1, 1)

    n_targets = y_true.shape[1]
    labels = target_cols or [f"y{i}" for i in range(n_targets)]

    fig, axes = plt.subplots(1, n_targets, figsize=(4 * n_targets, 4), squeeze=False)

    for idx, ax in enumerate(axes[0]):
        true_vals = y_true[:, idx]
        pred_vals = y_pred[:, idx]
        vmin = min(true_vals.min(), pred_vals.min())
        vmax = max(true_vals.max(), pred_vals.max())

        if y_std is not None and show_std:
            std_vals = y_std[:, idx]
            ax.errorbar(
                true_vals,
                pred_vals,
                yerr=std_vals,
                fmt="none",
                ecolor="black",
                alpha=0.3,
                elinewidth=1.0,
                capsize=0,
            )
            ax.scatter(
                true_vals,
                pred_vals,
                alpha=0.66,
                color="black",
                label="Train",
                marker=".",
            )
        else:
            ax.scatter(
                true_vals,
                pred_vals,
                alpha=0.66,
                color="black",
                label="Train",
                marker=".",
            )

        if y_true_test is not None and y_pred_test is not None:
            true_vals_test = y_true_test[:, idx]
            pred_vals_test = y_pred_test[:, idx]
            vmin = min(vmin, true_vals_test.min(), pred_vals_test.min())
            vmax = max(vmax, true_vals_test.max(), pred_vals_test.max())

            if y_std_test is not None and show_std:
                std_vals_test = y_std_test[:, idx]
                ax.errorbar(
                    true_vals_test,
                    pred_vals_test,
                    yerr=std_vals_test,
                    fmt="none",
                    ecolor="red",
                    alpha=0.3,
                    elinewidth=1.0,
                    capsize=0,
                )
                ax.scatter(
                    true_vals_test,
                    pred_vals_test,
                    alpha=0.66,
                    color="red",
                    label="Test",
                    marker=".",
                )
            else:
                ax.scatter(
                    true_vals_test,
                    pred_vals_test,
                    alpha=0.66,
                    color="red",
                    label="Test",
                    marker=".",
                )

        ax.plot(
            [vmin, vmax],
            [vmin, vmax],
            linestyle="--",
            linewidth=1.0,
            color="black",
            alpha=0.66,
            marker="."
        )
        ax.set_xlim(vmin, vmax)
        ax.set_ylim(vmin, vmax)
        ax.grid(True, alpha=0.5, linewidth=0.6)
        ax.set_xlabel("True")
        ax.set_ylabel("Predicted")
        ax.set_title(f"True vs Predicted ({labels[idx]})")
        if y_true_test is not None and y_pred_test is not None:
            ax.legend(frameon=False)

    if show or filepath is not None:
        plt.tight_layout()
    if filepath is not None:
        fig.savefig(filepath, bbox_inches="tight")
    if show:
        plt.show()

    return fig, axes
