from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require_role
from ..models import Report
from ..schemas import ReviewRequest
from ..services.audit import write_audit
from ..services.reports import UploadProblem, create_report
from .cells import serialize_report

router = APIRouter(tags=["reports"])


@router.get("/reports")
def list_reports(status: str | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    query = db.query(Report)
    if user.role == "volunteer":
        query = query.filter(Report.user_id == user.id)
    if status:
        query = query.filter(Report.status == status)
    return [serialize_report(report) for report in query.order_by(Report.received_at.desc()).all()]


@router.post("/reports", status_code=201)
async def upload_report(response: Response, client_report_id: str = Form(...), lat: float | None = Form(None), lon: float | None = Form(None),
                        captured_at: datetime = Form(...), device_id: str | None = Form(None),
                        note: str | None = Form(None), location_name: str | None = Form(None),
                        photo: UploadFile = File(...),
                        db: Session = Depends(get_db),
                        user=Depends(require_role("volunteer", "admin"))):
    if note and len(note) > 500:
        raise HTTPException(422, detail={"code": "note_too_long", "message": "Note must be 500 characters or less"})
    if location_name and len(location_name) > 300:
        raise HTTPException(422, detail={"code": "location_name_too_long", "message": "Place name must be 300 characters or less"})
    content = await photo.read(10 * 1024 * 1024 + 1)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    try:
        report, created = create_report(db, user_id=user.id, client_report_id=client_report_id,
                                        device_id=device_id, lat=lat, lon=lon, location_name=location_name,
                                        captured_at=captured_at,
                                        note=note, content=content, content_type=photo.content_type or "")
        if created:
            write_audit(db, user.email, "report_received", "report", report.id,
                        {"client_report_id": client_report_id, "flags": report.flags})
        db.commit()
    except UploadProblem as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    if response is not None and not created:
        response.status_code = 200
    return {"id": report.id, "client_report_id": report.client_report_id,
            "status": report.status, "flags": report.flags, "cell_id": report.cell_id,
            "location_name": report.location_name,
            "synthetic": report.synthetic}


@router.get("/reports/{report_id}/photo")
def get_photo(report_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, detail={"code": "report_not_found", "message": "Report does not exist"})
    if user.role == "volunteer" and report.user_id != user.id:
        raise HTTPException(404, detail={"code": "report_not_found", "message": "Report does not exist"})
    return FileResponse(report.photo_path, media_type="image/jpeg")


@router.post("/reports/{report_id}/review")
def review_report(report_id: str, request: ReviewRequest,
                  db: Session = Depends(get_db), officer=Depends(require_role("officer"))):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, detail={"code": "report_not_found", "message": "Report does not exist"})
    if report.status != "pending":
        raise HTTPException(409, detail={"code": "report_already_reviewed", "message": "Report is no longer pending"})
    report.status = request.decision
    from ..models import Review
    db.add(Review(report_id=report.id, officer_id=officer.id, decision=request.decision, note=request.note))
    write_audit(db, officer.email, "report_reviewed", "report", report.id,
                {"decision": request.decision, "note": request.note})
    db.commit()
    return serialize_report(report)
