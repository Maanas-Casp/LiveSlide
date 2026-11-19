from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .bootstrap import block_bootstrap
from .cv import grouped_folds, temporal_holdout
from .metrics import binary_metrics

DYNAMIC_FEATURES = ["rain_1d", "rain_3d", "rain_7d", "rain_20d", "soil_moisture"]
STATIC_FEATURES = ["elevation_m", "slope_deg", "curvature", "twi"]


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _train_predict(train, test, features, seed):
    from ..models.gbm import build_model, tune_model

    y = train["label"].astype(int)
    if y.nunique() < 2:
        return np.full(len(test), float(y.iloc[0]) if len(y) else 0.0), None
    model = build_model("v1" if any(name in STATIC_FEATURES for name in features) else "v0",
                        seed=seed, positives=int(y.sum()), negatives=int((y == 0).sum()))
    model, _ = tune_model(model, train[features], y, train["block_id"])
    return model.predict_proba(test[features])[:, 1], model


def evaluate_table(frame: pd.DataFrame, config: dict, *, output_root: str | Path,
                   config_path: str | Path) -> dict:
    required = {"label", "block_id", "ts", *DYNAMIC_FEATURES}
    missing = required - set(frame)
    if missing:
        raise ValueError(f"Feature table lacks columns: {', '.join(sorted(missing))}")
    if frame["label"].nunique() < 2:
        raise ValueError("Evaluation requires positive and negative labels")
    frame = frame.dropna(subset=DYNAMIC_FEATURES + ["label", "block_id", "ts"]).copy()
    seed = int(config["random_seed"])
    records = []
    for version, features in (("v0", DYNAMIC_FEATURES),
                              ("v1", DYNAMIC_FEATURES + STATIC_FEATURES)):
        features = [name for name in features if name in frame]
        if version == "v1" and len(features) == len(DYNAMIC_FEATURES):
            continue
        oof = np.full(len(frame), np.nan)
        for train_idx, test_idx in grouped_folds(frame["block_id"], n_splits=5):
            train, test = frame.iloc[train_idx], frame.iloc[test_idx]
            probabilities, _ = _train_predict(train, test, features, seed)
            oof[test_idx] = probabilities
        valid = np.isfinite(oof)
        metrics = binary_metrics(frame.loc[valid, "label"], oof[valid])
        intervals = block_bootstrap(frame.loc[valid, "label"], oof[valid],
                                    frame.loc[valid, "block_id"], binary_metrics, seed=seed)
        records.append({"method": version, "scheme": "block CV", "metrics": metrics,
                        "intervals_95": intervals})
        if "final_season_start" in config:
            train_idx, test_idx = temporal_holdout(frame["ts"], config["final_season_start"])
            probabilities, _ = _train_predict(frame.iloc[train_idx], frame.iloc[test_idx], features, seed)
            holdout = binary_metrics(frame.iloc[test_idx]["label"], probabilities)
            holdout_intervals = block_bootstrap(frame.iloc[test_idx]["label"], probabilities,
                                                frame.iloc[test_idx]["block_id"], binary_metrics, seed=seed)
            records.append({"method": version, "scheme": "temporal holdout", "metrics": holdout,
                            "intervals_95": holdout_intervals})

    for method, columns in (
        ("intensity-duration threshold", {
            "block CV": "id_threshold_cv_oof",
            "temporal holdout": "id_threshold_temporal_holdout",
        }),
        ("LHASA", {"block CV": "lhasa_risk", "temporal holdout": "lhasa_risk"}),
    ):
        for scheme, column in columns.items():
            if column not in frame or frame[column].isna().all():
                reason = ("fold-safe threshold predictions have not been constructed"
                          if method.startswith("intensity") else
                          "matching LHASA values are unavailable for this table's region and dates")
                records.append({"method": method, "scheme": scheme, "status": "unavailable",
                                "reason": reason, "metrics": None, "intervals_95": None})
                continue
            subset = frame.dropna(subset=[column, "label", "block_id"])
            if scheme == "temporal holdout":
                _, test_idx = temporal_holdout(frame["ts"], config["final_season_start"])
                subset = frame.iloc[test_idx].dropna(subset=[column, "label", "block_id"])
            predictions = subset[column]
            if method.startswith("intensity"):
                predictions = predictions.astype(float)
            scores = binary_metrics(subset["label"], predictions)
            intervals = block_bootstrap(subset["label"], predictions, subset["block_id"],
                                        binary_metrics, seed=seed)
            records.append({"method": method, "scheme": scheme, "metrics": scores,
                            "intervals_95": intervals})

    data_path = Path(__file__).resolve().parents[5] / "data/processed/features.parquet"
    digest = _sha256(data_path) if data_path.exists() else "unavailable"
    commit = _git_commit()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=False)
    payload = {"run_id": run_id, "synthetic": bool(config.get("synthetic", False)),
               "seed": seed, "data_hash": digest, "git_commit": commit,
               "config": config, "results": records}
    (output / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output / "config.yaml").write_text(Path(config_path).read_text(encoding="utf-8"), encoding="utf-8")
    return payload


def print_metrics_table(payload: dict) -> None:
    columns = ("POD", "FAR", "CSI", "HSS", "PR-AUC", "Brier", "ECE")
    print(f"{'method':32} {'scheme':20} " + " ".join(f"{name:>23}" for name in columns))
    for row in payload["results"]:
        if row.get("status") == "unavailable":
            print(f"{row['method']:32} {row['scheme']:20} unavailable: {row['reason']}")
            continue
        metrics = row["metrics"]
        intervals = row.get("intervals_95") or {}
        values = []
        for name in columns:
            key = name.lower().replace('-', '_')
            value = metrics.get(key)
            ci = intervals.get(key)
            if isinstance(value, (float, int)) and ci and ci[0] is not None:
                values.append(f"{value:.3f} [{ci[0]:.3f},{ci[1]:.3f}]")
            elif isinstance(value, (float, int)):
                values.append(f"{value:.3f} [n/a]")
            else:
                values.append("n/a")
        print(f"{row['method']:32} {row['scheme']:20} " + " ".join(
            f"{value:>23}" for value in values
        ))
