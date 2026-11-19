from __future__ import annotations

from pathlib import Path


def download_collection(short_name: str, version: str, bbox: tuple[float, float, float, float],
                       start_date: str, end_date: str, cache_dir: str | Path) -> list[Path]:
    """Search and download a version-pinned NASA collection into its raw cache."""
    try:
        import earthaccess
    except ImportError as exc:
        raise RuntimeError("Install the optional 'nasa' dependencies to use Earthdata") from exc
    target = Path(cache_dir)
    target.mkdir(parents=True, exist_ok=True)
    earthaccess.login(strategy="environment", persist=False)
    granules = earthaccess.search_data(
        short_name=short_name,
        version=version,
        bounding_box=bbox,
        temporal=(start_date, end_date),
    )
    if not granules:
        raise RuntimeError(f"Earthdata returned no {short_name} v{version} granules for this region/date range")
    earthaccess.download(granules, local_path=str(target))
    files = sorted(path for path in target.iterdir() if path.is_file() and not path.name.endswith(".xml"))
    if not files:
        raise RuntimeError(f"Earthdata returned granules but no files were cached under {target}")
    return files


def record_downloads(files: list[Path], *, source: str, version: str,
                    start_date: str, end_date: str) -> None:
    from .manifest import write_manifest

    for path in files:
        write_manifest(path, source=source, version=version,
                       start_date=start_date, end_date=end_date,
                       metadata={"license_reference": "NASA Earthdata product terms; see docs/DATA_SOURCES.md"})
