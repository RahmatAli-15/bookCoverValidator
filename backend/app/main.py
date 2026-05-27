import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.services.cover_processing_service import init_ocr_reader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


def _ensure_local_spreadsheet() -> None:
    csv_path = settings.project_root / "storage" / "processed" / "airtable_local_sheet.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if csv_path.exists():
        return
    header = ",".join(
        [
            "record_id",
            "ISBN",
            "filename",
            "validation_status",
            "confidence_score",
            "readiness_score",
            "issue_count",
            "issue_severity",
            "correction_instructions",
            "processing_timestamp",
            "annotation_image_path",
            "revision_history",
        ]
    )
    csv_path.write_text(f"{header}\n", encoding="utf-8")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    frontend_url = os.getenv("FRONTEND_URL", "").strip()
    allowed_origins = ["http://localhost:5173", "http://localhost:5174"]
    if frontend_url:
        allowed_origins.append(frontend_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.ocr_results_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.notifications_dir.mkdir(parents=True, exist_ok=True)
    settings.benchmarks_dir.mkdir(parents=True, exist_ok=True)
    settings.annotations_dir.mkdir(parents=True, exist_ok=True)
    _ensure_local_spreadsheet()

    Base.metadata.create_all(bind=engine)
    # Optional preload only when explicitly enabled.
    # Default behavior is lazy initialization on first OCR request to reduce startup memory.
    if os.getenv("OCR_PRELOAD", "").strip().lower() in {"1", "true", "yes"}:
        init_ocr_reader()

    app.include_router(api_router, prefix=settings.API_PREFIX)
    return app


app = create_app()
