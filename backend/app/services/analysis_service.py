from __future__ import annotations


def build_ai_layout_analysis(status: str, issues: list[dict], quality: dict) -> list[str]:
    lines: list[str] = []
    has_badge = any(i.get("type") == "BADGE_OVERLAP" for i in issues)
    has_margin = any(i.get("type") in {"SAFE_MARGIN_VIOLATION", "BORDERLINE_SPACING"} for i in issues)

    lines.append("Typography readability is acceptable" if quality.get("small_text_ratio", 0) < 0.35 else "Typography readability needs improvement")
    lines.append("Award badge zone is unobstructed" if not has_badge else "Award badge zone has text obstruction")
    lines.append("Spacing margins are compliant" if not has_margin else "Spacing margins require adjustment")

    if quality.get("is_blurry"):
        lines.append("Image clarity is below recommended QA threshold")
    if status == "PASS":
        lines.append("Layout is production-ready for publishing operations")
    return lines


def compute_publishing_readiness(ocr_conf: float, overlap_safety: float, quality: dict, issues: list[dict]) -> int:
    spacing_score = 1.0 - min(1.0, overlap_safety)
    quality_score = 1.0
    if quality.get("is_blurry"):
        quality_score -= 0.12
    if not quality.get("resolution_ok", True):
        quality_score -= 0.2
    quality_score -= min(0.18, float(quality.get("small_text_ratio", 0.0)) * 0.35)
    quality_score = max(0.0, quality_score)

    severity_penalty = 0.0
    for item in issues:
        sev = item.get("severity")
        if item.get("type") == "LOW_IMAGE_QUALITY":
            # Mild readiness reduction for quality warnings unless supported by other hard failures.
            severity_penalty += 0.02 if sev == "MEDIUM" else 0.01
            continue

        severity_penalty += 0.12 if sev == "HIGH" else 0.06 if sev == "MEDIUM" else 0.025
        if item.get("type") == "TYPOGRAPHY_CONFLICT" and sev == "HIGH":
            severity_penalty += 0.15
        if item.get("type") == "BADGE_OVERLAP" and sev == "HIGH":
            severity_penalty += 0.18

    raw = ((ocr_conf * 0.25) + (spacing_score * 0.3) + (quality_score * 0.25) + ((1.0 - severity_penalty) * 0.2))
    return max(0, min(100, int(round(raw * 100))))


def suggested_correction(issue_type: str) -> str:
    mapping = {
        "BADGE_OVERLAP": "Move author name above reserved Emily Dickinson Award area.",
        "AUTHOR_NAME_CONFLICT": "Reposition author name upward and keep it clear of badge and side safe margins.",
        "SAFE_MARGIN_VIOLATION": "Increase border spacing to keep typography inside safe margin limits.",
        "BACK_COVER_ALIGNMENT": "Align back-cover body text to a consistent left or center axis.",
        "TYPOGRAPHY_CONFLICT": "Increase spacing between subtitle and badge zone.",
        "BORDERLINE_SPACING": "Increase margin spacing slightly for safer print tolerance.",
        "LOW_OCR_CONFIDENCE": "Improve image clarity and text contrast before resubmission.",
        "UNCERTAIN_OVERLAP": "Reposition nearby text to remove ambiguous overlap risk.",
        "LOW_IMAGE_QUALITY": "Increase image resolution and sharpness for reliable QA.",
        "AUTHOR_POSITION_CONFLICT": "Move author name higher to avoid protected badge region.",
    }
    return mapping.get(issue_type, "Adjust layout placement and resubmit for validation.")
