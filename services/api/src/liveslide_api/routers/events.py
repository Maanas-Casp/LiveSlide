from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Event
from .cells import parse_bbox

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(bbox: str | None = None, limit: int = Query(100, ge=1, le=10000),
                db: Session = Depends(get_db), user=Depends(current_user)):
    query = db.query(Event)
    if bbox:
        min_lon, min_lat, max_lon, max_lat = parse_bbox(bbox)
        query = query.filter(Event.longitude.between(min_lon, max_lon),
                             Event.latitude.between(min_lat, max_lat))
    return [{"id": event.id, "event_date": event.event_date.isoformat(),
             "latitude": event.latitude, "longitude": event.longitude,
             "location_accuracy_m": event.location_accuracy_m, "source": event.source,
             "trigger": event.trigger, "fatalities": event.fatalities,
             "cell_id": event.cell_id, "synthetic": event.synthetic}
            for event in query.order_by(Event.event_date.desc()).limit(limit).all()]
