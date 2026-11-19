from __future__ import annotations

import numpy as np
from sklearn.model_selection import GroupKFold


def grouped_folds(groups, n_splits: int = 5):
    """Yield train/test row indexes with whole spatial groups held together."""
    groups = np.asarray(groups)
    if len(np.unique(groups)) < n_splits:
        raise ValueError(f"Need at least {n_splits} distinct blocks")
    splitter = GroupKFold(n_splits=n_splits)
    placeholder = np.zeros((len(groups), 1))
    for train, test in splitter.split(placeholder, groups=groups):
        if set(groups[train]) & set(groups[test]):
            raise AssertionError("Spatial block leakage in grouped fold")
        yield train, test


def temporal_holdout(timestamps, final_season_start: str):
    """Split rows by prediction timestamp, with the final season reserved for test."""
    import pandas as pd

    times = pd.to_datetime(timestamps, utc=True)
    cutoff = pd.Timestamp(final_season_start, tz="UTC")
    train = np.flatnonzero(times < cutoff)
    test = np.flatnonzero(times >= cutoff)
    if not len(train) or not len(test):
        raise ValueError("Temporal split needs rows on both sides of final_season_start")
    return train, test
