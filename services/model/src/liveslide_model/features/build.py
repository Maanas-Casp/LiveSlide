from __future__ import annotations

import pandas as pd
import numpy as np
import hashlib
import json
from pathlib import Path

RAIN_COLUMNS = ("rain_1d", "rain_3d", "rain_7d", "rain_20d")


def build_daily_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Build cell-day features using observations no later than each row's date."""
    required = {"cell_id", "ts", "rain_mm"}
    missing = required - set(daily.columns)
    if missing:
        raise ValueError(f"Missing input columns: {', '.join(sorted(missing))}")
    frame = daily.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values(["cell_id", "ts"], kind="stable")
    if frame.duplicated(["cell_id", "ts"]).any():
        raise ValueError("Input must have at most one rainfall row per cell and timestamp")
    for _, rows in frame.groupby("cell_id", sort=False):
        intervals = rows["ts"].diff().dropna()
        if not intervals.eq(pd.Timedelta(days=1)).all():
            raise ValueError("Rainfall input must have one row per cell for every consecutive day")
    for days, name in ((1, "rain_1d"), (3, "rain_3d"), (7, "rain_7d"), (20, "rain_20d")):
        frame[name] = frame.groupby("cell_id", sort=False)["rain_mm"].transform(
            lambda values: values.rolling(days, min_periods=days).sum()
        )
    frame["source_max_ts"] = frame["ts"]
    assert_no_future_features(frame)
    if "soil_moisture" not in frame:
        frame["soil_moisture"] = pd.NA
    return frame


def assert_no_future_features(frame: pd.DataFrame, source_max_ts: str = "source_max_ts") -> None:
    """Reject feature rows whose source timestamp is after their prediction timestamp."""
    if source_max_ts not in frame:
        raise ValueError(f"Missing leakage audit column: {source_max_ts}")
    prediction = pd.to_datetime(frame["ts"], utc=True)
    source = pd.to_datetime(frame[source_max_ts], utc=True)
    leaked = source > prediction
    if leaked.any():
        bad_rows = frame.index[leaked].tolist()[:5]
        raise ValueError(f"Future data leakage at row indexes: {bad_rows}")


def write_feature_parquet(frame: pd.DataFrame, output_path: str | Path,
                          source_paths: list[str | Path], config: dict) -> str:
    """Write a Parquet table with a reproducible hash of input data and config metadata."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Install pyarrow to write the model feature table") from exc
    digest = hashlib.sha256()
    digest.update(json.dumps(config, sort_keys=True, separators=(",", ":")).encode())
    for source in sorted(map(Path, source_paths), key=lambda item: str(item)):
        digest.update(str(source.name).encode())
        digest.update(hashlib.sha256(source.read_bytes()).digest())
    version_hash = digest.hexdigest()
    table = pa.Table.from_pandas(frame, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    metadata[b"liveslide.data_version_hash"] = version_hash.encode()
    metadata[b"liveslide.synthetic"] = str(bool(config.get("synthetic", False))).lower().encode()
    pq.write_table(table.replace_schema_metadata(metadata), output_path)
    return version_hash


def label_cell_days(features: pd.DataFrame, cells: pd.DataFrame, events: pd.DataFrame,
                    *, buffer_m: float, window_days: int, negative_ratio: int,
                    seed: int) -> pd.DataFrame:
    """Label cell-days from future events and sample far-from-event negatives by month.

    Cells must provide min/max lon/lat bounds. Events need event_date, latitude, longitude.
    Distance to the cell rectangle is approximated with a local equirectangular projection.
    """
    cell_columns = {"cell_id", "min_lon", "min_lat", "max_lon", "max_lat"}
    event_columns = {"event_date", "latitude", "longitude"}
    if cell_columns - set(cells) or event_columns - set(events):
        raise ValueError("cells or events lack the required geometry/date columns")
    event_frame = events.copy()
    event_frame["event_date"] = pd.to_datetime(event_frame["event_date"], utc=True)
    event_rows = event_frame.to_dict("records")
    cell_bounds = cells.set_index("cell_id").to_dict("index")
    close_event_dates = {}
    for cell_id, bounds in cell_bounds.items():
        centre_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
        dates = []
        for event in event_rows:
            lat = float(event["latitude"])
            lon = float(event["longitude"])
            dx = max(bounds["min_lon"] - lon, 0.0, lon - bounds["max_lon"])
            dy = max(bounds["min_lat"] - lat, 0.0, lat - bounds["max_lat"])
            distance_m = np.hypot(dx * np.cos(np.radians(centre_lat)) * 111_320,
                                  dy * 111_320)
            if distance_m <= buffer_m:
                dates.append(event["event_date"])
        close_event_dates[cell_id] = dates
    frame = features.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    labels = []
    for row in frame.to_dict("records"):
        bounds = cell_bounds.get(row["cell_id"])
        if bounds is None:
            raise ValueError(f"No cell geometry for {row['cell_id']}")
        close_events = close_event_dates[row["cell_id"]]
        prediction_time = row["ts"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        future = [date for date in close_events
                  if prediction_time < date <= prediction_time + pd.Timedelta(days=window_days)]
        recent = [date for date in close_events
                  if abs((prediction_time - date).total_seconds()) <= 3 * 24 * 60 * 60]
        labels.append(1 if future else 0 if not recent else None)
    frame["label"] = labels
    frame = frame[frame["label"].notna()].copy()
    positives = frame[frame["label"] == 1]
    negatives = frame[frame["label"] == 0]
    rng = np.random.default_rng(seed)
    selected_negative_indexes = []
    positives["month"] = positives["ts"].dt.month
    negatives["month"] = negatives["ts"].dt.month
    for month, positive_group in positives.groupby("month"):
        candidates = negatives[negatives["month"] == month]
        take = min(len(candidates), len(positive_group) * negative_ratio)
        if take:
            selected_negative_indexes.extend(
                rng.choice(candidates.index.to_numpy(), size=take, replace=False).tolist()
            )
    sampled = pd.concat([positives, negatives.loc[selected_negative_indexes]], ignore_index=True)
    return sampled.drop(columns="month", errors="ignore").sort_values(["cell_id", "ts"])
