from __future__ import annotations

import subprocess


class ProtocolReadinessError(RuntimeError):
    """Raised when a research run would violate the protocol-first rule."""


def require_committed_protocol() -> None:
    """Require a clean protocol commit that is an ancestor of the model commit."""
    try:
        protocol_commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "docs/EVALUATION_PROTOCOL.md"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        model_commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "services/model"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--", "docs/EVALUATION_PROTOCOL.md", "services/model"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProtocolReadinessError("Could not verify the protocol and model commits") from exc
    if not protocol_commit:
        raise ProtocolReadinessError("Commit docs/EVALUATION_PROTOCOL.md before the first model run")
    if not model_commit or protocol_commit == model_commit:
        raise ProtocolReadinessError(
            "Commit the model code in a separate later commit, after the evaluation protocol"
        )
    try:
        subprocess.run(["git", "merge-base", "--is-ancestor", protocol_commit, model_commit],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProtocolReadinessError(
            "The protocol commit must be an ancestor of a later model-code commit"
        ) from exc
    if dirty:
        raise ProtocolReadinessError(
            "Commit or discard changes in docs/EVALUATION_PROTOCOL.md and services/model before running"
        )
