from __future__ import annotations

import json

from app.core.config import settings
from app.schemas.cover import AuthorMetadata


def get_author_metadata(isbn: str) -> AuthorMetadata:
    try:
        payload = json.loads(settings.author_metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}

    item = payload.get(isbn)
    if item:
        return AuthorMetadata(author_name=item["author_name"], author_email=item["author_email"])
    return AuthorMetadata(author_name="Publishing Team", author_email="publishing-ops@example.com")
