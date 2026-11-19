from __future__ import annotations

import pandas as pd
import json
from pathlib import Path
import math


def read_inventory(path: str, bbox: tuple[float, float, float, float], start_date: str,
                   end_date: str, *, spatial_buffer_m: float = 0,
                   temporal_lookahead_days: int = 0) -> tuple[pd.DataFrame, dict]:
    """Read a placed inventory CSV, retaining the spatial/temporal label halo."""
    frame = pd.read_csv(path)
    required = {"event_date", "latitude", "longitude", "source"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Inventory missing columns: {', '.join(sorted(missing))}")
    original = len(frame)
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce", utc=True)
    min_lon, min_lat, max_lon, max_lat = bbox
    centre_lat = (min_lat + max_lat) / 2
    lat_pad = spatial_buffer_m / 111_320
    lon_pad = spatial_buffer_m / (111_320 * math.cos(math.radians(centre_lat)))
    start = pd.Timestamp(start_date, tz="UTC")
    end = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=temporal_lookahead_days)
    scoped = frame[
        frame["event_date"].between(start, end)
        & frame["longitude"].between(min_lon - lon_pad, max_lon + lon_pad)
        & frame["latitude"].between(min_lat - lat_pad, max_lat + lat_pad)
    ].copy()
    if "location_accuracy_m" not in scoped:
        scoped["location_accuracy_m"] = pd.NA
    before_dedup = len(scoped)
    scoped = scoped.drop_duplicates(["event_date", "latitude", "longitude"])
    return scoped, {"input_rows": original, "out_of_scope_or_invalid": original - before_dedup,
                    "exact_duplicates": before_dedup - len(scoped), "retained": len(scoped)}


def write_events_geojson(events: pd.DataFrame, path: str | Path) -> None:
    """Export retained inventory events for the API's events import-layer command."""
    features = []
    for row in events.to_dict("records"):
        properties = {key: (value.isoformat() if hasattr(value, "isoformat") else value)
                      for key, value in row.items() if key not in {"latitude", "longitude"}}
        features.append({"type": "Feature", "properties": properties,
                         "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]}})
    collection = {"type": "FeatureCollection", "name": "landslide_events", "features": features}
    Path(path).write_text(json.dumps(collection, default=str), encoding="utf-8")
