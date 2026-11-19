from __future__ import annotations

import json
import os
from pathlib import Path

import httpx


def publish_batches(endpoint: str, rows: list[dict], *, dry_run: bool, output_dir: str | Path,
                    base_url: str | None = None, service_key: str | None = None,
                    batch_size: int = 5000) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    batches = [rows[index:index + batch_size] for index in range(0, len(rows), batch_size)]
    if dry_run:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        for index, batch in enumerate(batches, start=1):
            (target / f"{endpoint.strip('/')}-batch-{index:04d}.json").write_text(
                json.dumps(batch, indent=2, sort_keys=True), encoding="utf-8")
        return len(rows)
    url = (base_url or os.getenv("API_URL", "")).rstrip("/")
    key = service_key or os.getenv("API_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("Set API_URL and API_SERVICE_KEY before live publishing")
    with httpx.Client(timeout=30) as client:
        for batch in batches:
            response = client.post(f"{url}/{endpoint.strip('/')}", json=batch,
                                   headers={"X-Service-Key": key})
            response.raise_for_status()
    return len(rows)
