from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cover_job import CoverJob
from app.schemas.cover import ComplianceCheck, TimingMetrics, ValidationConfidence, ValidationIssue
from app.services.analysis_service import suggested_correction
from app.utils.image_processing import ImageProcessingError, PDFProcessingError, load_pdf_first_page_as_bgr, load_png_as_bgr

Rect = tuple[float, float, float, float]


def _resolve_upload_path(file_path: str) -> Path:
    return settings.project_root / file_path


def _load_latest_ocr_payload(job_id: int) -> dict:
    matches = sorted(settings.ocr_results_dir.glob(f"job_{job_id}_*.json"), reverse=True)
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR result not found. Process cover before validation.")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def _load_image_for_validation(job: CoverJob, ocr_payload: dict):
    rendered_rel = ocr_payload.get("rendered_image_path")
    if rendered_rel:
        rendered_abs = settings.project_root / rendered_rel
        if rendered_abs.exists():
            image = cv2.imread(str(rendered_abs))
            if image is not None:
                return image
    upload_path = _resolve_upload_path(job.file_path)
    return load_pdf_first_page_as_bgr(upload_path, scale=1.3) if job.file_type == "pdf" else load_png_as_bgr(upload_path)


def _mm_to_px(width: int, height: int, mm_x: float, mm_y: float) -> tuple[float, float]:
    px_per_mm_x = width / settings.COVER_REFERENCE_WIDTH_MM
    px_per_mm_y = height / settings.COVER_REFERENCE_HEIGHT_MM
    return mm_x * px_per_mm_x, mm_y * px_per_mm_y


def _safe_zones(width: int, height: int) -> dict[str, Rect]:
    margin_x, _ = _mm_to_px(width, height, settings.SAFE_MARGIN_MM, settings.SAFE_MARGIN_MM)
    _, badge_h = _mm_to_px(width, height, settings.BADGE_ZONE_HEIGHT_MM, settings.BADGE_ZONE_HEIGHT_MM)
    _, badge_pad = _mm_to_px(width, height, settings.BADGE_ZONE_PADDING_MM, settings.BADGE_ZONE_PADDING_MM)
    critical_y = float(height - (badge_h + badge_pad))
    return {
        "safe_area": (margin_x, 0.0, float(width - margin_x), critical_y),
        "left_margin": (0.0, 0.0, margin_x, float(height)),
        "right_margin": (float(width - margin_x), 0.0, float(width), float(height)),
        "critical_badge_zone": (0.0, critical_y, float(width), float(height)),
    }


def _intersection_area(a: Rect, b: Rect) -> float:
    x1 = max(a[0], b[0]); y1 = max(a[1], b[1]); x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return float((x2 - x1) * (y2 - y1))


def _intersection_ratio(a: Rect, b: Rect) -> float:
    inter = _intersection_area(a, b)
    area_a = max((a[2] - a[0]) * (a[3] - a[1]), 1.0)
    return inter / area_a


def _overlap_severity(overlap_percentage: float) -> tuple[str, str]:
    if overlap_percentage <= 0:
        return "PASS", "LOW"
    if overlap_percentage <= 10:
        return "LOW", "LOW"
    if overlap_percentage <= 25:
        return "MEDIUM", "MEDIUM"
    if overlap_percentage <= 40:
        return "HIGH", "HIGH"
    return "CRITICAL", "CRITICAL"


def _draw_overlay(img, rect: Rect, color: tuple[int, int, int], alpha: float) -> None:
    x1, y1, x2, y2 = map(int, rect)
    if x2 <= x1 or y2 <= y1:
        return
    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)


def _draw_label(img, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    x = max(2, min(x, img.shape[1] - tw - 4))
    y = max(th + 4, min(y, img.shape[0] - baseline - 2))
    cv2.rectangle(img, (x - 2, y - th - 2), (x + tw + 2, y + baseline), (255, 255, 255), -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def _estimate_shift_px(bbox: list[float], zone: Rect) -> str:
    if bbox[3] <= zone[1]:
        return "No vertical movement required."
    move = int(bbox[3] - zone[1] + 16)
    return f"Recommended adjustment: move text {move}-{move + 10}px upward."


def _detect_visual_text_in_badge_zone(image, badge_zone: Rect) -> tuple[bool, float, list[float]]:
    x1, y1, x2, y2 = [int(v) for v in badge_zone]
    if x2 <= x1 or y2 <= y1:
        return False, 0.0, [0.0, 0.0, 0.0, 0.0]

    roi = image[y1:y2, x1:x2]
    if roi.size == 0:
        return False, 0.0, [0.0, 0.0, 0.0, 0.0]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    bw_dark = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 7)
    bw_light = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 7)
    mask = cv2.bitwise_or(bw_dark, cv2.bitwise_not(bw_light))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 2))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    text_like = 0
    text_area = 0.0
    best = (0, 0, 0, 0, 0.0)
    for c in contours:
        bx, by, bw, bh = cv2.boundingRect(c)
        area = float(bw * bh)
        if area < 25 or area > 8000:
            continue
        if bh < 5 or bh > 90:
            continue
        if bw < 8:
            continue
        ratio = bw / max(bh, 1)
        if ratio < 0.8:
            continue
        text_like += 1
        text_area += area
        if area > best[4]:
            best = (bx, by, bw, bh, area)

    roi_area = float(max(roi.shape[0] * roi.shape[1], 1))
    density = text_area / roi_area
    certainty = min(1.0, (density * 36.0) + (text_like * 0.1))
    found = text_like >= 2 and density > 0.002

    if best[4] > 0:
        bx, by, bw, bh, _ = best
        bbox = [float(x1 + bx), float(y1 + by), float(x1 + bx + bw), float(y1 + by + bh)]
    else:
        bbox = [float(x1), float(y1), float(x2), float(y2)]

    return found, round(certainty, 4), bbox


def _build_issue(issue_type: str, severity: str, text: str, bbox: list[float], message: str, overlap_certainty: float, overlap_percentage: float, badge_zone: Rect) -> ValidationIssue:
    issue_conf = round(max(0.0, min(1.0, (overlap_certainty * 0.65) + 0.35)), 4)
    overlap_sev, default_severity = _overlap_severity(overlap_percentage)
    return ValidationIssue(
        type=issue_type,
        severity=(severity or default_severity),
        text=text,
        bbox=bbox,
        message=message,
        overlap_certainty=round(overlap_certainty, 4),
        overlap_percentage=round(overlap_percentage, 2),
        overlap_severity=overlap_sev,
        conflicting_text=text,
        badge_zone_coordinates=[float(badge_zone[0]), float(badge_zone[1]), float(badge_zone[2]), float(badge_zone[3])],
        suggested_correction=suggested_correction(issue_type),
        issue_confidence=issue_conf,
    )


def validate_cover_job(db: Session, job_id: int) -> dict:
    validation_start = time.perf_counter()
    job = db.get(CoverJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover job not found.")
    if job.status not in {"ocr_complete", "validation_complete", "report_generated"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cover must complete OCR before validation.")

    ocr_payload = _load_latest_ocr_payload(job_id)
    quality = ocr_payload.get("quality_metrics", {})

    try:
        image = _load_image_for_validation(job, ocr_payload)
    except (PDFProcessingError, ImageProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    h, w = image.shape[:2]
    zones = _safe_zones(w, h)
    issues: list[ValidationIssue] = []
    ocr_conf = float(ocr_payload.get("confidence_summary", {}).get("average", 0.0))
    overlaps: list[float] = []
    correction_recommendations: list[str] = []

    for block in ocr_payload.get("extracted_text_blocks", []):
        text = str(block.get("text", "")).strip()
        if len(text) < 3:
            continue
        bbox = [float(v) for v in block.get("bbox", [0, 0, 0, 0])]
        rect: Rect = (bbox[0], bbox[1], bbox[2], bbox[3])

        overlap_ratio = _intersection_ratio(rect, zones["critical_badge_zone"])
        overlap_pct = overlap_ratio * 100.0
        if overlap_ratio > 0:
            overlaps.append(overlap_ratio)
            if "author" in text.lower():
                msg = "Move author name above reserved Emily Dickinson Award area."
            elif any(k in text.lower() for k in ["subtitle", "edition"]):
                msg = "Increase spacing between subtitle and badge zone."
            else:
                msg = "Typography enters protected badge zone."

            issue_type = "BADGE_OVERLAP" if ("author" in text.lower() or "subtitle" in text.lower()) else "TYPOGRAPHY_CONFLICT"
            _, sev = _overlap_severity(overlap_pct)
            issues.append(_build_issue(issue_type, sev, text, bbox, msg, overlap_ratio, overlap_pct, zones["critical_badge_zone"]))
            correction_recommendations.append(_estimate_shift_px(bbox, zones["critical_badge_zone"]))

        left_overlap = _intersection_ratio(rect, zones["left_margin"])
        right_overlap = _intersection_ratio(rect, zones["right_margin"])
        margin_overlap = max(left_overlap, right_overlap)
        if margin_overlap > 0:
            overlaps.append(margin_overlap)
            margin_msg = "Text violates left safe margin." if left_overlap > right_overlap else "Text violates right safe margin."
            _, margin_sev = _overlap_severity(margin_overlap * 100.0)
            issues.append(_build_issue("SAFE_MARGIN_VIOLATION", margin_sev, text, bbox, margin_msg, margin_overlap, margin_overlap * 100.0, zones["critical_badge_zone"]))

    if ocr_conf < 0.70:
        issues.append(_build_issue("LOW_OCR_CONFIDENCE", "MEDIUM", "", [0, 0, 0, 0], "OCR confidence too low for reliable validation", max(0.0, 0.7 - ocr_conf), 0.0, zones["critical_badge_zone"]))

    resolution_low = not quality.get("resolution_ok", True)
    blur_critical = float(quality.get("blur_score", 999.0)) < 30.0
    readability_impacted = float(quality.get("small_text_ratio", 0.0)) > 0.55
    ocr_poor = ocr_conf < 0.62
    low_quality = ((resolution_low and (ocr_poor or readability_impacted)) or (blur_critical and (ocr_poor or readability_impacted)) or (readability_impacted and ocr_poor))
    if low_quality:
        issues.append(_build_issue("LOW_IMAGE_QUALITY", "MEDIUM", "", [0, 0, 0, 0], "Blurry/low-quality image may reduce layout validation reliability", 0.5, 0.0, zones["critical_badge_zone"]))

    visual_overlap_found, visual_certainty, visual_bbox = _detect_visual_text_in_badge_zone(image, zones["critical_badge_zone"])
    if visual_overlap_found and not any(i.type in {"BADGE_OVERLAP", "TYPOGRAPHY_CONFLICT"} for i in issues):
        overlaps.append(visual_certainty)
        issues.append(
            _build_issue(
                "UNCERTAIN_OVERLAP",
                "HIGH",
                "Undetected typography in protected badge zone",
                visual_bbox,
                "Text-like pattern detected in reserved badge area; manual review required.",
                visual_certainty,
                min(100.0, visual_certainty * 100.0),
                zones["critical_badge_zone"],
            )
        )
        correction_recommendations.append(_estimate_shift_px(visual_bbox, zones["critical_badge_zone"]))

    has_major_typography_conflict = any(i.type == "TYPOGRAPHY_CONFLICT" and i.severity in {"HIGH", "CRITICAL"} for i in issues)
    avg_overlap = round(sum(overlaps) / len(overlaps), 4) if overlaps else 0.0
    overall_conf = round(max(0.0, min(1.0, (ocr_conf * 0.7) + ((1 - avg_overlap) * 0.3))), 4)
    blocking_issue_types = {"BADGE_OVERLAP", "TYPOGRAPHY_CONFLICT", "SAFE_MARGIN_VIOLATION", "LOW_OCR_CONFIDENCE", "UNCERTAIN_OVERLAP"}
    has_blocking_issue = any(i.type in blocking_issue_types for i in issues)
    status_value = "REVIEW_NEEDED" if has_blocking_issue or has_major_typography_conflict else "PASS"
    if any(i.severity in {"HIGH", "CRITICAL"} for i in issues):
        overall_conf = round(max(0.0, overall_conf - 0.2), 4)

    confidence = ValidationConfidence(ocr_confidence=round(ocr_conf, 4), overlap_certainty=avg_overlap, overall_validation_confidence=overall_conf)

    has_badge_conflict = any(i.type in {"BADGE_OVERLAP", "TYPOGRAPHY_CONFLICT"} for i in issues)
    has_margin_conflict = any(i.type == "SAFE_MARGIN_VIOLATION" for i in issues)
    ocr_readable = ocr_conf >= 0.70 and not any(i.type == "LOW_OCR_CONFIDENCE" for i in issues)
    layout_clear = not any(i.type in {"TYPOGRAPHY_CONFLICT", "UNCERTAIN_OVERLAP"} for i in issues)
    resolution_ok = bool(quality.get("resolution_ok", True)) and not any(i.type == "LOW_IMAGE_QUALITY" for i in issues)

    safe_zone_compliance = [
        ComplianceCheck(rule="Badge Safe Zone", passed=not has_badge_conflict, message="Reserved badge zone is unobstructed." if not has_badge_conflict else "Typography overlaps protected award region."),
        ComplianceCheck(rule="Typography Margins", passed=not has_margin_conflict, message="Typography stays within safe margins." if not has_margin_conflict else "Text enters unsafe border margins."),
        ComplianceCheck(rule="OCR Readability", passed=ocr_readable, message="OCR readability confidence is acceptable." if ocr_readable else "OCR confidence is low for reliable automation."),
        ComplianceCheck(rule="Layout Clarity", passed=layout_clear, message="Layout structure appears clear and balanced." if layout_clear else "Typography crowding detected near protected publishing region."),
        ComplianceCheck(rule="Resolution Quality", passed=resolution_ok, message="Resolution quality is production-ready." if resolution_ok else "Image quality may impact publishing validation."),
    ]

    if status_value == "PASS":
        publishing_decision = "Production Ready"
    elif has_badge_conflict or any(i.severity in {"CRITICAL", "HIGH"} for i in issues):
        publishing_decision = "Requires Manual Review"
    else:
        publishing_decision = "Needs Typography Adjustment"

    operational_guidance: list[str] = []
    if has_badge_conflict:
        operational_guidance.append("Move subtitle upward to restore award badge visibility.")
    if has_margin_conflict:
        operational_guidance.append("Typography crowding detected near protected publishing region.")
    if not ocr_readable:
        operational_guidance.append("Improve text clarity to increase OCR reliability before production approval.")
    if not operational_guidance:
        operational_guidance.append("Layout appears compliant with publishing production QA rules.")
    if not correction_recommendations and has_badge_conflict:
        correction_recommendations.append("Recommended adjustment: move subtitle 35-45px upward.")

    executive_summary = f"{publishing_decision}. Detected {len(issues)} issue(s); overall validation confidence {round(confidence.overall_validation_confidence * 100, 1)}%."

    annotated = image.copy()
    _draw_overlay(annotated, zones["safe_area"], (0, 170, 0), 0.12)
    _draw_overlay(annotated, zones["left_margin"], (0, 220, 220), 0.18)
    _draw_overlay(annotated, zones["right_margin"], (0, 220, 220), 0.18)
    _draw_overlay(annotated, zones["critical_badge_zone"], (0, 220, 220), 0.22)
    cv2.rectangle(annotated, (int(zones["critical_badge_zone"][0]), int(zones["critical_badge_zone"][1])), (int(zones["critical_badge_zone"][2]), int(zones["critical_badge_zone"][3])), (0, 200, 255), 2)
    _draw_label(annotated, "Critical Badge Zone - Emily Dickinson Award", int(zones["critical_badge_zone"][0]) + 14, int(zones["critical_badge_zone"][1]) + 22, (10, 90, 200))

    cv2.rectangle(annotated, (14, 14), (380, 126), (248, 248, 248), -1)
    _draw_label(annotated, "Severity Legend", 22, 35, (40, 40, 40))
    _draw_label(annotated, "LOW - Yellow", 22, 55, (0, 180, 230))
    _draw_label(annotated, "MEDIUM - Orange", 22, 73, (0, 140, 255))
    _draw_label(annotated, "HIGH - Red", 22, 91, (0, 0, 220))
    _draw_label(annotated, "CRITICAL - Dark Red", 22, 109, (0, 0, 140))

    label_rows: dict[int, int] = {}
    for issue in issues:
        rect = (issue.bbox[0], issue.bbox[1], issue.bbox[2], issue.bbox[3])
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            continue
        if issue.severity == "CRITICAL":
            color = (0, 0, 140)
        elif issue.severity == "HIGH":
            color = (0, 0, 255)
        elif issue.severity == "MEDIUM":
            color = (0, 140, 255)
        else:
            color = (0, 230, 230)
        _draw_overlay(annotated, rect, color, 0.16)
        cv2.rectangle(annotated, (int(rect[0]), int(rect[1])), (int(rect[2]), int(rect[3])), color, 2)
        lane = int(rect[1] // 28)
        lane_count = label_rows.get(lane, 0)
        label_rows[lane] = lane_count + 1
        _draw_label(annotated, f"{issue.type}:{issue.overlap_percentage}%", int(rect[0]) + 4, max(20, int(rect[1]) - 8 - (lane_count * 16)), color)

    settings.annotations_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    image_name = f"job_{job.id}_{ts}.png"
    image_abs = settings.annotations_dir / image_name
    image_rel = str(Path("storage") / "annotations" / image_name)
    cv2.imwrite(str(image_abs), annotated)

    existing_timing = ocr_payload.get("timing_metrics", {})
    timing_metrics = TimingMetrics(
        image_load_ms=int(existing_timing.get("image_load_ms", 0)),
        preprocess_ms=int(existing_timing.get("preprocess_ms", 0)),
        ocr_ms=int(existing_timing.get("ocr_ms", 0)),
        validation_ms=int((time.perf_counter() - validation_start) * 1000),
        total_pipeline_ms=int(existing_timing.get("total_pipeline_ms", 0)),
    )

    result_payload = {
        "job_id": job.id,
        "status": status_value,
        "issues": [item.model_dump() for item in issues],
        "confidence": confidence.model_dump(),
        "annotated_image_path": image_rel,
        "publishing_decision": publishing_decision,
        "executive_summary": executive_summary,
        "operational_guidance": operational_guidance,
        "correction_recommendations": correction_recommendations,
        "safe_zone_compliance": [c.model_dump() for c in safe_zone_compliance],
        "timing_metrics": timing_metrics.model_dump(),
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    (settings.annotations_dir / f"job_{job.id}_{ts}.json").write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    job.status = "validation_complete"
    db.commit()
    return result_payload


def get_latest_annotation_path(job_id: int) -> Path:
    matches = sorted(settings.annotations_dir.glob(f"job_{job_id}_*.png"), reverse=True)
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotated image not found for this job.")
    return matches[0]
