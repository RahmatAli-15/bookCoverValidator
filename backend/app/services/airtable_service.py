from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

AIRTABLE_API_URL = "https://api.airtable.com/v0"


def _fallback_record_id(report: dict) -> str:
    isbn = str(report.get("isbn", "")).strip() or "UNKNOWN"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"LOCAL-{isbn}-{ts}"


def _headers() -> dict[str, str]:
    api_key = os.getenv("AIRTABLE_API_KEY", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _enabled() -> bool:
    return bool(os.getenv("AIRTABLE_API_KEY")) and bool(os.getenv("AIRTABLE_BASE_ID")) and bool(os.getenv("AIRTABLE_TABLE_NAME"))


def _local_sheet_path() -> Path:
    return settings.project_root / "storage" / "processed" / "airtable_local_sheet.csv"


def _read_local_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader)


def _write_local_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sync_local_spreadsheet(fields: dict, fallback_record_id: str) -> dict:
    path = _local_sheet_path()
    rows = _read_local_rows(path)
    isbn = str(fields.get("ISBN", "")).strip()
    fieldnames = ["record_id", *list(fields.keys())]

    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        normalized_row = {name: str(row.get(name, "")) for name in fieldnames}
        normalized_rows.append(normalized_row)

    updated = False
    for row in normalized_rows:
        if str(row.get("ISBN", "")).strip() == isbn and isbn:
            row["record_id"] = fallback_record_id
            for key, value in fields.items():
                row[key] = str(value)
            updated = True
            break

    if not updated:
        normalized_rows.append({"record_id": fallback_record_id, **{k: str(v) for k, v in fields.items()}})

    _write_local_rows(path, normalized_rows, fieldnames)
    return {
        "status": "synced",
        "message": f"Saved to local spreadsheet: {path.name}",
        "record_id": fallback_record_id,
        "fields": fields,
    }


def _sync_payload(report: dict) -> dict:
    issues = report.get("validation", {}).get("issues", [])
    correction_instructions = "\n".join([f"- {item.get('suggested_correction', 'Adjust layout and resubmit.')}" for item in issues]) or "No corrections required."
    revision_history = report.get("revision_history_preview", "N/A")

    return {
        "ISBN": report.get("isbn", ""),
        "filename": report.get("file_name", ""),
        "validation_status": report.get("validation", {}).get("status", ""),
        "confidence_score": report.get("operational_summary", {}).get("overall_confidence", 0),
        "readiness_score": report.get("publishing_readiness_score", 0),
        "issue_count": report.get("operational_summary", {}).get("detected_issue_count", 0),
        "issue_severity": report.get("operational_summary", {}).get("issue_severity", "NONE"),
        "correction_instructions": correction_instructions,
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "annotation_image_path": report.get("validation", {}).get("annotated_image_path", ""),
        "revision_history": revision_history,
    }


def sync_airtable_report(report: dict) -> dict:
    fields = _sync_payload(report)
    fallback_record_id = _fallback_record_id(report)
    if not _enabled():
        return _sync_local_spreadsheet(fields, fallback_record_id)

    base_id = os.getenv("AIRTABLE_BASE_ID", "")
    table_name = os.getenv("AIRTABLE_TABLE_NAME", "")
    isbn = report.get("isbn", "")

    try:
        # Try find existing record by ISBN to avoid duplicates.
        find_url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"
        find_params = {"filterByFormula": f"{{ISBN}}='{isbn}'", "maxRecords": 1}
        find_resp = requests.get(find_url, headers=_headers(), params=find_params, timeout=20)
        if find_resp.status_code >= 400:
            raise RuntimeError(f"Airtable lookup failed: {find_resp.status_code} {find_resp.text}")

        records = find_resp.json().get("records", [])
        if records:
            record_id = records[0]["id"]
            patch_url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}/{record_id}"
            patch_resp = requests.patch(patch_url, headers=_headers(), json={"fields": fields}, timeout=20)
            if patch_resp.status_code >= 400:
                raise RuntimeError(f"Airtable update failed: {patch_resp.status_code} {patch_resp.text}")
            return {"status": "synced", "message": "Record updated", "record_id": record_id, "fields": fields}

        create_resp = requests.post(find_url, headers=_headers(), json={"fields": fields}, timeout=20)
        if create_resp.status_code >= 400:
            raise RuntimeError(f"Airtable create failed: {create_resp.status_code} {create_resp.text}")
        return {"status": "synced", "message": "Record created", "record_id": create_resp.json().get("id"), "fields": fields}

    except Exception as exc:
        logger.exception("Airtable sync failure")
        local_result = _sync_local_spreadsheet(fields, fallback_record_id)
        local_result["status"] = "failed"
        local_result["message"] = f"{exc} | Fallback saved locally."
        return local_result
