from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    APP_NAME: str = "Book Cover Validator API"
    APP_VERSION: str = "0.6.0"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = "sqlite:///./book_cover_validator.db"
    COVER_REFERENCE_WIDTH_MM: float = 129.0
    COVER_REFERENCE_HEIGHT_MM: float = 198.0
    SAFE_MARGIN_MM: float = 3.0
    BADGE_ZONE_HEIGHT_MM: float = 9.0
    BADGE_ZONE_PADDING_MM: float = 2.0

    @property
    def backend_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def project_root(self) -> Path:
        return self.backend_dir.parent

    @property
    def uploads_dir(self) -> Path:
        return self.project_root / "storage" / "uploads"

    @property
    def ocr_results_dir(self) -> Path:
        return self.project_root / "storage" / "processed" / "ocr_results"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / "storage" / "processed" / "reports"

    @property
    def notifications_dir(self) -> Path:
        return self.project_root / "storage" / "processed" / "notifications"

    @property
    def benchmarks_dir(self) -> Path:
        return self.project_root / "storage" / "processed" / "benchmarks"

    @property
    def worker_status_path(self) -> Path:
        return self.project_root / "storage" / "processed" / "worker_status.json"

    @property
    def drive_state_path(self) -> Path:
        return self.project_root / "storage" / "processed" / "drive_processed_ids.json"

    @property
    def annotations_dir(self) -> Path:
        return self.project_root / "storage" / "annotations"

    @property
    def test_samples_dir(self) -> Path:
        return self.project_root / "test_samples"

    @property
    def author_metadata_path(self) -> Path:
        return self.backend_dir / "core" / "author_metadata.json"


settings = Settings()
