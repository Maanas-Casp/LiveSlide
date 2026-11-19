from __future__ import annotations

from pathlib import Path

import pandas as pd

from .earthdata import download_collection, record_downloads


def ingest(config: dict, cells: pd.DataFrame, raw_root: str | Path) -> pd.DataFrame:
    """Download IMERG V07 granules and sample the nearest daily pixel per cell."""
    short_name = config.get("imerg_short_name", "GPM_3IMERGDF")
    version = str(config.get("imerg_version", "07"))
    raw_dir = Path(raw_root) / "imerg"
    files = download_collection(short_name, version, tuple(config["bbox"]),
                                config["start_date"], config["end_date"], raw_dir)
    record_downloads(files, source=short_name, version=version,
                     start_date=config["start_date"], end_date=config["end_date"])
    return read_daily_cells(files, cells)


def read_daily_cells(files: list[Path], cells: pd.DataFrame) -> pd.DataFrame:
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("Install the optional 'geo' dependencies to read IMERG files") from exc
    required = {"cell_id", "latitude", "longitude"}
    if required - set(cells):
        raise ValueError("cells require cell_id and centroid latitude/longitude")
    output = []
    for path in files:
        try:
            dataset = xr.open_dataset(path)
        except (ValueError, OSError):
            dataset = xr.open_dataset(path, group="Grid")
        lon_name = next((name for name in ("lon", "longitude") if name in dataset.coords), None)
        lat_name = next((name for name in ("lat", "latitude") if name in dataset.coords), None)
        time_name = next((name for name in ("time", "time_bnds") if name in dataset.coords), None)
        var_name = next((name for name in ("precipitationCal", "precipitation", "precipitationUncal")
                         if name in dataset.data_vars), None)
        if not all((lon_name, lat_name, time_name, var_name)):
            dataset.close()
            raise ValueError(f"Could not identify daily rainfall coordinates/variable in {path.name}")
        values = dataset[var_name]
        if time_name in values.dims:
            values = values.isel({time_name: 0})
        for cell in cells.itertuples(index=False):
            point = values.sel({lon_name: cell.longitude, lat_name: cell.latitude}, method="nearest")
            amount = float(point.values)
            timestamp = pd.to_datetime(dataset[time_name].values.reshape(-1)[0], utc=True)
            output.append({"cell_id": cell.cell_id, "ts": timestamp, "rain_mm": amount})
        dataset.close()
    frame = pd.DataFrame(output)
    if frame.empty:
        raise ValueError("No IMERG daily records were produced")
    duplicates = frame[frame.duplicated(["cell_id", "ts"], keep=False)]
    conflicts = duplicates.groupby(["cell_id", "ts"])["rain_mm"].nunique(dropna=False)
    if (conflicts > 1).any():
        raise ValueError("Overlapping IMERG granules contain conflicting daily values")
    return frame.drop_duplicates(["cell_id", "ts"]).sort_values(["cell_id", "ts"])
