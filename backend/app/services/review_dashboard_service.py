from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import settings


def _latest_report_file(job_id: int) -> Path:
    matches = sorted(settings.reports_dir.glob(f"job_{job_id}_*.json"), reverse=True)
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow report not found for job.")
    return matches[0]


def list_review_queue(status_filter: str | None = None) -> list[dict]:
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(settings.reports_dir.glob("job_*.json"), reverse=True)
    items: list[dict] = []
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        stat = payload["operational_summary"]["validation_status"]
        if status_filter and stat != status_filter:
            continue
        items.append(
            {
                "job_id": payload["job_id"],
                "isbn": payload["isbn"],
                "file_name": payload["file_name"],
                "validation_status": stat,
                "overall_confidence": payload["operational_summary"]["overall_confidence"],
                "issue_count": payload["operational_summary"]["detected_issue_count"],
                "issue_severity": payload["operational_summary"]["issue_severity"],
                "processing_latency_ms": payload["operational_summary"]["processing_time_ms"],
                "publishing_readiness_score": payload.get("publishing_readiness_score", 0),
                "airtable_sync_status": payload.get("airtable_sync", {}).get("status", "pending"),
                "created_at": payload["pipeline_states"][0]["timestamp"],
            }
        )
    return items


def get_review_detail(job_id: int) -> dict:
    report_path = _latest_report_file(job_id)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.setdefault(
        "timing_metrics",
        {"image_load_ms": 0, "preprocess_ms": 0, "ocr_ms": 0, "validation_ms": 0, "total_pipeline_ms": report.get("operational_summary", {}).get("processing_time_ms", 0)},
    )

    history_files = sorted(settings.reports_dir.glob(f"job_{job_id}_*.json"), reverse=True)
    history = []
    for f in history_files:
        p = json.loads(f.read_text(encoding="utf-8"))
        history.append(
            {
                "file": f.name,
                "status": p["operational_summary"]["validation_status"],
                "confidence": p["operational_summary"]["overall_confidence"],
                "issues": p["operational_summary"]["detected_issue_count"],
            }
        )

    return {"workflow_report": report, "revision_history": history}
