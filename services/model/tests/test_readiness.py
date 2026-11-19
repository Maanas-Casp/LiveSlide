import subprocess

import pytest

from liveslide_model.eval.readiness import ProtocolReadinessError, require_committed_protocol


def test_protocol_must_be_committed_before_model_code(monkeypatch):
    def fake_output(command, **kwargs):
        if command[1] == "log" and "docs/EVALUATION_PROTOCOL.md" in command:
            return "protocol-commit"
        if command[1] == "log":
            return "model-commit"
        return ""

    monkeypatch.setattr(subprocess, "check_output", fake_output)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    require_committed_protocol()


def test_dirty_model_code_blocks_first_run(monkeypatch):
    def fake_output(command, **kwargs):
        if command[1] == "log" and "docs/EVALUATION_PROTOCOL.md" in command:
            return "protocol-commit"
        if command[1] == "log":
            return "model-commit"
        return " M services/model/src/liveslide_model/__main__.py"

    monkeypatch.setattr(subprocess, "check_output", fake_output)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(ProtocolReadinessError, match="Commit or discard"):
        require_committed_protocol()
