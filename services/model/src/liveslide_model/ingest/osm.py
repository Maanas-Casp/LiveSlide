from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
import hashlib

import httpx


def ingest(config: dict, output_root: str | Path) -> dict[str, int]:
    """Export OSM roads and named settlements from Overpass as GeoJSON."""
    min_lon, min_lat, max_lon, max_lat = config["bbox"]
    bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    endpoint = config.get("overpass_url", "https://overpass-api.de/api/interpreter")
    query = f"""[out:json][timeout:180];
(way[\"highway\"]({bbox}););out geom;
node[\"place\"~\"city|town|village|hamlet\"][\"name\"]({bbox});out body;
"""
    response = httpx.post(endpoint, data={"data": query}, timeout=210)
    response.raise_for_status()
    payload = response.json()
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    roads, settlements = [], []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        if element.get("type") == "way" and tags.get("highway"):
            coordinates = [[point["lon"], point["lat"]] for point in element.get("geometry", [])]
            if len(coordinates) >= 2:
                roads.append({"type": "Feature", "id": f"way/{element['id']}",
                              "properties": {"name": tags.get("name"), "road_class": tags["highway"]},
                              "geometry": {"type": "LineString", "coordinates": coordinates}})
        elif element.get("type") == "node" and tags.get("place"):
            settlements.append({"type": "Feature", "id": f"node/{element['id']}",
                                "properties": {"name": tags.get("name"), "place": tags["place"],
                                               "population": _population(tags.get("population"))},
                                "geometry": {"type": "Point", "coordinates": [element["lon"], element["lat"]]}})
    _write_feature_collection(output / "roads.geojson", roads)
    _write_feature_collection(output / "settlements.geojson", settlements)
    manifest = {"source": "OpenStreetMap Overpass API", "endpoint": endpoint,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "bbox": config["bbox"], "license": "ODbL",
                "roads_sha256": hashlib.sha256((output / "roads.geojson").read_bytes()).hexdigest(),
                "settlements_sha256": hashlib.sha256((output / "settlements.geojson").read_bytes()).hexdigest()}
    (output / "osm_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"roads": len(roads), "settlements": len(settlements)}


def _population(value):
    try:
        return int(str(value).replace(",", "")) if value is not None else None
    except ValueError:
        return None


def _write_feature_collection(path: Path, features: list[dict]) -> None:
    collection = {"type": "FeatureCollection", "name": path.stem,
                  "license": "Open Database License (ODbL)",
                  "attribution": "© OpenStreetMap contributors",
                  "features": features}
    path.write_text(json.dumps(collection), encoding="utf-8")
