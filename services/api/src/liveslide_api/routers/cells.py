from datetime import datetime, timedelta, timezone
import math

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..config import AGENTS_URL, API_SERVICE_KEY, DISPATCH_MODE, MAX_BBOX_AREA_DEG2
from ..db import get_db
from ..deps import current_user
from ..models import Cell, Event, Feature, Report, Road, Score, Settlement
from ..deps import require_role
from ..services.time import iso_utc

router = APIRouter(tags=["cells"])


def parse_bbox(value: str):
    try:
        bounds = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_bbox", "message": "bbox must be min_lon,min_lat,max_lon,max_lat"}) from exc
    if len(bounds) != 4:
        raise HTTPException(422, detail={"code": "invalid_bbox", "message": "bbox must contain four numbers"})
    min_lon, min_lat, max_lon, max_lat = bounds
    if min_lon >= max_lon or min_lat >= max_lat or min_lat < -90 or max_lat > 90:
        raise HTTPException(422, detail={"code": "invalid_bbox", "message": "bbox bounds are invalid"})
    if (max_lon - min_lon) * (max_lat - min_lat) > MAX_BBOX_AREA_DEG2:
        raise HTTPException(422, detail={"code": "bbox_too_large", "message": "bbox exceeds the configured maximum area"})
    return bounds


def latest_score(db: Session, cell_id: str):
    return db.query(Score).filter(Score.cell_id == cell_id).order_by(Score.ts.desc()).first()


def cell_properties(cell, score=None):
    return {"cell_id": cell.cell_id, "state": cell.state, "row": cell.row, "col": cell.col,
            "elevation_m": cell.elevation_m, "slope_deg": cell.slope_deg,
            "curvature": cell.curvature, "twi": cell.twi,
            "action": score.action if score else None, "risk_p": score.risk_p if score else None,
            "score_ts": iso_utc(score.ts) if score else None,
            "synthetic": bool(cell.synthetic or (score and score.synthetic))}


@router.get("/cells")
def get_cells(bbox: str, limit: int = Query(5000, ge=1, le=10000),
              db: Session = Depends(get_db), user=Depends(current_user)):
    min_lon, min_lat, max_lon, max_lat = parse_bbox(bbox)
    if db.bind.dialect.name == "postgresql":
        cell_ids = [row[0] for row in db.execute(text(
            "SELECT cell_id FROM cells WHERE geom && ST_MakeEnvelope(:min_lon,:min_lat,:max_lon,:max_lat,4326) "
            "AND ST_Intersects(geom, ST_MakeEnvelope(:min_lon,:min_lat,:max_lon,:max_lat,4326)) LIMIT :limit"),
            {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat, "limit": limit}).all()]
        cells = db.query(Cell).filter(Cell.cell_id.in_(cell_ids)).all() if cell_ids else []
    else:
        cells = db.query(Cell).filter(Cell.min_lon <= max_lon, Cell.max_lon >= min_lon,
                                      Cell.min_lat <= max_lat, Cell.max_lat >= min_lat).limit(limit).all()
    features = []
    for cell in cells:
        score = latest_score(db, cell.cell_id)
        geometry = {"type": "Polygon", "coordinates": [[[cell.min_lon, cell.min_lat],
                    [cell.max_lon, cell.min_lat], [cell.max_lon, cell.max_lat],
                    [cell.min_lon, cell.max_lat], [cell.min_lon, cell.min_lat]]]}
        features.append({"type": "Feature", "geometry": geometry,
                         "properties": cell_properties(cell, score)})
    return {"type": "FeatureCollection", "features": features}


@router.get("/cells/{cell_id}")
def get_cell(cell_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    cell = db.get(Cell, cell_id)
    if not cell:
        raise HTTPException(404, detail={"code": "cell_not_found", "message": "Cell does not exist"})
    return cell_properties(cell, latest_score(db, cell_id))


@router.post("/cells/{cell_id}/agent-run", status_code=202)
async def start_agent_run(cell_id: str, db: Session = Depends(get_db),
                          officer=Depends(require_role("officer", "admin"))):
    """Start an alert drafting run from the latest score; officers still approve dispatch."""
    if not AGENTS_URL:
        raise HTTPException(503, detail={"code": "agents_unavailable", "message": "Agent service is not configured"})
    cell = db.get(Cell, cell_id)
    score = latest_score(db, cell_id)
    if not cell or not score:
        raise HTTPException(404, detail={"code": "score_not_found", "message": "Cell or score does not exist"})
    if score.synthetic and DISPATCH_MODE != "mock":
        raise HTTPException(409, detail={"code": "synthetic_score", "message": "Synthetic scores can only run in mock dispatch mode"})
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{AGENTS_URL.rstrip('/')}/runs",
                headers={"X-Service-Key": API_SERVICE_KEY},
                json={"cell_id": cell.cell_id, "risk_p": score.risk_p, "synthetic": score.synthetic,
                      "area_name": cell.state, "road_names": []})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail={"code": "agents_unavailable", "message": "Could not start agent run"}) from exc


@router.get("/cells/{cell_id}/features")
def get_features(cell_id: str, days: int = Query(14, ge=1, le=365),
                 db: Session = Depends(get_db), user=Depends(current_user)):
    if not db.get(Cell, cell_id):
        raise HTTPException(404, detail={"code": "cell_not_found", "message": "Cell does not exist"})
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    rows = db.query(Feature).filter(Feature.cell_id == cell_id, Feature.ts >= cutoff).order_by(Feature.ts).all()
    return [{"ts": row.ts.isoformat(), "rain_1d": row.rain_1d, "rain_3d": row.rain_3d,
             "rain_7d": row.rain_7d, "rain_20d": row.rain_20d,
             "soil_moisture": row.soil_moisture, "synthetic": row.synthetic} for row in rows]


def distance_km(lat1, lon1, lat2, lon2):
    radius = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(min(1, math.sqrt(a)))


@router.get("/cells/{cell_id}/context")
def get_context(cell_id: str, radius_km: float = Query(3, ge=0, le=100),
                db: Session = Depends(get_db), user=Depends(current_user)):
    cell = db.get(Cell, cell_id)
    if not cell:
        raise HTTPException(404, detail={"code": "cell_not_found", "message": "Cell does not exist"})
    lat = (cell.min_lat + cell.max_lat) / 2
    lon = (cell.min_lon + cell.max_lon) / 2
    roads = []
    for road in db.query(Road).all():
        coords = road.geometry.get("coordinates", [])
        points = coords if road.geometry.get("type") == "LineString" else []
        distance = min((distance_km(lat, lon, point[1], point[0]) for point in points), default=999999)
        if distance <= radius_km:
            roads.append({"id": road.id, "name": road.name, "road_class": road.road_class,
                          "distance_km": round(distance, 3), "synthetic": road.synthetic})
    settlements = []
    for settlement in db.query(Settlement).all():
        distance = distance_km(lat, lon, settlement.latitude, settlement.longitude)
        if distance <= radius_km:
            settlements.append({"id": settlement.id, "name": settlement.name,
                                 "population": settlement.population, "distance_km": round(distance, 3),
                                 "synthetic": settlement.synthetic})
    cutoff = (datetime.now(timezone.utc) - timedelta(days=365 * 5)).date()
    events = db.query(Event).filter(Event.event_date >= cutoff).all()
    events = [event for event in events if distance_km(lat, lon, event.latitude, event.longitude) <= radius_km]
    return {"cell": cell_properties(cell, latest_score(db, cell_id)), "roads": roads,
            "settlements": settlements, "events": [{"event_date": e.event_date.isoformat(),
            "source": e.source, "trigger": e.trigger, "synthetic": e.synthetic} for e in events]}


@router.get("/cells/{cell_id}/reports")
def get_cell_reports(cell_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    query = db.query(Report).filter(Report.cell_id == cell_id, Report.status == "pending")
    if user.role == "volunteer":
        query = query.filter(Report.user_id == user.id)
    return [serialize_report(row) for row in query.order_by(Report.received_at.desc()).all()]


def serialize_report(row):
    return {"id": row.id, "client_report_id": row.client_report_id, "cell_id": row.cell_id,
            "lat": row.lat, "lon": row.lon, "location_name": row.location_name,
            "captured_at": iso_utc(row.captured_at),
            "received_at": iso_utc(row.received_at), "note": row.note, "flags": row.flags,
            "status": row.status, "verifier_score": row.verifier_score, "synthetic": row.synthetic}
