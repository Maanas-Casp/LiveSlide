from __future__ import annotations

from pathlib import Path

import pandas as pd

from .earthdata import download_collection, record_downloads


def ingest(config: dict, cells: pd.DataFrame, raw_root: str | Path) -> pd.DataFrame:
    """Download SMAP L4 and compute a daily mean root-zone moisture per cell."""
    short_name = config.get("smap_short_name", "SPL4SMGP")
    version = str(config.get("smap_version", "008"))
    files = download_collection(short_name, version, tuple(config["bbox"]),
                                config["start_date"], config["end_date"], Path(raw_root) / "smap")
    record_downloads(files, source=short_name, version=version,
                     start_date=config["start_date"], end_date=config["end_date"])
    return read_daily_cells(files, cells)


def read_daily_cells(files: list[Path], cells: pd.DataFrame) -> pd.DataFrame:
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("Install the optional 'geo' dependencies to read SMAP files") from exc
    required = {"cell_id", "latitude", "longitude"}
    if required - set(cells):
        raise ValueError("cells require cell_id and centroid latitude/longitude")
    output = []
    for path in files:
        dataset = xr.open_dataset(path)
        lon_name = next((name for name in ("longitude", "lon") if name in dataset.coords), None)
        lat_name = next((name for name in ("latitude", "lat") if name in dataset.coords), None)
        x_name = next((name for name in ("x", "EASE2_X") if name in dataset.coords), None)
        y_name = next((name for name in ("y", "EASE2_Y") if name in dataset.coords), None)
        time_name = next((name for name in ("time",) if name in dataset.coords), None)
        variable = next((name for name in ("sm_rootzone", "sm_surface", "soil_moisture")
                         if name in dataset.data_vars), None)
        if not all((time_name, variable)) or not ((lon_name and lat_name) or (x_name and y_name)):
            dataset.close()
            raise ValueError(f"Expected lat/lon/time and an SMAP soil-moisture variable in {path.name}")
        data = dataset[variable]
        transformer = None
        if not (lon_name and lat_name):
            try:
                from pyproj import Transformer
            except ImportError as exc:
                dataset.close()
                raise RuntimeError("Install the optional 'geo' dependencies to map SMAP EASE-Grid coordinates") from exc
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)
        for cell in cells.itertuples(index=False):
            if transformer:
                x, y = transformer.transform(cell.longitude, cell.latitude)
                point = data.sel({x_name: x, y_name: y}, method="nearest")
            else:
                point = data.sel({lon_name: cell.longitude, lat_name: cell.latitude}, method="nearest")
            times = pd.to_datetime(point[time_name].values.reshape(-1), utc=True)
            values = point.values.reshape(-1)
            daily = pd.DataFrame({"ts": times, "soil_moisture": values})
            daily["date"] = daily["ts"].dt.floor("D")
            for date, rows in daily.groupby("date"):
                valid = rows.soil_moisture.dropna()
                output.append({"cell_id": cell.cell_id, "ts": date,
                               "soil_moisture": float(valid.mean()) if len(valid) else float("nan")})
        dataset.close()
    frame = pd.DataFrame(output)
    if frame.empty:
        raise ValueError("No SMAP daily records were produced")
    return (frame.groupby(["cell_id", "ts"], as_index=False, sort=True)["soil_moisture"]
            .mean())
