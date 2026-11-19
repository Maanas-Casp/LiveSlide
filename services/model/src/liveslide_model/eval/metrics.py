from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score


def _ratio(numerator: float, denominator: float):
    return float(numerator / denominator) if denominator else None


def binary_metrics(labels, probabilities, threshold: float = 0.5, bins: int = 10) -> dict:
    y = np.asarray(labels, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    if y.shape != p.shape or y.ndim != 1:
        raise ValueError("labels and probabilities must be same-length vectors")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("labels must be binary and probabilities finite in [0, 1]")
    predicted = p >= threshold
    hit = int(((y == 1) & predicted).sum())
    miss = int(((y == 1) & ~predicted).sum())
    false_alarm = int(((y == 0) & predicted).sum())
    correct_negative = int(((y == 0) & ~predicted).sum())
    hss_den = ((hit + miss) * (miss + correct_negative)
               + (hit + false_alarm) * (false_alarm + correct_negative))
    ece = 0.0
    edges = np.linspace(0, 1, bins + 1)
    for index in range(bins):
        mask = (p >= edges[index]) & ((p < edges[index + 1]) if index < bins - 1 else (p <= 1))
        if mask.any():
            ece += float(mask.mean() * abs(p[mask].mean() - y[mask].mean()))
    return {
        "pod": _ratio(hit, hit + miss),
        "far": _ratio(false_alarm, hit + false_alarm),
        "csi": _ratio(hit, hit + miss + false_alarm),
        "hss": _ratio(2 * (hit * correct_negative - miss * false_alarm), hss_den),
        "pr_auc": float(average_precision_score(y, p)) if len(np.unique(y)) > 1 else None,
        "brier": float(np.mean((p - y) ** 2)) if len(y) else None,
        "ece": ece if len(y) else None,
        "counts": {"hits": hit, "misses": miss, "false_alarms": false_alarm,
                   "correct_negatives": correct_negative},
    }
