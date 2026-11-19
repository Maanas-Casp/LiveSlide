from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog


def _canonical(ts, actor, action, entity, entity_id, payload) -> bytes:
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        timestamp = ts.astimezone(timezone.utc).isoformat()
    else:
        timestamp = str(ts)
    value = {"ts": timestamp, "actor": actor, "action": action, "entity": entity,
             "entity_id": entity_id, "payload": payload or {}}
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def write_audit(db: Session, actor: str, action: str, entity: str, entity_id: str,
                payload: dict | None = None) -> AuditLog:
    last = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    previous = last.row_hash if last else "0" * 64
    timestamp = datetime.now(timezone.utc)
    content = _canonical(timestamp, actor, action, entity, entity_id, payload)
    row_hash = hashlib.sha256(previous.encode() + content).hexdigest()
    row = AuditLog(ts=timestamp, actor=actor, action=action, entity=entity,
                   entity_id=str(entity_id), payload=payload or {}, prev_hash=previous,
                   row_hash=row_hash)
    db.add(row)
    db.flush()
    return row


def verify_audit_chain(db: Session) -> dict:
    expected_prev = "0" * 64
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
    for row in rows:
        actual = hashlib.sha256(expected_prev.encode() + _canonical(
            row.ts, row.actor, row.action, row.entity, row.entity_id, row.payload
        )).hexdigest()
        if row.prev_hash != expected_prev or row.row_hash != actual:
            return {"valid": False, "first_broken_row": row.id}
        expected_prev = row.row_hash
    return {"valid": True, "rows_checked": len(rows)}
