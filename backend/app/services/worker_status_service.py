from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import settings


def get_worker_status() -> dict:
    default = {
        "worker_active": False,
        "last_sync_time": None,
        "files_processed": 0,
        "automation_health": "unknown",
        "last_error": None,
    }

    if not settings.worker_status_path.exists():
        return default

    try:
        payload = json.loads(settings.worker_status_path.read_text(encoding="utf-8"))
    except Exception:
        return {**default, "automation_health": "error", "last_error": "Invalid worker status file."}

    for key, value in default.items():
        payload.setdefault(key, value)

    payload.setdefault("retrieved_at", datetime.now(timezone.utc).isoformat())
    return payload
