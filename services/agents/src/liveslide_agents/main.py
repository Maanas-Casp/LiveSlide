"""Small, deterministic agent service for a reviewable first vertical slice.

The workflow deliberately drafts alerts only. Dispatch is represented by a local
mock log and can happen only after an officer resumes an approved run.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .workflow import risk_workflow

SERVICE_KEY = os.getenv("API_SERVICE_KEY", "local-dev-service-key")
DB_PATH = Path(os.getenv("AGENTS_DB", "/tmp/liveslide-agents.sqlite"))
DISPATCH_LOG = Path(os.getenv("DISPATCH_LOG", "/tmp/liveslide-dispatch.jsonl"))
DISPATCH_MODE = os.getenv("DISPATCH_MODE", "mock")


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, cell_id TEXT NOT NULL, risk_p REAL NOT NULL, status TEXT NOT NULL, alert_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, result TEXT)")
    return db


class RunRequest(BaseModel):
    cell_id: str = Field(min_length=1, max_length=80)
    risk_p: float = Field(ge=0, le=1)
    synthetic: bool = False
    area_name: str = "Area requiring officer review"
    road_names: list[str] = []


class ResumeRequest(BaseModel):
    approved: bool
    officer_id: str = Field(min_length=1)


app = FastAPI(title="Liveslide Agent Workflow", version="0.1.0")


def require_key(key: str | None):
    if not key or key != SERVICE_KEY:
        raise HTTPException(403, "Invalid service key")


@app.get("/health")
def health():
    return {"status": "ok", "dispatch_mode": DISPATCH_MODE}


@app.post("/runs", status_code=202)
async def create_run(request: RunRequest, x_service_key: str | None = Header(default=None)):
    require_key(x_service_key)
    run_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    # Only a high risk score can enter the alert drafting path.
    workflow = risk_workflow.invoke({"risk_p": request.risk_p})
    if workflow["decision"] == "close_without_alert":
        status, result = "closed_no_alert", {"reason": "risk_below_draft_threshold"}
        alert_id = None
    else:
        status, result, alert_id = workflow["decision"], None, None
        valid_from = now
        facts = {"cell_ids": [request.cell_id], "cell_count": 1, "risk_p": request.risk_p,
                 "risk_band": "high" if request.risk_p >= 0.8 else "moderate",
                 "area_names": [request.area_name], "road_names": request.road_names,
                 "valid_from": valid_from.isoformat().replace("+00:00", "Z"),
                 "valid_until": (valid_from + timedelta(hours=12)).isoformat().replace("+00:00", "Z"),
                 "recommended_action": "prepare_to_move" if request.risk_p >= 0.8 else "avoid_slopes_and_roads",
                 "synthetic": request.synthetic}
        db = connect()
        db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, NULL, ?, ?, NULL)",
                   (run_id, request.cell_id, request.risk_p, "drafting", now.isoformat(), now.isoformat()))
        db.commit()
        db.close()
        import httpx
        api_url = os.getenv("API_INTERNAL_URL", "http://api:8000/api/v1").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(f"{api_url}/alerts/drafts", headers={"X-Service-Key": SERVICE_KEY},
                    json={"run_id": run_id, "facts": facts,
                          "texts": {"en": f"Landslide risk is elevated near {request.area_name}. Please follow local authority guidance.",
                                    "hi": f"{request.area_name} के पास भूस्खलन का जोखिम बढ़ा है। स्थानीय प्रशासन के निर्देशों का पालन करें।"}})
                response.raise_for_status()
                alert_id = response.json()["id"]
        except Exception as exc:
            db = connect()
            db.execute("UPDATE runs SET status='failed', result=?, updated_at=? WHERE id=?",
                       (json.dumps({"error": str(exc)[:300]}), datetime.now(UTC).isoformat(), run_id))
            db.commit()
            db.close()
            raise HTTPException(502, "Could not create the API alert draft") from exc
        result = {"alert_id": alert_id, "synthetic": request.synthetic}
    db = connect()
    db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (run_id, request.cell_id, request.risk_p, status, alert_id, now.isoformat(),
                datetime.now(UTC).isoformat(), json.dumps(result) if result else None))
    db.commit()
    db.close()
    return {"run_id": run_id, "status": status, "alert_id": alert_id, "result": result}


@app.get("/runs/{run_id}")
def get_run(run_id: str, x_service_key: str | None = Header(default=None)):
    require_key(x_service_key)
    db = connect()
    row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    db.close()
    if row is None:
        raise HTTPException(404, "Run not found")
    return {**dict(row), "result": json.loads(row["result"]) if row["result"] else None}


@app.post("/runs/{run_id}/resume")
def resume_run(run_id: str, request: ResumeRequest, x_service_key: str | None = Header(default=None)):
    require_key(x_service_key)
    db = connect()
    row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        db.close()
        raise HTTPException(404, "Run not found")
    if row["status"] != "waiting_for_approval":
        db.close()
        raise HTTPException(409, "Run is not waiting for officer approval")
    if request.approved and DISPATCH_MODE == "mock":
        DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DISPATCH_LOG.open("a", encoding="utf-8") as log:
            run_result = json.loads(row["result"]) if row["result"] else {}
            log.write(json.dumps({"run_id": run_id, "cell_id": row["cell_id"],
                                  "approved_by": request.officer_id, "mode": "mock",
                                  "synthetic": bool(run_result.get("synthetic", False)),
                                  "at": datetime.now(UTC).isoformat()}) + "\n")
        status = "mock_dispatched"
    elif request.approved:
        status = "approved_dispatch_disabled"
    else:
        status = "rejected"
    db.execute("UPDATE runs SET status=?, updated_at=? WHERE id=?",
               (status, datetime.now(UTC).isoformat(), run_id))
    db.commit()
    db.close()
    return {"run_id": run_id, "status": status}
