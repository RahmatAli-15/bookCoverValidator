import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cover_job import CoverJob

FILENAME_PATTERN = re.compile(r"^(?P<isbn>\d{13})_text\.(?P<ext>pdf|png)$", re.IGNORECASE)
ALLOWED_EXTENSIONS = {"pdf", "png"}
ALLOWED_CONTENT_TYPES = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
}


def _validate_filename(filename: str) -> tuple[str, str]:
    match = FILENAME_PATTERN.match(filename)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename format. Expected ISBN_text.extension (e.g., 1234567890123_text.pdf).",
        )

    isbn = match.group("isbn")
    extension = match.group("ext").lower()
    return isbn, extension


def _validate_file_type(upload: UploadFile, extension: str) -> None:
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF and PNG are accepted.",
        )

    if upload.content_type not in ALLOWED_CONTENT_TYPES[extension]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content type does not match extension.",
        )


def create_cover_upload_job(db: Session, upload: UploadFile) -> CoverJob:
    if not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    isbn, extension = _validate_filename(upload.filename)
    _validate_file_type(upload, extension)

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    storage_name = f"{isbn}_{timestamp}.{extension}"
    storage_path = settings.uploads_dir / storage_name

    content = upload.file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    storage_path.write_bytes(content)

    relative_path = str(Path("storage") / "uploads" / storage_name)

    job = CoverJob(
        isbn=isbn,
        filename=upload.filename,
        file_path=relative_path,
        file_type=extension,
        status="uploaded",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
