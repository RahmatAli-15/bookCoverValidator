from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.cover_job import CoverJob
from app.schemas.cover import CoverWorkflowResponse, OperationalSummary, PipelineState, TimingMetrics
from app.services.airtable_service import sync_airtable_report
from app.services.analysis_service import build_ai_layout_analysis, compute_publishing_readiness
from app.services.author_metadata_service import get_author_metadata
from app.services.cover_processing_service import process_cover_job
from app.services.cover_upload_service import create_cover_upload_job
from app.services.cover_validation_service import validate_cover_job
from app.services.notification_service import build_notification
from app.core.config import settings

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _max_severity(issues: list[dict]) -> str:
    if not issues:
        return "NONE"
    if any(i.get("severity") == "HIGH" for i in issues):
        return "HIGH"
    if any(i.get("severity") == "MEDIUM" for i in issues):
        return "MEDIUM"
    return "LOW"


def _save_report(job_id: int, payload: dict) -> None:
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    ts = _now().strftime("%Y%m%d%H%M%S%f")
    (settings.reports_dir / f"job_{job_id}_{ts}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _save_notification(job_id: int, payload: dict) -> None:
    settings.notifications_dir.mkdir(parents=True, exist_ok=True)
    ts = _now().strftime("%Y%m%d%H%M%S%f")
    (settings.notifications_dir / f"job_{job_id}_{ts}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _extract_timing(ocr_result: dict, validation_result: dict, total_ms: int) -> TimingMetrics:
    ocr_timing = ocr_result.get("timing_metrics")
    val_timing = validation_result.get("timing_metrics")

    image_load_ms = int(getattr(ocr_timing, "image_load_ms", 0)) if ocr_timing is not None else 0
    preprocess_ms = int(getattr(ocr_timing, "preprocess_ms", 0)) if ocr_timing is not None else 0
    ocr_ms = int(getattr(ocr_timing, "ocr_ms", 0)) if ocr_timing is not None else 0
    validation_ms = int(getattr(val_timing, "validation_ms", 0)) if val_timing is not None else 0

    logger.info(
        "Timing metrics object validation: ocr_timing=%s validation_timing=%s",
        type(ocr_timing).__name__,
        type(val_timing).__name__,
    )

    timing = TimingMetrics(
        image_load_ms=image_load_ms,
        preprocess_ms=preprocess_ms,
        ocr_ms=ocr_ms,
        validation_ms=validation_ms,
        total_pipeline_ms=total_ms,
    )
    logger.info("Workflow timing extraction success: %s", timing.model_dump())
    return timing


def run_automated_workflow(db: Session, upload: UploadFile) -> CoverWorkflowResponse:
    timer_start = time.perf_counter()
    start = _now()
    states: list[PipelineState] = []

    job: CoverJob = create_cover_upload_job(db=db, upload=upload)
    states.append(PipelineState(state="uploaded", timestamp=_now()))
    states.append(PipelineState(state="processing", timestamp=_now()))

    ocr_result = process_cover_job(db=db, job_id=job.id)
    states.append(PipelineState(state="ocr_complete", timestamp=_now()))

    validation_result = validate_cover_job(db=db, job_id=job.id)
    states.append(PipelineState(state="validation_complete", timestamp=_now()))

    elapsed = int((_now() - start).total_seconds() * 1000)
    issues = validation_result.get("issues", [])
    quality = ocr_result["quality_metrics"].model_dump() if hasattr(ocr_result["quality_metrics"], "model_dump") else ocr_result["quality_metrics"]
    overlap = float(validation_result["confidence"]["overlap_certainty"])
    ocr_conf = float(validation_result["confidence"]["ocr_confidence"])

    readiness = compute_publishing_readiness(ocr_conf, overlap, quality, issues)
    ai_layout_analysis = build_ai_layout_analysis(validation_result["status"], issues, quality)

    summary = OperationalSummary(
        validation_status=validation_result["status"],
        overall_confidence=float(validation_result["confidence"]["overall_validation_confidence"]),
        issue_severity=_max_severity(issues),
        processing_time_ms=elapsed,
        detected_issue_count=len(issues),
    )

    author = get_author_metadata(job.isbn)
    notification = build_notification(validation_result["status"], author.author_name, author.author_email, issues, readiness)
    _save_notification(job.id, notification)

    job.status = "report_generated"
    db.commit()
    states.append(PipelineState(state="report_generated", timestamp=_now()))

    total_pipeline_ms = int((time.perf_counter() - timer_start) * 1000)
    timing_metrics = _extract_timing(ocr_result=ocr_result, validation_result=validation_result, total_ms=total_pipeline_ms)

    draft_report = {
        "success": True,
        "job_id": job.id,
        "isbn": job.isbn,
        "file_name": job.filename,
        "file_type": job.file_type,
        "file_path": job.file_path,
        "pipeline_states": [s.model_dump(mode="json") for s in states],
        "detected_text_count": ocr_result["detected_text_count"],
        "extracted_text_blocks": [b.model_dump() if hasattr(b, "model_dump") else b for b in ocr_result["extracted_text_blocks"]],
        "ocr_confidence_summary": ocr_result["confidence_summary"].model_dump() if hasattr(ocr_result["confidence_summary"], "model_dump") else ocr_result["confidence_summary"],
        "validation": validation_result,
        "quality_metrics": ocr_result["quality_metrics"].model_dump() if hasattr(ocr_result["quality_metrics"], "model_dump") else ocr_result["quality_metrics"],
        "operational_summary": summary.model_dump(),
        "ai_layout_analysis": ai_layout_analysis,
        "publishing_readiness_score": readiness,
        "author": author.model_dump(),
        "notification": notification,
        "timing_metrics": timing_metrics.model_dump(),
        "revision_history_preview": f"job_{job.id}_latest",
    }

    airtable_sync_raw = sync_airtable_report(draft_report)
    airtable_sync = {
        "status": airtable_sync_raw.get("status", "failed"),
        "message": airtable_sync_raw.get("message", "Unknown sync result."),
        "record_id": airtable_sync_raw.get("record_id"),
        "fields": airtable_sync_raw.get("fields", {}),
    }

    response = CoverWorkflowResponse(
        success=True,
        job_id=job.id,
        isbn=job.isbn,
        file_name=job.filename,
        file_type=job.file_type,
        file_path=job.file_path,
        pipeline_states=states,
        detected_text_count=ocr_result["detected_text_count"],
        extracted_text_blocks=ocr_result["extracted_text_blocks"],
        ocr_confidence_summary=ocr_result["confidence_summary"],
        validation=validation_result,
        quality_metrics=ocr_result["quality_metrics"],
        operational_summary=summary,
        ai_layout_analysis=ai_layout_analysis,
        publishing_readiness_score=readiness,
        author=author,
        notification=notification,
        airtable_sync=airtable_sync,
        timing_metrics=timing_metrics,
    )

    _save_report(job.id, response.model_dump(mode="json"))
    return response
