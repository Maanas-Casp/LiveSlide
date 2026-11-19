from __future__ import annotations

from typing import Protocol


class Calibrator(Protocol):
    def fit(self, scores, labels, groups) -> "Calibrator": ...
    def predict_set(self, score: float) -> set[str]: ...


class ThresholdCalibrator:
    """No-op placeholder; returns a binary label using a fixed 0.5 threshold."""

    def fit(self, scores, labels, groups) -> "ThresholdCalibrator":
        return self

    def predict_set(self, score: float) -> set[str]:
        return {"event" if score >= 0.5 else "no_event"}
