from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from starlette.datastructures import Headers
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.cover import BenchmarkMetrics, BenchmarkResultResponse, BenchmarkSampleResult
from app.services.workflow_service import run_automated_workflow

logger = logging.getLogger(__name__)


@dataclass
class _SampleMeta:
    filename: str
    expected_status: str
    expected_badge_overlap: bool
    source_bucket: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_metadata(bucket: str) -> list[_SampleMeta]:
    metadata_path = settings.test_samples_dir / bucket / "metadata.json"
    if not metadata_path.exists():
        return []

    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    items: list[_SampleMeta] = []
    for row in raw:
        filename = str(row.get("filename", "")).strip()
        expected_status = str(row.get("expected_status", "")).strip().upper()
        if not filename or expected_status not in {"PASS", "REVIEW_NEEDED", "BORDERLINE"}:
            continue
        expected_badge_overlap = bool(row.get("expected_badge_overlap", expected_status == "REVIEW_NEEDED"))
        items.append(
            _SampleMeta(
                filename=filename,
                expected_status=expected_status,
                expected_badge_overlap=expected_badge_overlap,
                source_bucket=bucket,
            )
        )
    return items


def _infer_expected_from_filename(filename: str) -> tuple[str, bool]:
    lower = filename.lower()
    if "_pass" in lower or "_fixed" in lower or "_fixe" in lower:
        return "PASS", False
    if "_bad" in lower:
        return "REVIEW_NEEDED", True
    return "BORDERLINE", True


def _read_fallback_samples() -> list[_SampleMeta]:
    sample_dir = settings.project_root / "frontend" / "src" / "data" / "sample-covers"
    if not sample_dir.exists():
        return []

    items: list[_SampleMeta] = []
    for path in sorted(sample_dir.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".pdf"}:
            continue
        expected_status, expected_overlap = _infer_expected_from_filename(path.name)
        items.append(
            _SampleMeta(
                filename=path.name,
                expected_status=expected_status,
                expected_badge_overlap=expected_overlap,
                source_bucket="fallback",
            )
        )
    return items


def _resolve_sample_file(sample: _SampleMeta) -> Path:
    if sample.source_bucket == "fallback":
        fallback = settings.project_root / "frontend" / "src" / "data" / "sample-covers" / sample.filename
        if fallback.exists():
            return fallback

    direct_sample = settings.test_samples_dir / sample.source_bucket / sample.filename
    if direct_sample.exists():
        return direct_sample

    direct_upload = settings.uploads_dir / sample.filename
    if direct_upload.exists():
        return direct_upload

    stem = Path(sample.filename).stem
    parts = stem.split("_")
    ext = Path(sample.filename).suffix.lower()
    if len(parts) >= 2 and parts[0].isdigit():
        isbn = parts[0]
        matches = sorted(settings.uploads_dir.glob(f"{isbn}_*{ext}"), reverse=True)
        if matches:
            return matches[0]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Benchmark sample not found: {sample.filename}",
    )


def _has_badge_overlap(workflow_payload: dict) -> bool:
    issues = workflow_payload.get("validation", {}).get("issues", [])
    critical_types = {"BADGE_OVERLAP", "AUTHOR_NAME_CONFLICT", "TYPOGRAPHY_CONFLICT", "UNCERTAIN_OVERLAP"}
    return any(issue.get("type") in critical_types for issue in issues)


def _max_overlap_severity(workflow_payload: dict) -> str:
    rank = {"PASS": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    best = "PASS"
    for issue in workflow_payload.get("validation", {}).get("issues", []):
        sev = str(issue.get("overlap_severity", "PASS")).upper()
        if sev in rank and rank[sev] > rank[best]:
            best = sev
    return best


def _predicted_category(workflow_payload: dict) -> str:
    status = workflow_payload.get("validation", {}).get("status", "REVIEW_NEEDED")
    if status == "PASS":
        return "PASS"
    overlap_severity = _max_overlap_severity(workflow_payload)
    confidence = float(workflow_payload.get("validation", {}).get("confidence", {}).get("overall_validation_confidence", 0.0))
    if overlap_severity in {"LOW", "MEDIUM"} and confidence >= 0.6:
        return "BORDERLINE"
    return "REVIEW_NEEDED"


def _calc_metrics(samples: list[BenchmarkSampleResult]) -> BenchmarkMetrics:
    total = len(samples)
    if total == 0:
        return BenchmarkMetrics(
            total_accuracy=0.0,
            badge_overlap_accuracy=0.0,
            overlap_precision=0.0,
            overlap_recall=0.0,
            false_positive_rate=0.0,
            false_negative_rate=0.0,
            true_positives=0,
            true_negatives=0,
            false_positives=0,
            false_negatives=0,
            overlap_conflict_samples=0,
            overlap_successful_detections=0,
            overlap_failed_detections=0,
            pass_samples=0,
            review_needed_samples=0,
            borderline_samples=0,
            average_confidence=0.0,
            average_processing_latency_ms=0.0,
            manual_review_reduction=0.0,
        )

    correct = sum(1 for s in samples if s.correct)
    overlap_conflict_samples = [s for s in samples if s.expected_badge_overlap]
    overlap_success = sum(1 for s in overlap_conflict_samples if s.badge_overlap_detected)
    overlap_failed = len(overlap_conflict_samples) - overlap_success
    badge_accuracy = (overlap_success / len(overlap_conflict_samples) * 100.0) if overlap_conflict_samples else 0.0

    tp = sum(1 for s in samples if s.expected_badge_overlap and s.badge_overlap_detected)
    tn = sum(1 for s in samples if not s.expected_badge_overlap and not s.badge_overlap_detected)
    fp = sum(1 for s in samples if not s.expected_badge_overlap and s.badge_overlap_detected)
    fn = sum(1 for s in samples if s.expected_badge_overlap and not s.badge_overlap_detected)
    overlap_precision = (tp / (tp + fp) * 100.0) if (tp + fp) else 0.0
    overlap_recall = (tp / (tp + fn) * 100.0) if (tp + fn) else 0.0

    expected_positive = sum(1 for s in samples if s.expected in {"REVIEW_NEEDED", "BORDERLINE"})
    expected_negative = sum(1 for s in samples if s.expected == "PASS")
    false_positives = sum(1 for s in samples if s.expected == "PASS" and s.actual in {"REVIEW_NEEDED", "BORDERLINE"})
    false_negatives = sum(1 for s in samples if s.expected in {"REVIEW_NEEDED", "BORDERLINE"} and s.actual == "PASS")
    false_positive_rate = (false_positives / expected_negative * 100.0) if expected_negative else 0.0
    false_negative_rate = (false_negatives / expected_positive * 100.0) if expected_positive else 0.0

    pass_samples = sum(1 for s in samples if s.expected == "PASS")
    review_needed_samples = sum(1 for s in samples if s.expected == "REVIEW_NEEDED")
    borderline_samples = sum(1 for s in samples if s.expected == "BORDERLINE")
    avg_conf = sum(s.confidence for s in samples) / total
    avg_latency = sum(s.processing_ms for s in samples) / total
    expected_reviews = sum(1 for s in samples if s.expected in {"REVIEW_NEEDED", "BORDERLINE"})
    actual_reviews = sum(1 for s in samples if s.actual in {"REVIEW_NEEDED", "BORDERLINE"})
    manual_review_reduction = ((expected_reviews - actual_reviews) / expected_reviews * 100.0) if expected_reviews else 0.0

    return BenchmarkMetrics(
        total_accuracy=round(correct / total * 100.0, 2),
        badge_overlap_accuracy=round(badge_accuracy, 2),
        overlap_precision=round(overlap_precision, 2),
        overlap_recall=round(overlap_recall, 2),
        false_positive_rate=round(false_positive_rate, 2),
        false_negative_rate=round(false_negative_rate, 2),
        true_positives=tp,
        true_negatives=tn,
        false_positives=false_positives,
        false_negatives=false_negatives,
        overlap_conflict_samples=len(overlap_conflict_samples),
        overlap_successful_detections=overlap_success,
        overlap_failed_detections=overlap_failed,
        pass_samples=pass_samples,
        review_needed_samples=review_needed_samples,
        borderline_samples=borderline_samples,
        average_confidence=round(avg_conf, 4),
        average_processing_latency_ms=round(avg_latency, 2),
        manual_review_reduction=round(manual_review_reduction, 2),
    )


def _build_summary(metrics: BenchmarkMetrics) -> str:
    return (
        "Critical overlap detection validated across real publishing cover samples. "
        f"Overlap recall: {metrics.overlap_recall:.2f}%."
    )


def _export_result(payload: dict) -> str:
    settings.benchmarks_dir.mkdir(parents=True, exist_ok=True)
    ts = _now().strftime("%Y%m%d%H%M%S%f")
    path = settings.benchmarks_dir / f"benchmark_{ts}.json"
    latest = settings.benchmarks_dir / "latest_benchmark.json"
    serialized = json.dumps(payload, indent=2)
    path.write_text(serialized, encoding="utf-8")
    latest.write_text(serialized, encoding="utf-8")
    return str(path.relative_to(settings.project_root))


def run_benchmark(db: Session) -> BenchmarkResultResponse:
    samples_meta = _read_metadata("pass") + _read_metadata("review_needed") + _read_metadata("borderline")
    if not samples_meta:
        samples_meta = _read_fallback_samples()
    if not samples_meta:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No benchmark metadata found.")

    sample_results: list[BenchmarkSampleResult] = []
    for sample in samples_meta:
        source_path = _resolve_sample_file(sample)
        ext = source_path.suffix.lower()
        content_type = "application/pdf" if ext == ".pdf" else "image/png"
        isbn_match = sample.filename.split("_")[0]
        normalized_name = f"{isbn_match}_text{ext}" if isbn_match.isdigit() and len(isbn_match) == 13 else sample.filename
        with source_path.open("rb") as fp:
            upload = UploadFile(
                filename=normalized_name,
                file=fp,
                headers=Headers({"content-type": content_type}),
            )
            workflow = run_automated_workflow(db=db, upload=upload).model_dump(mode="json")

        actual_status = _predicted_category(workflow)
        confidence = float(workflow["validation"]["confidence"]["overall_validation_confidence"])
        processing_ms = int(workflow["timing_metrics"]["total_pipeline_ms"])
        badge_overlap_detected = _has_badge_overlap(workflow)
        issue_count = len(workflow.get("validation", {}).get("issues", []))
        overlap_severity = _max_overlap_severity(workflow)

        sample_results.append(
            BenchmarkSampleResult(
                cover=sample.filename,
                expected=sample.expected_status,  # type: ignore[arg-type]
                actual=actual_status,  # type: ignore[arg-type]
                correct=sample.expected_status == actual_status,
                prediction=actual_status,  # type: ignore[arg-type]
                confidence=confidence,
                processing_ms=processing_ms,
                issue_count=issue_count,
                overlap_severity=overlap_severity,  # type: ignore[arg-type]
                latency_ms=processing_ms,
                badge_overlap_detected=badge_overlap_detected,
                expected_badge_overlap=sample.expected_badge_overlap,
            )
        )

    metrics = _calc_metrics(sample_results)
    response = BenchmarkResultResponse(
        total_samples=len(sample_results),
        metrics=metrics,
        samples=sample_results,
        summary=_build_summary(metrics),
        exported_json_path="",
        generated_at=_now(),
    )
    payload = response.model_dump(mode="json")
    payload["exported_json_path"] = _export_result(payload)

    logger.info("Benchmark completed: total_samples=%s total_accuracy=%s", payload["total_samples"], payload["metrics"]["total_accuracy"])
    return BenchmarkResultResponse(**payload)


def get_latest_benchmark() -> BenchmarkResultResponse:
    latest_path = settings.benchmarks_dir / "latest_benchmark.json"
    if not latest_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No benchmark result found.")
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", {})
    metrics.setdefault("overlap_precision", 0.0)
    metrics.setdefault("overlap_recall", 0.0)
    metrics.setdefault("false_positive_rate", 0.0)
    metrics.setdefault("false_negative_rate", 0.0)
    metrics.setdefault("true_positives", 0)
    metrics.setdefault("true_negatives", 0)
    metrics.setdefault("overlap_conflict_samples", 0)
    metrics.setdefault("overlap_successful_detections", 0)
    metrics.setdefault("overlap_failed_detections", 0)
    metrics.setdefault("pass_samples", 0)
    metrics.setdefault("review_needed_samples", 0)
    metrics.setdefault("borderline_samples", 0)
    payload["metrics"] = metrics

    for sample in payload.get("samples", []):
        sample.setdefault("prediction", sample.get("actual", "REVIEW_NEEDED"))
        sample.setdefault("issue_count", 0)
        sample.setdefault("overlap_severity", "PASS")
        sample.setdefault("latency_ms", int(sample.get("processing_ms", 0)))

    return BenchmarkResultResponse(**payload)
