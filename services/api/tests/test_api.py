import io
import uuid

from PIL import Image

from liveslide_api.config import API_SERVICE_KEY
from liveslide_api.db import SessionLocal
from liveslide_api.models import AuditLog
from liveslide_api.services.audit import verify_audit_chain
from conftest import login


def _jpeg(color=(100, 120, 130)):
    stream = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(stream, "JPEG")
    return stream.getvalue()


def test_health_login_success_and_failure(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.post("/api/v1/auth/login", json={"email": "officer@example.test", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "officer@example.test", "password": "test-password"}).status_code == 200


def test_service_key_and_bulk_upsert(client):
    body = [{"cell_id": "AS-0000-0000", "ts": "2026-01-01T00:00:00Z", "risk_p": .7,
             "action": "VERIFY", "model_version": "v0", "synthetic": True}]
    assert client.post("/api/v1/scores", json=body).status_code == 403
    headers = {"X-Service-Key": API_SERVICE_KEY}
    assert client.post("/api/v1/scores", json=body, headers=headers).json() == {"count": 1}
    body[0]["risk_p"] = .8
    assert client.post("/api/v1/scores", json=body, headers=headers).json() == {"count": 1}
    token = login(client)
    cell = client.get("/api/v1/cells/AS-0000-0000", headers={"Authorization": f"Bearer {token}"}).json()
    assert cell["risk_p"] == .8


def test_bbox_validation_and_filter(client):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/cells", params={"bbox": "91.59,25.99,91.62,26.02"}, headers=headers)
    assert len(response.json()["features"]) == 1
    assert client.get("/api/v1/cells", params={"bbox": "bad"}, headers=headers).status_code == 422


def test_report_upload_idempotence_bad_types_and_outside_grid(client):
    token = login(client, "volunteer@example.test")
    headers = {"Authorization": f"Bearer {token}"}
    form = {"client_report_id": str(uuid.uuid4()), "lat": "26.005", "lon": "91.605",
            "captured_at": "2026-11-12T10:00:00+00:00", "device_id": "phone-1"}
    file = {"photo": ("ignored-name.jpeg", _jpeg(), "image/jpeg")}
    first = client.post("/api/v1/reports", data=form, files=file, headers=headers)
    assert first.status_code == 201
    assert first.json()["status"] == "pending"
    assert first.json()["cell_id"] == "AS-0000-0000"
    duplicate = client.post("/api/v1/reports", data=form, files=file, headers=headers)
    assert duplicate.status_code == 200
    second = dict(form, client_report_id=str(uuid.uuid4()))
    near_duplicate = client.post("/api/v1/reports", data=second, files=file, headers=headers)
    assert "duplicate_photo" in near_duplicate.json()["flags"]
    outside = dict(form, client_report_id=str(uuid.uuid4()), lat="28.0", lon="92.0")
    outside_response = client.post("/api/v1/reports", data=outside, files=file, headers=headers)
    assert "outside_grid" in outside_response.json()["flags"]
    wrong = client.post("/api/v1/reports", data=dict(form, client_report_id=str(uuid.uuid4())),
                        files={"photo": ("x.png", b"not an image", "image/png")}, headers=headers)
    assert wrong.status_code == 415


def test_report_size_role_and_officer_review(client):
    volunteer = login(client, "volunteer@example.test")
    volunteer_headers = {"Authorization": f"Bearer {volunteer}"}
    form = {"client_report_id": str(uuid.uuid4()), "lat": "26.005", "lon": "91.605",
            "captured_at": "2026-11-12T10:00:00+00:00"}
    too_big = b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024)
    response = client.post("/api/v1/reports", data=form,
                           files={"photo": ("big.jpg", too_big, "image/jpeg")}, headers=volunteer_headers)
    assert response.status_code == 413
    assert client.post("/api/v1/reports/test/review", json={"decision": "accepted"},
                       headers=volunteer_headers).status_code == 403
    uploaded = client.post("/api/v1/reports", data=form,
                           files={"photo": ("photo.jpg", _jpeg(), "image/jpeg")}, headers=volunteer_headers)
    officer = login(client)
    reviewed = client.post(f"/api/v1/reports/{uploaded.json()['id']}/review",
                           json={"decision": "accepted"},
                           headers={"Authorization": f"Bearer {officer}"})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "accepted"


def test_place_name_can_be_submitted_without_coordinates(client):
    volunteer = login(client, "volunteer@example.test")
    headers = {"Authorization": f"Bearer {volunteer}"}
    form = {"client_report_id": str(uuid.uuid4()), "captured_at": "2026-11-12T10:00:00+00:00",
            "location_name": "Near the village market, Sohra"}
    response = client.post("/api/v1/reports", data=form,
                           files={"photo": ("photo.jpg", _jpeg(), "image/jpeg")}, headers=headers)
    assert response.status_code == 201
    assert response.json()["location_name"] == "Near the village market, Sohra"
    assert "location_pending" in response.json()["flags"]
    reports = client.get("/api/v1/reports", headers=headers).json()
    saved = next(row for row in reports if row["id"] == response.json()["id"])
    assert saved["lat"] is None and saved["lon"] is None


def test_alert_schema_role_transition_and_audit_detection(client):
    facts = {"cell_ids": ["AS-0000-0000"], "cell_count": 1, "risk_p": .83,
             "risk_band": "high", "area_names": ["Demo"], "road_names": ["Road"],
             "valid_from": "2026-11-12T10:00:00Z", "valid_until": "2026-11-12T22:00:00Z",
             "recommended_action": "prepare_to_move"}
    draft = client.post("/api/v1/alerts/drafts", headers={"X-Service-Key": API_SERVICE_KEY},
                        json={"run_id": "run-1", "facts": facts, "texts": {"en": "Alert", "hi": "सूचना"}})
    assert draft.status_code == 201
    volunteer = login(client, "volunteer@example.test")
    assert client.post(f"/api/v1/alerts/{draft.json()['id']}/approve",
                       headers={"Authorization": f"Bearer {volunteer}"}).status_code == 403
    officer = login(client)
    headers = {"Authorization": f"Bearer {officer}"}
    assert client.post(f"/api/v1/alerts/{draft.json()['id']}/approve", headers=headers).status_code == 200
    assert client.post(f"/api/v1/alerts/{draft.json()['id']}/approve", headers=headers).status_code == 409
    invalid = client.post("/api/v1/alerts/drafts", headers={"X-Service-Key": API_SERVICE_KEY},
                          json={"run_id": "bad", "facts": {"bad": True}, "texts": {}})
    assert invalid.status_code == 422
    assert client.get("/api/v1/audit/verify", headers=headers).json()["valid"]

    db = SessionLocal()
    db.execute(__import__("sqlalchemy").text("DROP TRIGGER IF EXISTS audit_no_update"))
    row = db.query(AuditLog).first()
    row.payload = {"tampered": True}
    db.commit()
    assert verify_audit_chain(db)["valid"] is False
    db.close()
