from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_service_key
from ..models import Cell, Event, Feature, Score
from ..schemas import FeatureItem, ScoreItem
from ..services.time import to_utc_naive

router = APIRouter(tags=["ingest"], dependencies=[Depends(require_service_key)])
MAX_BATCH = 10000


def ensure_batch(items):
    if not isinstance(items, list) or len(items) > MAX_BATCH:
        raise HTTPException(422, detail={"code": "invalid_batch", "message": "Expected an array of at most 10,000 rows"})


@router.post("/features")
def ingest_features(items: list[FeatureItem], db: Session = Depends(get_db)):
    ensure_batch(items)
    for item in items:
        if not db.get(Cell, item.cell_id):
            raise HTTPException(422, detail={"code": "unknown_cell", "message": f"Cell {item.cell_id} does not exist"})
        day = to_utc_naive(item.ts).date()
        row = db.query(Feature).filter(Feature.cell_id == item.cell_id, Feature.ts == day).first()
        values = item.model_dump(exclude={"cell_id", "ts"})
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            db.add(Feature(cell_id=item.cell_id, ts=day, **values))
    db.commit()
    return {"count": len(items)}


@router.post("/scores")
def ingest_scores(items: list[ScoreItem], db: Session = Depends(get_db)):
    ensure_batch(items)
    for item in items:
        if not db.get(Cell, item.cell_id):
            raise HTTPException(422, detail={"code": "unknown_cell", "message": f"Cell {item.cell_id} does not exist"})
        timestamp = to_utc_naive(item.ts)
        row = db.query(Score).filter(Score.cell_id == item.cell_id, Score.ts == timestamp,
                                     Score.model_version == item.model_version).first()
        values = item.model_dump(exclude={"cell_id", "ts", "model_version"})
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            db.add(Score(cell_id=item.cell_id, ts=timestamp, model_version=item.model_version, **values))
    db.commit()
    return {"count": len(items)}


@router.post("/cells/static")
def ingest_static(items: list[dict], db: Session = Depends(get_db)):
    ensure_batch(items)
    for item in items:
        required = {"cell_id", "state", "row", "col", "min_lon", "min_lat", "max_lon", "max_lat"}
        if required - item.keys():
            raise HTTPException(422, detail={"code": "invalid_cell", "message": "Cell is missing required geometry fields"})
        cell = db.get(Cell, item["cell_id"])
        values = {key: item.get(key) for key in required | {"elevation_m", "slope_deg", "curvature", "twi", "synthetic"}}
        values["synthetic"] = bool(item.get("synthetic", False))
        if cell:
            for key, value in values.items():
                setattr(cell, key, value)
        else:
            db.add(Cell(**values))
    db.commit()
    return {"count": len(items)}


@router.post("/events")
def ingest_events(items: list[dict], db: Session = Depends(get_db)):
    ensure_batch(items)
    for item in items:
        try:
            day = date.fromisoformat(str(item["event_date"])[:10])
            lat, lon = float(item["latitude"]), float(item["longitude"])
            source = str(item["source"])
        except (KeyError, ValueError) as exc:
            raise HTTPException(422, detail={"code": "invalid_event", "message": "Event needs date, latitude, longitude and source"}) from exc
        existing = db.query(Event).filter(Event.event_date == day, Event.latitude == lat,
                                          Event.longitude == lon, Event.source == source).first()
        if existing:
            for key in ("location_accuracy_m", "trigger", "fatalities", "notes", "cell_id", "synthetic"):
                if key in item:
                    setattr(existing, key, item[key])
        else:
            cell = db.query(Cell).filter(Cell.min_lon <= lon, Cell.max_lon >= lon,
                                         Cell.min_lat <= lat, Cell.max_lat >= lat).first()
            db.add(Event(event_date=day, latitude=lat, longitude=lon, source=source,
                         cell_id=cell.cell_id if cell else None,
                         location_accuracy_m=item.get("location_accuracy_m"),
                         trigger=item.get("trigger"), fatalities=item.get("fatalities"),
                         notes=item.get("notes"), synthetic=bool(item.get("synthetic", False))))
    db.commit()
    return {"count": len(items)}
