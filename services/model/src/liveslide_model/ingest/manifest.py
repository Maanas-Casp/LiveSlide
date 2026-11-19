from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def write_manifest(output_path: str | Path, *, source: str, version: str,
                   start_date: str, end_date: str, metadata: dict | None = None) -> Path:
    output = Path(output_path)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    manifest = {"source": source, "version": version, "date_range": [start_date, end_date],
                "accessed_at": datetime.now(timezone.utc).isoformat(),
                "file": output.name, "sha256": digest, "code_commit": commit,
                "metadata": metadata or {}}
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path
