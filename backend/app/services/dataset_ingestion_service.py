from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.core.config import settings
from app.services.workflow_service import run_automated_workflow

STRICT_FILENAME_PATTERN = re.compile(r"^(?P<isbn>\d{13})_text\.(?P<ext>png|pdf)$", re.IGNORECASE)
FLEX_FILENAME_PATTERN = re.compile(r"^(?P<isbn>\d{13})_(?P<label>[a-z0-9_-]+)\.(?P<ext>png|pdf)$", re.IGNORECASE)
PIPELINE_RULESET_VERSION = "2026-05-26-badge-visual-overlap-v4"
PIPELINE_STAGES = [
    "NEW FILE FOUND",
    "UPLOADING",
    "OCR PROCESSING",
    "SAFE-ZONE VALIDATION",
    "BADGE OVERLAP ANALYSIS",
    "QUALITY ANALYSIS",
    "GENERATING ANNOTATIONS",
    "GENERATING AIRTABLE RECORD",
    "GENERATING EMAIL NOTIFICATION",
    "COMPLETED",
]


def _dataset_dir() -> Path:
    return settings.project_root / "frontend" / "src" / "data" / "sample-covers"


def _state_path() -> Path:
    return settings.project_root / "storage" / "processed" / "dataset_ingest_state.json"


def _airtable_sim_dir() -> Path:
    return settings.backend_dir / "storage" / "airtable_records"


def _email_sim_dir() -> Path:
    return settings.backend_dir / "storage" / "email_previews"


def _content_type(ext: str) -> str:
    return "application/pdf" if ext == ".pdf" else "image/png"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict:
    return {
        "processed_files": {},
        "pending_files": [],
        "jobs": [],
        "stage_events": [],
        "last_run": None,
        "current_stage": "IDLE",
        "current_file": None,
        "ruleset_version": PIPELINE_RULESET_VERSION,
    }


def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return _default_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        base = _default_state()
        base.update(payload)
        return base
    except Exception:
        return _default_state()


def _save_state(payload: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _push_stage_event(state: dict, stage: str, filename: str | None = None) -> None:
    events = state.setdefault("stage_events", [])
    events.append(
        {
            "stage": stage,
            "filename": filename or state.get("current_file"),
            "timestamp": _now_iso(),
        }
    )
    # Keep latest events only for UI.
    if len(events) > 200:
        del events[:-200]


def _persist_simulation_artifacts(workflow: dict) -> None:
    isbn = workflow.get("isbn", "")
    if not isbn:
        return
    _airtable_sim_dir().mkdir(parents=True, exist_ok=True)
    _email_sim_dir().mkdir(parents=True, exist_ok=True)
    (_airtable_sim_dir() / f"{isbn}_record.json").write_text(json.dumps(workflow.get("airtable_sync", {}), indent=2), encoding="utf-8")
    notification = workflow.get("notification", {})
    email_text = f"To: {notification.get('recipient_email', '')}\nSubject: {notification.get('subject', '')}\n\n{notification.get('body', '')}\n"
    (_email_sim_dir() / f"{isbn}_email.txt").write_text(email_text, encoding="utf-8")


def _build_job_result(source_file: str, workflow: dict) -> dict:
    file_type = str(workflow.get("file_type", "")).lower()
    return {
        "filename": source_file,
        "isbn": workflow.get("isbn", ""),
        "file_type": file_type,
        "page_count": workflow.get("page_count", 1),
        "status": workflow.get("validation", {}).get("status", "REVIEW_NEEDED"),
        "confidence_score": workflow.get("operational_summary", {}).get("overall_confidence", 0),
        "readiness_score": workflow.get("publishing_readiness_score", 0),
        "issues": workflow.get("validation", {}).get("issues", []),
        "annotation_path": workflow.get("validation", {}).get("annotated_image_path", ""),
        "executive_summary": workflow.get("validation", {}).get("executive_summary", ""),
        "operational_guidance": workflow.get("validation", {}).get("operational_guidance", []),
        "correction_recommendation": workflow.get("validation", {}).get("correction_recommendations", []),
        "airtable_payload": workflow.get("airtable_sync", {}),
        "email_preview": workflow.get("notification", {}),
        "job_id": workflow.get("job_id"),
        "pipeline_status": "COMPLETED",
        "pipeline_timeline": PIPELINE_STAGES,
        "processing_time_ms": workflow.get("timing_metrics", {}).get("total_pipeline_ms", 0),
    }


def _build_invalid_job(source_file: str, reason: str) -> dict:
    return {
        "filename": source_file,
        "isbn": "",
        "file_type": Path(source_file).suffix.lower().lstrip("."),
        "page_count": None,
        "status": "INVALID_FILENAME",
        "confidence_score": 0,
        "readiness_score": 0,
        "issues": [{"type": "INVALID_FILENAME", "message": reason}],
        "annotation_path": "",
        "executive_summary": reason,
        "operational_guidance": ["Use ISBN-prefixed naming (9789373145068_text.png or 9789373145068_anylabel.png)."],
        "correction_recommendation": ["Preferred format: 9789373145068_text.png"],
        "airtable_payload": {"status": "pending", "message": "Skipped due to invalid filename."},
        "email_preview": {"subject": "Publishing QA: Ingestion Skipped", "body": reason},
        "job_id": None,
        "pipeline_status": "COMPLETED",
        "pipeline_timeline": ["NEW FILE FOUND", "COMPLETED"],
        "processing_time_ms": 0,
    }


def _get_page_count(dataset_path: Path) -> int:
    if dataset_path.suffix.lower() != ".pdf":
        return 1
    try:
        with fitz.open(dataset_path) as doc:
            return max(int(doc.page_count), 1)
    except Exception:
        return 1


def _scan_files() -> list[str]:
    dataset_dir = _dataset_dir()
    if not dataset_dir.exists():
        return []
    files = [p.name for p in dataset_dir.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".pdf"}]
    return sorted(files, key=lambda x: x.lower())


def _build_dashboard_summary(state: dict) -> dict:
    jobs = state.get("jobs", [])
    total_detected = len(jobs) + len(state.get("pending_files", []))
    completed = sum(1 for j in jobs if j.get("pipeline_status") == "COMPLETED")
    pass_count = sum(1 for j in jobs if j.get("status") == "PASS")
    review_count = sum(1 for j in jobs if j.get("status") == "REVIEW_NEEDED")
    invalid_filename_count = sum(1 for j in jobs if j.get("status") == "INVALID_FILENAME")
    overlap_count = sum(1 for j in jobs if any(i.get("type") in {"BADGE_OVERLAP", "UNCERTAIN_OVERLAP"} for i in j.get("issues", [])))
    return {
        "total_files_detected": total_detected,
        "completed_jobs": completed,
        "pass_count": pass_count,
        "review_needed_count": review_count,
        "invalid_filename_count": invalid_filename_count,
        "overlap_detections": overlap_count,
        "processing_queue_count": len(state.get("pending_files", [])),
    }


def _refresh_queue(state: dict, force: bool) -> None:
    ruleset_changed = state.get("ruleset_version") != PIPELINE_RULESET_VERSION
    if force or ruleset_changed:
        state["processed_files"] = {}
        state["jobs"] = []
        state["pending_files"] = []

    scanned = _scan_files()
    # Retry stale INVALID_FILENAME entries that previously failed with
    # "file not found" but are now present in the dataset directory.
    stale_not_found = []
    retained_jobs = []
    for job in state.get("jobs", []):
        status_text = str(job.get("status", "")).upper()
        issue_message = str((job.get("issues") or [{}])[0].get("message", "")).lower()
        filename = str(job.get("filename", ""))
        if status_text == "INVALID_FILENAME" and "file not found" in issue_message and filename in scanned:
            stale_not_found.append(filename)
            continue
        retained_jobs.append(job)

    if stale_not_found:
        state["jobs"] = retained_jobs
        existing_pending = set(state.get("pending_files", []))
        for filename in stale_not_found:
            if filename not in existing_pending:
                state["pending_files"].append(filename)
                existing_pending.add(filename)

    known = set(state.get("pending_files", [])) | {j.get("filename") for j in state.get("jobs", [])}
    for name in scanned:
        if name not in known:
            state["pending_files"].append(name)
    state["ruleset_version"] = PIPELINE_RULESET_VERSION


def _process_one_file(db: Session, state: dict) -> None:
    if not state.get("pending_files"):
        state["current_stage"] = "COMPLETED"
        state["current_file"] = None
        return

    filename = state["pending_files"].pop(0)
    state["current_file"] = filename
    state["current_stage"] = "NEW FILE FOUND"
    _push_stage_event(state, "NEW FILE FOUND", filename)

    dataset_path = _dataset_dir() / filename
    if not dataset_path.exists():
        state["jobs"].append(_build_invalid_job(filename, "File not found in dataset directory."))
        state["current_stage"] = "COMPLETED"
        _push_stage_event(state, "COMPLETED", filename)
        return

    state["current_stage"] = "UPLOADING"
    _push_stage_event(state, "UPLOADING", filename)
    strict_match = STRICT_FILENAME_PATTERN.match(filename)
    flex_match = FLEX_FILENAME_PATTERN.match(filename)
    match = strict_match or flex_match
    if not match:
        state["jobs"].append(_build_invalid_job(filename, "Invalid filename format. Expected ISBN_text.extension"))
        state["current_stage"] = "COMPLETED"
        _push_stage_event(state, "COMPLETED", filename)
        return

    isbn = match.group("isbn")
    ext = dataset_path.suffix.lower()
    normalized_upload_name = f"{isbn}_text{ext}"
    state["current_stage"] = "OCR PROCESSING"
    _push_stage_event(state, "OCR PROCESSING", filename)
    with dataset_path.open("rb") as fp:
        upload = UploadFile(filename=normalized_upload_name, file=fp, headers=Headers({"content-type": _content_type(ext)}))
        workflow = run_automated_workflow(db=db, upload=upload).model_dump(mode="json")
    workflow["page_count"] = _get_page_count(dataset_path)
    state["current_stage"] = "SAFE-ZONE VALIDATION"
    _push_stage_event(state, "SAFE-ZONE VALIDATION", filename)
    state["current_stage"] = "BADGE OVERLAP ANALYSIS"
    _push_stage_event(state, "BADGE OVERLAP ANALYSIS", filename)
    state["current_stage"] = "QUALITY ANALYSIS"
    _push_stage_event(state, "QUALITY ANALYSIS", filename)
    state["current_stage"] = "GENERATING ANNOTATIONS"
    _push_stage_event(state, "GENERATING ANNOTATIONS", filename)
    state["current_stage"] = "GENERATING AIRTABLE RECORD"
    _push_stage_event(state, "GENERATING AIRTABLE RECORD", filename)
    state["current_stage"] = "GENERATING EMAIL NOTIFICATION"
    _push_stage_event(state, "GENERATING EMAIL NOTIFICATION", filename)

    _persist_simulation_artifacts(workflow)
    state["jobs"].append(_build_job_result(filename, workflow))
    state["current_stage"] = "COMPLETED"
    _push_stage_event(state, "COMPLETED", filename)


def ingest_sample_dataset(db: Session, force: bool = False) -> dict:
    if not _dataset_dir().exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample dataset folder not found.")

    state = _load_state()
    _refresh_queue(state, force=force)
    _process_one_file(db=db, state=state)
    state["last_run"] = _now_iso()
    _save_state(state)
    return get_ingestion_status()


def get_ingestion_status() -> dict:
    state = _load_state()
    return {
        "last_run": state.get("last_run"),
        "jobs": state.get("jobs", []),
        "summary": _build_dashboard_summary(state),
        "pipeline_stages": PIPELINE_STAGES,
        "stage_events": state.get("stage_events", []),
        "current_stage": state.get("current_stage", "IDLE"),
        "current_file": state.get("current_file"),
    }


def get_ops_summary() -> dict:
    status_payload = get_ingestion_status()
    return {
        "dataset_last_run": status_payload.get("last_run"),
        "ingestion_summary": status_payload.get("summary", {}),
    }
