from dataclasses import dataclass

import numpy as np


@dataclass
class CompositionalConfig:
    """
    Configuration for compositional feature preparation.
    Attributes
    ----------
    groups:
        Mapping of feature_name -> group_name.
    group_targets:
        Optional mapping of group_name -> target sum. Defaults to 1.0 for all groups.
    jitter_eps:
        Small random jitter added to break ties for strict ordering.
    group_n_select:
        Optional mapping of group_name -> top-n allowed nonzero features for that group.
    n_select:
        Optional global top-n allowed nonzero features across the group.
    mandatory_features:
        Optional list of feature names that must be kept (if present in a group).
    round_to_percent:
        If True, round to 2 decimals via integer percent logic (sums to group target).
    """
    groups: dict[str, str]
    group_targets: dict[str, float] | None = None
    jitter_eps: float = 1e-6
    group_n_select: dict[str, int] | None = None
    n_select: int | None = None
    mandatory_features: list[str] | None = None
    round_to_percent: bool = False


def prepare_compositional_inputs(
    x_full: np.ndarray,
    *,
    features: list[str],
    bounds: dict[str, tuple[float, float]] | None,
    config: CompositionalConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Prepare compositional inputs per group so each group sums to its target (default 1.0).
    """
    if x_full.ndim != 2:
        raise ValueError("x_full must be 2D (n_samples, n_features)")

    bounds = bounds or {}
    group_targets = config.group_targets or {}
    feature_index = {name: idx for idx, name in enumerate(features)}

    groups_to_indices: dict[str, list[int]] = {}
    for feat, group in config.groups.items():
        if feat not in feature_index:
            continue
        groups_to_indices.setdefault(group, []).append(feature_index[feat])

    if not groups_to_indices:
        return x_full

    x_out = np.asarray(x_full, dtype=float).copy()

    for group, idxs in groups_to_indices.items():
        idxs = list(idxs)
        target_sum = float(group_targets.get(group, 1.0))
        x_group = x_out[:, idxs]

        x_group = _to_composition(
            x_group,
            idxs=idxs,
            bounds=bounds,
            features=features,
            group=group,
            target_sum=target_sum,
            rng=rng,
            config=config,
        )
        x_out[:, idxs] = x_group

    return x_out


def _to_composition(
    x_group: np.ndarray,
    *,
    idxs: list[int],
    bounds: dict[str, tuple[float, float]],
    features: list[str],
    group: str,
    target_sum: float,
    rng: np.random.Generator,
    config: CompositionalConfig,
) -> np.ndarray:
    """
    Batch wrapper; heavy per-row logic remains row-wise due to ranking and selection steps.
    """
    out = np.zeros_like(x_group, dtype=float)
    for i in range(x_group.shape[0]):
        out[i] = _to_composition_row(
            x_group[i],
            idxs=idxs,
            bounds=bounds,
            features=features,
            group=group,
            target_sum=target_sum,
            rng=rng,
            config=config,
        )
    return out


def _to_composition_row(
    x: np.ndarray,
    *,
    idxs: list[int],
    bounds: dict[str, tuple[float, float]],
    features: list[str],
    group: str,
    target_sum: float,
    rng: np.random.Generator,
    config: CompositionalConfig,
) -> np.ndarray:
    """
    Translate the provided logic to a single group row, adapted to sum to target_sum.
    """
    x = np.asarray(x, dtype=float).copy()

    # Ensure unique values for strict ordering
    while len(np.unique(x)) != len(x):
        x = x + rng.random(x.size) * config.jitter_eps

    # Optional: top-n per group (group_n_select)
    if config.group_n_select and group in config.group_n_select:
        n = int(config.group_n_select[group])
        if n > 0 and n < x.size:
            cutoff = np.sort(x)[-n]
            x = np.where(x < cutoff, 0.0, x)

    # Mandatory features
    mandatory_idx_local: list[int] = []
    if config.mandatory_features:
        for feat in config.mandatory_features:
            if feat in features:
                feat_idx = features.index(feat)
                if feat_idx in idxs:
                    mandatory_idx_local.append(idxs.index(feat_idx))

    x_man = np.zeros_like(x)
    if mandatory_idx_local:
        x_man[mandatory_idx_local] = x[mandatory_idx_local]
        x[mandatory_idx_local] = 0.0

    # Optional: global top-n selection within group
    if config.n_select:
        n_sel = int(config.n_select)
        if n_sel > 0 and n_sel < x.size:
            cutoff = np.sort(x)[::-1][n_sel - 1]
            x_selection = x.copy()
            x = np.where(x < cutoff, 0.0, x)
        else:
            x_selection = x.copy()
    else:
        x_selection = x.copy()
        x = np.zeros_like(x)

    if mandatory_idx_local:
        x = x + x_man

    # Bounds per feature
    max_ = np.array([
        bounds.get(features[idx], (0.0, 1.0))[1] if x_i != 0 else 0.0
        for idx, x_i in zip(idxs, x)
    ])
    min_ = np.array([
        bounds.get(features[idx], (0.0, 1.0))[0] if x_i != 0 else 0.0
        for idx, x_i in zip(idxs, x)
    ])

    # Scale to bounds
    x = min_ + (max_ - min_) * x

    # Normalize to target sum
    total = x.sum()
    if total > 0:
        x = (x / total) * target_sum

    # Clip to bounds and redistribute
    overshot = np.array([x_i - max_i if x_i > max_i else 0.0 for x_i, max_i in zip(x, max_)])
    undershot = np.array([min_i - x_i if x_i < min_i else 0.0 for x_i, min_i in zip(x, min_)])
    if np.any(overshot + undershot):
        x = np.clip(x, a_min=min_, a_max=max_)
        margin_pos = np.array([max_i - x_i if x_i else 0.0 for x_i, max_i in zip(x, max_)])
        margin_neg = np.array([x_i - min_i if x_i else 0.0 for x_i, min_i in zip(x, min_)])
        if overshot.sum() > 0 and margin_pos.sum() > 0:
            x = x + (margin_pos / margin_pos.sum()) * overshot.sum()
        if undershot.sum() > 0 and margin_neg.sum() > 0:
            x = x - (margin_neg / margin_neg.sum()) * undershot.sum()

    # Add new materials if needed
    if config.n_select:
        n = int(config.n_select)
        if n > 0:
            while x.sum() + 0.01 < target_sum and n < x.size:
                missing = target_sum - x.sum()
                threshold = np.sort(x_selection)[::-1][n]
                candidates = [
                    (idx, x_sel)
                    for idx, x_sel in enumerate(x_selection)
                    if x_sel >= threshold and x[idx] == 0
                ]
                if not candidates:
                    break
                new_idx, _ = min(candidates, key=lambda v: v[1])
                x[new_idx] = min(max_[new_idx], missing)
                n += 1

    # Optional rounding to percent-like values
    if config.round_to_percent:
        scale = 100
        x = np.ceil(x * scale).astype(int)
        while x.sum() < int(target_sum * scale):
            x[np.argmax(x)] += 1
        while x.sum() > int(target_sum * scale):
            x[np.argmax(x)] -= 1
        x = x / scale

    return x
