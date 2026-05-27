from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.cover import (
    BenchmarkResultResponse,
    CoverProcessResponse,
    CoverProcessResult,
    CoverValidationResponse,
    CoverWorkflowResponse,
    ReviewDetailResponse,
    ReviewQueueResponse,
)
from app.services.cover_processing_service import get_ocr_result, process_cover_job
from app.services.cover_validation_service import get_latest_annotation_path, validate_cover_job
from app.services.benchmark_service import get_latest_benchmark, run_benchmark
from app.services.dataset_ingestion_service import get_ingestion_status, get_ops_summary, ingest_sample_dataset
from app.services.review_dashboard_service import get_review_detail, list_review_queue
from app.services.worker_status_service import get_worker_status
from app.services.workflow_service import run_automated_workflow

router = APIRouter(prefix="/covers")
admin_router = APIRouter(prefix="/admin")


@router.post("/upload", response_model=CoverWorkflowResponse)
def upload_cover(file: UploadFile = File(...), db: Session = Depends(get_db)) -> CoverWorkflowResponse:
    return run_automated_workflow(db=db, upload=file)


@router.post("/process/{job_id}", response_model=CoverProcessResponse)
def process_cover(job_id: int, db: Session = Depends(get_db)) -> CoverProcessResponse:
    result = process_cover_job(db=db, job_id=job_id)
    return CoverProcessResponse(success=True, **result)


@router.get("/results/{job_id}", response_model=CoverProcessResult)
def get_cover_results(job_id: int, db: Session = Depends(get_db)) -> CoverProcessResult:
    result = get_ocr_result(db=db, job_id=job_id)
    return CoverProcessResult(**result)


@router.post("/validate/{job_id}", response_model=CoverValidationResponse)
def validate_cover(job_id: int, db: Session = Depends(get_db)) -> CoverValidationResponse:
    result = validate_cover_job(db=db, job_id=job_id)
    return CoverValidationResponse(success=True, **result)


@router.get("/annotations/{job_id}")
def get_annotation_image(job_id: int) -> FileResponse:
    image_path = get_latest_annotation_path(job_id)
    return FileResponse(path=image_path, media_type="image/png", filename=image_path.name)


@admin_router.get("/review-queue", response_model=ReviewQueueResponse)
def review_queue(status: str | None = Query(default=None)) -> ReviewQueueResponse:
    return ReviewQueueResponse(items=list_review_queue(status_filter=status))


@admin_router.get("/review/{job_id}", response_model=ReviewDetailResponse)
def review_detail(job_id: int) -> ReviewDetailResponse:
    payload = get_review_detail(job_id)
    return ReviewDetailResponse(**payload)


@admin_router.get("/worker-status")
def worker_status() -> dict:
    return get_worker_status()


@admin_router.post("/benchmarks/run", response_model=BenchmarkResultResponse)
def run_benchmarks(db: Session = Depends(get_db)) -> BenchmarkResultResponse:
    return run_benchmark(db=db)


@admin_router.get("/benchmarks/latest", response_model=BenchmarkResultResponse)
def latest_benchmarks() -> BenchmarkResultResponse:
    return get_latest_benchmark()


@admin_router.post("/dataset/ingest")
def dataset_ingest(force: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    return ingest_sample_dataset(db=db, force=force)


@admin_router.get("/ops-summary")
def ops_summary() -> dict:
    return get_ops_summary()


@admin_router.get("/dataset/status")
def dataset_status() -> dict:
    return get_ingestion_status()


@admin_router.get("/dataset/file/{filename}")
def dataset_file(filename: str) -> FileResponse:
    dataset_dir = settings.project_root / "frontend" / "src" / "data" / "sample-covers"
    path = (dataset_dir / filename).resolve()
    if dataset_dir.resolve() not in path.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid dataset file path.")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found.")
    ext = path.suffix.lower()
    media_type = "application/pdf" if ext == ".pdf" else "image/png"
    return FileResponse(path=path, media_type=media_type, filename=Path(filename).name)


@admin_router.get("/airtable/local-sheet")
def airtable_local_sheet() -> FileResponse:
    path = (settings.project_root / "storage" / "processed" / "airtable_local_sheet.csv").resolve()
    if settings.project_root.resolve() not in path.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid spreadsheet path.")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local spreadsheet not found.")
    return FileResponse(path=path, media_type="text/csv", filename=path.name)
