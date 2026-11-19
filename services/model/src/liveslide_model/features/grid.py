from __future__ import annotations

import math

import pandas as pd


def make_grid(state: str, bbox: tuple[float, float, float, float], cell_km: float = 1.0) -> pd.DataFrame:
    """Return cell IDs and bounds using a regular EPSG:4326 approximation.

    Longitude spacing is calculated once at the bbox centre latitude. Cell area therefore
    varies slightly across the region; calculate final areas in a projected CRS downstream.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    if min_lon >= max_lon or min_lat >= max_lat or cell_km <= 0:
        raise ValueError("Invalid bbox or cell size")
    centre_lat = (min_lat + max_lat) / 2
    lat_step = cell_km / 111.32
    lon_step = cell_km / (111.32 * math.cos(math.radians(centre_lat)))
    rows = []
    row = 0
    south = min_lat
    while south < max_lat - 1e-12:
        col = 0
        west = min_lon
        while west < max_lon - 1e-12:
            rows.append({
                "cell_id": f"{state}-{row:04d}-{col:04d}",
                "state": state,
                "row": row,
                "col": col,
                "min_lon": west,
                "min_lat": south,
                "max_lon": min(west + lon_step, max_lon),
                "max_lat": min(south + lat_step, max_lat),
                "longitude": west + lon_step / 2,
                "latitude": south + lat_step / 2,
            })
            col += 1
            west = min_lon + col * lon_step
        row += 1
        south = min_lat + row * lat_step
    return pd.DataFrame(rows)
