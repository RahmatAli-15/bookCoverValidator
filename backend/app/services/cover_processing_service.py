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
from app.schemas.cover import OCRBlock, OCRConfidenceSummary, QualityMetrics, TimingMetrics
from app.services.ocr_manager import ocr_manager
from app.utils.ocr_text_cleanup import clean_ocr_text, is_major_typography_block
from app.utils.image_processing import (
    ImageProcessingError,
    PDFProcessingError,
    load_pdf_first_page_as_bgr,
    load_png_as_bgr,
    preprocess_for_ocr,
)

MIN_OCR_CONFIDENCE = 0.55
MIN_BOX_HEIGHT_PX = 12.0
MIN_BOX_WIDTH_PX = 20.0


def init_ocr_reader() -> None:
    ocr_manager.initialize()


def _resolve_upload_path(file_path: str) -> Path:
    return settings.project_root / file_path


def _flatten_bbox(points: list[list[float]]) -> list[float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]


def _summarize_confidences(confidences: list[float]) -> OCRConfidenceSummary:
    if not confidences:
        return OCRConfidenceSummary(average=0.0, minimum=0.0, maximum=0.0)
    return OCRConfidenceSummary(
        average=round(sum(confidences) / len(confidences), 4),
        minimum=round(min(confidences), 4),
        maximum=round(max(confidences), 4),
    )


def _estimate_dpi(width: int, height: int) -> float:
    dpi_x = width / (settings.COVER_REFERENCE_WIDTH_MM / 25.4)
    dpi_y = height / (settings.COVER_REFERENCE_HEIGHT_MM / 25.4)
    return round((dpi_x + dpi_y) / 2.0, 2)


def _load_source_image(job: CoverJob):
    path = _resolve_upload_path(job.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded file not found on storage.")
    if job.file_type == "pdf":
        return load_pdf_first_page_as_bgr(path, scale=1.3)
    if job.file_type == "png":
        return load_png_as_bgr(path)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type for processing.")


def _persist_rendered_image(job_id: int, image_bgr) -> str:
    settings.ocr_results_dir.mkdir(parents=True, exist_ok=True)
    rendered_name = f"job_{job_id}_rendered.jpg"
    rendered_abs = settings.ocr_results_dir / rendered_name
    cv2.imwrite(str(rendered_abs), image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return str(Path("storage") / "processed" / "ocr_results" / rendered_name)


def process_cover_job(db: Session, job_id: int) -> dict:
    total_start = time.perf_counter()
    job = db.get(CoverJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover job not found.")

    job.status = "processing"
    db.commit()

    try:
        load_start = time.perf_counter()
        source = _load_source_image(job)
        image_load_ms = int((time.perf_counter() - load_start) * 1000)

        h, w = source.shape[:2]
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        preprocess_start = time.perf_counter()
        processed = preprocess_for_ocr(source)
        preprocess_ms = int((time.perf_counter() - preprocess_start) * 1000)

        ocr_start = time.perf_counter()
        raw_results = ocr_manager.get_reader().readtext(processed)
        ocr_ms = int((time.perf_counter() - ocr_start) * 1000)

        blocks: list[OCRBlock] = []
        confidences: list[float] = []
        small_text_count = 0
        for bbox_points, text, confidence in raw_results:
            conf = float(confidence)
            if conf < MIN_OCR_CONFIDENCE:
                continue

            bbox = _flatten_bbox(bbox_points)
            box_w = bbox[2] - bbox[0]
            box_h = bbox[3] - bbox[1]
            if box_h < MIN_BOX_HEIGHT_PX or box_w < MIN_BOX_WIDTH_PX:
                continue

            cleaned = clean_ocr_text((text or "").strip())
            if not cleaned:
                continue

            if box_h < 14:
                small_text_count += 1

            # Keep only meaningful major typography blocks for publishing QA readability.
            if not is_major_typography_block(cleaned, box_h, h):
                continue

            blocks.append(OCRBlock(text=cleaned, confidence=round(conf, 4), bbox=bbox))
            confidences.append(conf)

        if not blocks:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="OCR completed but no readable text was detected.")

        summary = _summarize_confidences(confidences)
        quality_metrics = QualityMetrics(
            width_px=w,
            height_px=h,
            dpi_estimate=_estimate_dpi(w, h),
            blur_score=round(blur_score, 2),
            # Calibrated lower blur sensitivity to reduce false positives on textured covers.
            is_blurry=blur_score < 45.0,
            resolution_ok=(w >= 1000 and h >= 1400),
            small_text_ratio=round(small_text_count / max(len(blocks), 1), 4),
        )

        rendered_image_path = _persist_rendered_image(job.id, source)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        result_name = f"job_{job.id}_{timestamp}.json"
        result_abs_path = settings.ocr_results_dir / result_name
        result_rel_path = str(Path("storage") / "processed" / "ocr_results" / result_name)

        timing_metrics = TimingMetrics(
            image_load_ms=image_load_ms,
            preprocess_ms=preprocess_ms,
            ocr_ms=ocr_ms,
            validation_ms=0,
            total_pipeline_ms=int((time.perf_counter() - total_start) * 1000),
        )

        payload = {
            "job_id": job.id,
            "isbn": job.isbn,
            "filename": job.filename,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "detected_text_count": len(blocks),
            "confidence_summary": summary.model_dump(),
            "extracted_text_blocks": [b.model_dump() for b in blocks],
            "quality_metrics": quality_metrics.model_dump(),
            "timing_metrics": timing_metrics.model_dump(),
            "rendered_image_path": rendered_image_path,
        }
        result_abs_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        job.status = "ocr_complete"
        db.commit()

        return {
            "job_id": job.id,
            "status": job.status,
            "detected_text_count": len(blocks),
            "confidence_summary": summary,
            "extracted_text_blocks": blocks,
            "ocr_result_path": result_rel_path,
            "quality_metrics": quality_metrics,
            "timing_metrics": timing_metrics,
            "rendered_image_path": rendered_image_path,
        }
    except (PDFProcessingError, ImageProcessingError) as exc:
        job.status = "uploaded"
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except HTTPException:
        job.status = "uploaded"
        db.commit()
        raise
    except Exception as exc:
        job.status = "uploaded"
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="OCR processing failed.") from exc


def get_ocr_result(db: Session, job_id: int) -> dict:
    job = db.get(CoverJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover job not found.")

    matches = sorted(settings.ocr_results_dir.glob(f"job_{job.id}_*.json"), reverse=True)
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR result not found for this job.")

    payload = json.loads(matches[0].read_text(encoding="utf-8"))
    return {
        "job_id": payload["job_id"],
        "status": job.status,
        "detected_text_count": payload["detected_text_count"],
        "confidence_summary": payload["confidence_summary"],
        "extracted_text_blocks": payload["extracted_text_blocks"],
        "ocr_result_path": str(Path("storage") / "processed" / "ocr_results" / matches[0].name),
        "quality_metrics": payload.get("quality_metrics", {}),
        "timing_metrics": payload.get("timing_metrics", {}),
    }
