import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from liveslide_agents import main
from liveslide_agents.main import ResumeRequest, RunRequest


class DraftResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"id": "alert-test-id"}


class DraftClient:
    def __init__(self, *args, **kwargs):
        self.payload = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, headers, json):
        self.payload = json
        return DraftResponse()


@pytest.fixture
def isolated_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "agents.sqlite")
    monkeypatch.setattr(main, "DISPATCH_LOG", tmp_path / "dispatch.jsonl")
    monkeypatch.setattr(main, "SERVICE_KEY", "test-key")
    monkeypatch.setattr(main, "DISPATCH_MODE", "mock")


def test_high_risk_run_drafts_and_waits_for_approval(isolated_agent, monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", DraftClient)
    result = asyncio.run(main.create_run(RunRequest(cell_id="AS-0000-0001", risk_p=0.86), "test-key"))
    assert result["status"] == "waiting_for_approval"
    assert result["alert_id"] == "alert-test-id"
    stored = main.get_run(result["run_id"], "test-key")
    assert stored["status"] == "waiting_for_approval"

    resumed = main.resume_run(result["run_id"], ResumeRequest(approved=True, officer_id="officer-1"), "test-key")
    assert resumed["status"] == "mock_dispatched"
    dispatches = main.DISPATCH_LOG.read_text(encoding="utf-8").splitlines()
    assert len(dispatches) == 1
    assert json.loads(dispatches[0])["approved_by"] == "officer-1"
    with pytest.raises(HTTPException) as error:
        main.resume_run(result["run_id"], ResumeRequest(approved=True, officer_id="officer-1"), "test-key")
    assert error.value.status_code == 409


def test_below_warn_run_closes_without_contacting_api(isolated_agent):
    result = asyncio.run(main.create_run(RunRequest(cell_id="AS-0000-0001", risk_p=0.79), "test-key"))
    assert result["status"] == "closed_no_alert"
    assert result["alert_id"] is None
    assert not main.DISPATCH_LOG.exists()
