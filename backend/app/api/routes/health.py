from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "book-cover-validator-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
