from datetime import datetime, timezone
from pathlib import Path
import json

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from jsonschema import ValidationError, validate
from sqlalchemy.orm import Session

from ..config import AGENTS_URL, API_SERVICE_KEY
from ..db import SessionLocal, get_db
from ..deps import current_user, require_role, require_service_key
from ..models import Alert
from ..schemas import AlertDraftRequest, RejectAlertRequest
from ..services.audit import write_audit
from ..services.time import iso_utc

router = APIRouter(tags=["alerts"])
FACTS_SCHEMA = Path(__file__).resolve().parents[5] / "contracts/alert_facts.schema.json"


def facts_schema():
    return json.loads(FACTS_SCHEMA.read_text(encoding="utf-8"))


async def resume_agent(run_id: str, approved: bool, officer_id: str):
    if not AGENTS_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"{AGENTS_URL.rstrip('/')}/runs/{run_id}/resume",
                json={"approved": approved, "officer_id": officer_id},
                headers={"X-Service-Key": API_SERVICE_KEY},
            )
            response.raise_for_status()
    except Exception as exc:
        db = SessionLocal()
        try:
            write_audit(db, "api", "agents_resume_failed", "agent_run", run_id,
                        {"approved": approved, "error": str(exc)[:200]})
            db.commit()
        finally:
            db.close()


@router.post("/alerts/drafts", status_code=201, dependencies=[Depends(require_service_key)])
def create_draft(request: AlertDraftRequest, db: Session = Depends(get_db)):
    try:
        validate(request.facts, facts_schema())
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(422, detail={"code": "invalid_alert_facts", "message": str(exc)}) from exc
    alert = Alert(run_id=request.run_id, facts=request.facts, texts=request.texts,
                  status="draft", created_at=datetime.now(timezone.utc))
    db.add(alert)
    db.flush()
    write_audit(db, "agents", "alert_drafted", "alert", alert.id, {"run_id": request.run_id})
    db.commit()
    return serialize_alert(alert)


@router.get("/alerts")
def list_alerts(status: str | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    return [serialize_alert(alert) for alert in query.order_by(Alert.created_at.desc()).all()]


@router.post("/alerts/{alert_id}/approve")
def approve_alert(alert_id: str, background: BackgroundTasks,
                  db: Session = Depends(get_db), officer=Depends(require_role("officer"))):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, detail={"code": "alert_not_found", "message": "Alert does not exist"})
    if alert.status != "draft":
        raise HTTPException(409, detail={"code": "alert_not_draft", "message": "Only a draft alert can be approved"})
    alert.status = "approved"
    alert.approved_by = officer.id
    alert.approved_at = datetime.now(timezone.utc)
    write_audit(db, officer.email, "alert_approved", "alert", alert.id, {"run_id": alert.run_id})
    db.commit()
    if AGENTS_URL:
        background.add_task(resume_agent, alert.run_id, True, officer.id)
    return serialize_alert(alert)


@router.post("/alerts/{alert_id}/reject")
def reject_alert(alert_id: str, request: RejectAlertRequest, background: BackgroundTasks,
                 db: Session = Depends(get_db), officer=Depends(require_role("officer"))):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, detail={"code": "alert_not_found", "message": "Alert does not exist"})
    if alert.status != "draft":
        raise HTTPException(409, detail={"code": "alert_not_draft", "message": "Only a draft alert can be rejected"})
    alert.status = "rejected"
    alert.rejected_reason = request.reason
    write_audit(db, officer.email, "alert_rejected", "alert", alert.id,
                {"run_id": alert.run_id, "reason": request.reason})
    db.commit()
    if AGENTS_URL:
        background.add_task(resume_agent, alert.run_id, False, officer.id)
    return serialize_alert(alert)


def serialize_alert(alert):
    return {"id": alert.id, "run_id": alert.run_id, "facts": alert.facts, "texts": alert.texts,
            "status": alert.status, "created_at": iso_utc(alert.created_at),
            "approved_by": alert.approved_by,
            "approved_at": iso_utc(alert.approved_at),
            "rejected_reason": alert.rejected_reason}
