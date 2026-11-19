from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import pandas as pd

from .earthdata import download_collection, record_downloads


def ingest(config: dict, cells: pd.DataFrame, raw_root: str | Path,
           processed_root: str | Path) -> pd.DataFrame:
    """Download SRTMGL1 V003 and derive cell-mean terrain values at 30 m."""
    try:
        import rasterio
        from rasterio.merge import merge
    except ImportError as exc:
        raise RuntimeError("Install the optional 'geo' dependencies to process SRTM") from exc
    short_name = config.get("dem_short_name", "SRTMGL1")
    version = str(config.get("dem_version", "003"))
    files = download_collection(short_name, version, tuple(config["bbox"]),
                                config["start_date"], config["end_date"], Path(raw_root) / "dem")
    record_downloads(files, source=short_name, version=version,
                     start_date=config["start_date"], end_date=config["end_date"])
    rasters = [rasterio.open(path) for path in files if path.suffix.lower() in {".tif", ".tiff"}]
    if not rasters:
        raise RuntimeError("SRTM search returned no GeoTIFF files")
    mosaic, transform = merge(rasters)
    profile = rasters[0].profile.copy()
    profile.update(driver="GTiff", height=mosaic.shape[1], width=mosaic.shape[2], transform=transform)
    for raster in rasters:
        raster.close()
    target_crs = config.get("terrain_crs") or _utm_crs(tuple(config["bbox"]))
    output = Path(processed_root)
    output.mkdir(parents=True, exist_ok=True)
    mosaic_path = output / "dem_mosaic.tif"
    with rasterio.open(mosaic_path, "w", **profile) as dst:
        dst.write(mosaic)
    metric_path = output / "dem_projected_30m.tif"
    _reproject_dem(mosaic_path, metric_path, target_crs)
    result = derive_terrain(metric_path, cells)
    terrain_path = output / "terrain.parquet"
    result.to_parquet(terrain_path, index=False)
    from .manifest import write_manifest
    write_manifest(terrain_path, source=short_name, version=version,
                   start_date=config["start_date"], end_date=config["end_date"],
                   metadata={"crs": target_crs, "resolution_m": 30,
                             "slope": "Horn 3x3 gradient", "curvature": "elevation Laplacian",
                             "twi": "D8 contributing cell counts times cell width over tan(slope)"})
    return result


def _utm_crs(bbox: tuple[float, float, float, float]) -> str:
    longitude = (bbox[0] + bbox[2]) / 2
    latitude = (bbox[1] + bbox[3]) / 2
    zone = int((longitude + 180) // 6) + 1
    return f"EPSG:{32600 + zone if latitude >= 0 else 32700 + zone}"


def _reproject_dem(source: Path, destination: Path, target_crs: str) -> None:
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    with rasterio.open(source) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds, resolution=30
        )
        profile = src.profile.copy()
        profile.update(crs=target_crs, transform=transform, width=width, height=height,
                       dtype="float32", nodata=-9999)
        with rasterio.open(destination, "w", **profile) as dst:
            for band in range(1, src.count + 1):
                reproject(source=rasterio.band(src, band), destination=rasterio.band(dst, band),
                          src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                          dst_transform=transform, dst_crs=target_crs, dst_nodata=-9999,
                          resampling=Resampling.bilinear)


def derive_terrain(raster_path: str | Path, cells: pd.DataFrame) -> pd.DataFrame:
    """Compute Horn 3x3 slope, Laplacian curvature and D8-flow TWI on a metric DEM."""
    import rasterio
    from pyproj import Transformer
    from rasterio.errors import WindowError
    from rasterio.features import geometry_mask, geometry_window
    from shapely.geometry import box, mapping
    from shapely.ops import transform as transform_geometry

    required = {"cell_id", "min_lon", "min_lat", "max_lon", "max_lat"}
    if required - set(cells):
        raise ValueError("Cell table must include IDs and geographic bounds")
    with rasterio.open(raster_path) as dataset:
        if not dataset.crs or not dataset.crs.is_projected:
            raise ValueError("Terrain raster must be reprojected to a metric CRS first")
        elevation = dataset.read(1, masked=True).astype("float64").filled(np.nan)
        pixel_x = abs(dataset.transform.a)
        pixel_y = abs(dataset.transform.e)
        if not np.isclose(pixel_x, 30, atol=1) or not np.isclose(pixel_y, 30, atol=1):
            raise ValueError("Terrain derivatives expect a 30 m projected raster")
        valid = np.isfinite(elevation)
        dz_dy, dz_dx = np.gradient(np.where(valid, elevation, np.nan), pixel_y, pixel_x)
        slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
        d2z_dy2 = np.gradient(dz_dy, pixel_y, axis=0)
        d2z_dx2 = np.gradient(dz_dx, pixel_x, axis=1)
        curvature = d2z_dx2 + d2z_dy2
        accumulation = _d8_accumulation(elevation, valid)
        twi = np.log(np.maximum(accumulation * pixel_x /
                                np.maximum(np.tan(slope_rad), 1e-4), 1e-6))
        transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
        results = []
        for cell in cells.itertuples(index=False):
            polygon = box(cell.min_lon, cell.min_lat, cell.max_lon, cell.max_lat)
            projected = transform_geometry(transformer.transform, polygon)
            try:
                window = geometry_window(dataset, [mapping(projected)])
            except WindowError:
                window = None
            if window is None:
                results.append({"cell_id": cell.cell_id, "elevation_m": np.nan,
                                "slope_deg": np.nan, "curvature": np.nan, "twi": np.nan})
                continue
            row_start, row_stop = int(window.row_off), int(window.row_off + window.height)
            col_start, col_stop = int(window.col_off), int(window.col_off + window.width)
            window_slice = np.s_[row_start:row_stop, col_start:col_stop]
            window_shape = (row_stop - row_start, col_stop - col_start)
            inside = geometry_mask([mapping(projected)], out_shape=window_shape,
                                   transform=dataset.window_transform(window), invert=True)
            mask = inside & valid[window_slice]
            if not mask.any():
                results.append({"cell_id": cell.cell_id, "elevation_m": np.nan,
                                "slope_deg": np.nan, "curvature": np.nan, "twi": np.nan})
                continue
            results.append({
                "cell_id": cell.cell_id,
                "elevation_m": float(np.nanmean(elevation[window_slice][mask])),
                "slope_deg": float(np.degrees(np.nanmean(slope_rad[window_slice][mask]))),
                "curvature": float(np.nanmean(curvature[window_slice][mask])),
                "twi": float(np.nanmean(twi[window_slice][mask])),
            })
    return pd.DataFrame(results)


def _d8_accumulation(elevation: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Accumulate upslope cell counts along the steepest of eight downslope neighbours."""
    rows, cols = elevation.shape
    accumulation = np.ones(elevation.shape, dtype="float64")
    downstream = np.full(elevation.shape + (2,), -1, dtype="int32")
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for row, col in zip(*np.where(valid)):
        best_slope = 0.0
        best = None
        for dr, dc in offsets:
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols and valid[nr, nc]:
                distance = 30 * math.hypot(dr, dc)
                downhill = (elevation[row, col] - elevation[nr, nc]) / distance
                if downhill > best_slope:
                    best_slope, best = downhill, (nr, nc)
        if best is not None:
            downstream[row, col] = best
    order = np.argsort(elevation[valid])[::-1]
    coordinates = np.column_stack(np.where(valid))
    for index in order:
        row, col = coordinates[index]
        nr, nc = downstream[row, col]
        if nr >= 0:
            accumulation[nr, nc] += accumulation[row, col]
    return accumulation
