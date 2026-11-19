from __future__ import annotations

import numpy as np


def block_bootstrap(labels, probabilities, groups, metric, n_resamples: int = 1000, seed: int = 26001):
    """Resample complete spatial blocks and return percentile intervals per metric."""
    y = np.asarray(labels)
    p = np.asarray(probabilities)
    g = np.asarray(groups)
    unique = np.unique(g)
    if not len(unique):
        raise ValueError("At least one block is required")
    rng = np.random.default_rng(seed)
    sampled = {key: [] for key, value in metric(y, p).items() if isinstance(value, (int, float))}
    for _ in range(n_resamples):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        indexes = np.concatenate([np.flatnonzero(g == key) for key in chosen])
        values = metric(y[indexes], p[indexes])
        for key in sampled:
            if values[key] is not None:
                sampled[key].append(values[key])
    return {key: (list(np.percentile(values, [2.5, 97.5])) if values else [None, None])
            for key, values in sampled.items()}
