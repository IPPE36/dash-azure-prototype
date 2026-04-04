from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def plot_pca_cumulative_variance(
    explained_variance_ratio: np.ndarray = None,
    *,
    pca: object = None,
    ax: plt.Axes = None,
    title: str = "Explained Variance",
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

    plt.tight_layout()
    if filepath is not None:
        fig.savefig(filepath, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()
    return


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

    plt.tight_layout()
    if filepath is not None:
        fig.savefig(filepath)
    if show:
        plt.show()
    plt.close()
    return


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
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)

    if y_std is not None:
        y_std = np.asarray(y_std, dtype=float)
        if y_std.ndim == 1:
            y_std = y_std.reshape(-1, 1)

    if y_true_test is not None:
        y_true_test = np.asarray(y_true_test, dtype=float)
        if y_true_test.ndim == 1:
            y_true_test = y_true_test.reshape(-1, 1)

    if y_pred_test is not None:
        y_pred_test = np.asarray(y_pred_test, dtype=float)
        if y_pred_test.ndim == 1:
            y_pred_test = y_pred_test.reshape(-1, 1)

    if y_std_test is not None:
        y_std_test = np.asarray(y_std_test, dtype=float)
        if y_std_test.ndim == 1:
            y_std_test = y_std_test.reshape(-1, 1)

    n_targets = y_true.shape[1]
    labels = target_cols or [f"y{i}" for i in range(n_targets)]
    filepath = Path(filepath) if filepath is not None else None

    for idx in range(n_targets):
        fig, ax = plt.subplots(figsize=(4, 4))

        plot_vals = []

        # --- TRAIN ---
        true_vals = y_true[:, idx]
        pred_vals = y_pred[:, idx]

        train_mask = ~np.isnan(true_vals) & ~np.isnan(pred_vals)
        true_plot = true_vals[train_mask]
        pred_plot = pred_vals[train_mask]

        if true_plot.size > 0:
            if y_std is not None and show_std:
                std_vals = y_std[:, idx]
                err_mask = train_mask & ~np.isnan(std_vals)
                ax.errorbar(
                    true_vals[err_mask],
                    pred_vals[err_mask],
                    yerr=std_vals[err_mask],
                    fmt="none",
                    ecolor="black",
                    alpha=0.3,
                    elinewidth=1.0,
                    capsize=0,
                )

            ax.scatter(
                true_plot,
                pred_plot,
                alpha=0.66,
                color="black",
                label="Train",
                marker=".",
            )
            plot_vals.extend([true_plot, pred_plot])

        # --- TEST ---
        has_test = y_true_test is not None and y_pred_test is not None
        if has_test:
            true_vals_test = y_true_test[:, idx]
            pred_vals_test = y_pred_test[:, idx]

            test_mask = ~np.isnan(true_vals_test) & ~np.isnan(pred_vals_test)
            true_plot_test = true_vals_test[test_mask]
            pred_plot_test = pred_vals_test[test_mask]

            if true_plot_test.size > 0:
                if y_std_test is not None and show_std:
                    std_vals_test = y_std_test[:, idx]
                    err_mask_test = test_mask & ~np.isnan(std_vals_test)
                    ax.errorbar(
                        true_vals_test[err_mask_test],
                        pred_vals_test[err_mask_test],
                        yerr=std_vals_test[err_mask_test],
                        fmt="none",
                        ecolor="red",
                        alpha=0.3,
                        elinewidth=1.0,
                        capsize=0,
                    )

                ax.scatter(
                    true_plot_test,
                    pred_plot_test,
                    alpha=0.66,
                    color="red",
                    label="Test",
                    marker=".",
                )
                plot_vals.extend([true_plot_test, pred_plot_test])

        # --- LIMITS / DIAGONAL ---
        if plot_vals:
            all_vals = np.concatenate(plot_vals)
            vmin = np.nanmin(all_vals)
            vmax = np.nanmax(all_vals)

            if np.isfinite(vmin) and np.isfinite(vmax):
                if vmin == vmax:
                    pad = 1.0 if vmin == 0 else abs(vmin) * 0.05
                    vmin -= pad
                    vmax += pad

                ax.plot(
                    [vmin, vmax],
                    [vmin, vmax],
                    linestyle="--",
                    linewidth=1.0,
                    color="black",
                    alpha=0.66,
                )
                ax.set_xlim(vmin, vmax)
                ax.set_ylim(vmin, vmax)
        else:
            ax.text(
                0.5, 0.5, "No valid rows",
                ha="center", va="center",
                transform=ax.transAxes,
            )

        ax.grid(True, alpha=0.5, linewidth=0.6)
        ax.set_xlabel("True")
        ax.set_ylabel("Predicted")
        ax.set_title(f"{labels[idx]}")

        if has_test:
            ax.legend(frameon=False)

        plt.tight_layout()
        if filepath is not None:
            out_path = filepath.with_name(
                f"{filepath.stem}_{labels[idx]}{filepath.suffix}"
            )
            fig.savefig(out_path, bbox_inches="tight")
        if show:
            plt.show()
        plt.close()

    return


def plot_scaler_hist(
    scaler,
    y_train: np.ndarray,
    y_test: np.ndarray,
    target_cols: list[str] = None,
    show: bool = True,
    filepath: str = None,
):
    if y_train.ndim == 1:
        y_train = y_train.reshape(-1, 1)
    if y_test.ndim == 1:
        y_test = y_test.reshape(-1, 1)

    if y_train.shape[1] != y_test.shape[1]:
        raise ValueError("y_train and y_test must have the same number of columns")

    n_targets = y_train.shape[1]
    labels = target_cols or [f"y{i}" for i in range(n_targets)]

    filepath = Path(filepath) if filepath is not None else None

    for idx in range(n_targets):
        fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2, figsize=(10, 4))

        y_train_col = y_train[:, idx].copy().reshape(-1, 1)
        y_test_col = y_test[:, idx].copy().reshape(-1, 1)

        # left: unscaled
        ax1.hist(y_train_col.squeeze(), label="train unscaled", alpha=0.7)
        ax1.hist(y_test_col.squeeze(), label="test unscaled", alpha=0.7)

        # fit separate scaler instance per column
        scaler_local = scaler.__class__(**scaler.get_params())
        y_train_scaled = scaler_local.fit_transform(y_train_col).squeeze()
        y_test_scaled = scaler_local.transform(y_test_col).squeeze()

        # right: scaled
        ax2.hist(y_train_scaled, label="train scaled", alpha=0.7)
        ax2.hist(y_test_scaled, label="test scaled", alpha=0.7)

        ax1.set_title(f"Unscaled ({labels[idx]})")
        ax2.set_title(f"Scaled ({labels[idx]})")

        ax1.grid(color="gray", linestyle="--", linewidth=0.5)
        ax2.grid(color="gray", linestyle="--", linewidth=0.5)
        ax1.legend()
        ax2.legend()

        plt.tight_layout()
        if filepath is not None:
            filepath = Path(filepath)
            out_path = filepath.with_name(
                f"{filepath.stem}_{labels[idx]}{filepath.suffix}"
            )
            fig.savefig(out_path, bbox_inches="tight")
        if show:
            plt.show()
        plt.close()
    return 


def plot_pareto_front(
    y1,
    y2,
    *,
    gen_indices: list[int] | set[int] | None = None,
    target_x: float | None = None,
    target_y: float | None = None,
    ax: plt.Axes = None,
    title: str = "Pareto Front",
    show: bool = True,
    filepath: str = None,
):
    """
    Plot Pareto front traces for selected generations.

    Parameters
    ----------
    y1, y2:
        Either list-like of per-generation arrays, or 2D arrays shaped
        (n_generations, n_points). If 1D, treated as a single generation.
    gen_indices:
        Optional generation indices to display. Defaults to 3 evenly spaced
        indices (e.g. 0, mid, last).
    target_x, target_y:
        Optional target values to display as crosshair.
    """
    def _is_list_like(obj):
        return isinstance(obj, (list, tuple))

    if _is_list_like(y1) and _is_list_like(y2):
        # List-like per-generation data (possibly ragged)
        y1_gens = [np.asarray(v, dtype=float) for v in y1]
        y2_gens = [np.asarray(v, dtype=float) for v in y2]
    else:
        y1 = np.asarray(y1, dtype=float)
        y2 = np.asarray(y2, dtype=float)

        if y1.ndim == 1 and y2.ndim == 1:
            y1_gens = [y1]
            y2_gens = [y2]
        elif y1.ndim == 2 and y2.ndim == 2:
            if y1.shape[0] != y2.shape[0]:
                raise ValueError("y1 and y2 must have the same number of generations.")
            y1_gens = [y1[i] for i in range(y1.shape[0])]
            y2_gens = [y2[i] for i in range(y2.shape[0])]
        else:
            raise ValueError("y1 and y2 must be 1D, 2D, or list-like per generation.")

    n_gens = len(y1_gens)
    if n_gens != len(y2_gens):
        raise ValueError("y1 and y2 must have the same number of generations.")
    if n_gens == 0:
        raise ValueError("No generation data provided.")

    if gen_indices is None:
        idx = np.linspace(0, n_gens - 1, 3, dtype=int)
        gen_indices = sorted(set(idx.tolist()))
    else:
        gen_indices = sorted({int(i) for i in gen_indices if 0 <= int(i) < n_gens})
        if not gen_indices:
            raise ValueError("gen_indices resolved to empty after bounds check.")

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    else:
        fig = ax.figure

    for gen in gen_indices:
        ax.scatter(
            y1_gens[gen],
            y2_gens[gen],
            s=18,
            alpha=0.7,
            label=f"Gen {gen}",
        )

    if target_x is not None:
        ax.axvline(target_x, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    if target_y is not None:
        ax.axhline(target_y, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    if target_x is not None and target_y is not None:
        ax.scatter([target_x], [target_y], marker="x", s=60, color="black", zorder=5)

    ax.grid(True, alpha=0.3, linewidth=0.6)
    ax.set_xlabel("y1")
    ax.set_ylabel("y2")
    ax.set_title(title)
    ax.legend(frameon=False)

    plt.tight_layout()
    if filepath is not None:
        fig.savefig(filepath, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()
    return
