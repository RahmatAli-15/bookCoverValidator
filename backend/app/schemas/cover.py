from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PipelineState(BaseModel):
    state: Literal[
        "uploaded",
        "queued",
        "processing",
        "ocr_complete",
        "validation_complete",
        "annotations_generated",
        "airtable_synced",
        "notification_generated",
        "report_generated",
        "completed",
    ]
    timestamp: datetime


class OCRBlock(BaseModel):
    text: str
    confidence: float
    bbox: list[float]


class OCRConfidenceSummary(BaseModel):
    average: float
    minimum: float
    maximum: float


class QualityMetrics(BaseModel):
    width_px: int
    height_px: int
    dpi_estimate: float
    blur_score: float
    is_blurry: bool
    resolution_ok: bool
    small_text_ratio: float


class ValidationIssue(BaseModel):
    type: Literal[
        "BADGE_OVERLAP",
        "SAFE_MARGIN_VIOLATION",
        "TYPOGRAPHY_CONFLICT",
        "LOW_OCR_CONFIDENCE",
        "BORDERLINE_SPACING",
        "UNCERTAIN_OVERLAP",
        "LOW_IMAGE_QUALITY",
    ]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    text: str
    bbox: list[float]
    message: str
    overlap_certainty: float = 0.0
    overlap_percentage: float = 0.0
    overlap_severity: Literal["PASS", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = "PASS"
    conflicting_text: str = ""
    badge_zone_coordinates: list[float] = []
    suggested_correction: str = ""
    issue_confidence: float = 0.0


class ValidationConfidence(BaseModel):
    ocr_confidence: float
    overlap_certainty: float
    overall_validation_confidence: float


class ComplianceCheck(BaseModel):
    rule: Literal["Badge Safe Zone", "Typography Margins", "OCR Readability", "Layout Clarity", "Resolution Quality"]
    passed: bool
    message: str


class ValidationResult(BaseModel):
    status: Literal["PASS", "REVIEW_NEEDED"]
    issues: list[ValidationIssue]
    confidence: ValidationConfidence
    annotated_image_path: str
    publishing_decision: Literal["Production Ready", "Needs Typography Adjustment", "Requires Manual Review"] = "Requires Manual Review"
    executive_summary: str = ""
    operational_guidance: list[str] = []
    correction_recommendations: list[str] = []
    safe_zone_compliance: list[ComplianceCheck] = []


class OperationalSummary(BaseModel):
    validation_status: Literal["PASS", "REVIEW_NEEDED"]
    overall_confidence: float
    issue_severity: Literal["HIGH", "MEDIUM", "LOW", "NONE"]
    processing_time_ms: int
    detected_issue_count: int


class TimingMetrics(BaseModel):
    image_load_ms: int
    preprocess_ms: int
    ocr_ms: int
    validation_ms: int
    total_pipeline_ms: int


class AuthorMetadata(BaseModel):
    author_name: str
    author_email: str


class NotificationPayload(BaseModel):
    recipient_name: str
    recipient_email: str
    subject: str
    body: str
    status: str


class AirtableSyncPayload(BaseModel):
    status: Literal["synced", "failed", "pending"]
    message: str
    record_id: str | None
    fields: dict


class CoverWorkflowResponse(BaseModel):
    success: bool
    job_id: int
    isbn: str
    file_name: str
    file_type: str
    file_path: str
    pipeline_states: list[PipelineState]
    detected_text_count: int
    extracted_text_blocks: list[OCRBlock]
    ocr_confidence_summary: OCRConfidenceSummary
    validation: ValidationResult
    quality_metrics: QualityMetrics
    operational_summary: OperationalSummary
    ai_layout_analysis: list[str]
    publishing_readiness_score: int
    author: AuthorMetadata
    notification: NotificationPayload
    airtable_sync: AirtableSyncPayload
    timing_metrics: TimingMetrics


class CoverProcessResponse(BaseModel):
    success: bool
    job_id: int
    status: str
    detected_text_count: int
    confidence_summary: OCRConfidenceSummary
    extracted_text_blocks: list[OCRBlock]
    ocr_result_path: str
    quality_metrics: QualityMetrics
    timing_metrics: TimingMetrics


class CoverProcessResult(BaseModel):
    job_id: int
    status: str
    detected_text_count: int
    confidence_summary: OCRConfidenceSummary
    extracted_text_blocks: list[OCRBlock]
    ocr_result_path: str
    quality_metrics: QualityMetrics
    timing_metrics: TimingMetrics


class CoverValidationResponse(BaseModel):
    success: bool
    job_id: int
    status: Literal["PASS", "REVIEW_NEEDED"]
    issues: list[ValidationIssue]
    confidence: ValidationConfidence
    annotated_image_path: str
    timing_metrics: TimingMetrics


class ReviewQueueItem(BaseModel):
    job_id: int
    isbn: str
    file_name: str
    validation_status: Literal["PASS", "REVIEW_NEEDED"]
    overall_confidence: float
    issue_count: int
    issue_severity: str
    processing_latency_ms: int
    publishing_readiness_score: int
    airtable_sync_status: str
    created_at: datetime


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]


class ReviewDetailResponse(BaseModel):
    workflow_report: CoverWorkflowResponse
    revision_history: list[dict]


class BenchmarkSampleResult(BaseModel):
    cover: str
    expected: Literal["PASS", "REVIEW_NEEDED", "BORDERLINE"]
    actual: Literal["PASS", "REVIEW_NEEDED", "BORDERLINE"]
    correct: bool
    prediction: Literal["PASS", "REVIEW_NEEDED", "BORDERLINE"] = "REVIEW_NEEDED"
    confidence: float
    processing_ms: int
    issue_count: int = 0
    overlap_severity: Literal["PASS", "LOW", "MEDIUM", "HIGH"] = "PASS"
    latency_ms: int = 0
    badge_overlap_detected: bool
    expected_badge_overlap: bool


class BenchmarkMetrics(BaseModel):
    total_accuracy: float
    badge_overlap_accuracy: float
    overlap_precision: float = 0.0
    overlap_recall: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int
    false_negatives: int
    overlap_conflict_samples: int = 0
    overlap_successful_detections: int = 0
    overlap_failed_detections: int = 0
    pass_samples: int = 0
    review_needed_samples: int = 0
    borderline_samples: int = 0
    average_confidence: float
    average_processing_latency_ms: float
    manual_review_reduction: float


class BenchmarkResultResponse(BaseModel):
    total_samples: int
    metrics: BenchmarkMetrics
    samples: list[BenchmarkSampleResult]
    summary: str
    exported_json_path: str
    generated_at: datetime


class CoverJobResponse(BaseModel):
    id: int
    isbn: str
    filename: str
    file_path: str
    file_type: str
    status: str
    created_at: datetime
    updated_at: datetime
