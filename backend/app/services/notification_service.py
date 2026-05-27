from __future__ import annotations


def build_notification(status: str, recipient_name: str, recipient_email: str, issues: list[dict], readiness_score: int) -> dict:
    issue_lines = "\n".join([f"- {i.get('message')} (severity: {i.get('severity')})" for i in issues]) or "- No issue details available"
    correction_lines = "\n".join([f"- {i.get('suggested_correction', 'Adjust layout and resubmit.')}" for i in issues]) or "- None"

    if status == "PASS":
        subject = "Book Cover QA Result: PASS"
        headline = "Your cover successfully passed automated QA validation."
        next_steps = "Proceed to production-ready submission and schedule print proofing."
    else:
        subject = "Book Cover QA Result: REVIEW_NEEDED"
        headline = "Your cover requires revision before approval."
        next_steps = "Apply corrections and re-upload using the same ISBN filename convention."

    body = (
        f"Hello {recipient_name},\n\n"
        f"{headline}\n\n"
        f"Validation Result: {status}\n"
        f"Publishing Readiness Score: {readiness_score}/100\n\n"
        "Detected Issues:\n"
        f"{issue_lines}\n\n"
        "Correction Guidance:\n"
        f"{correction_lines}\n\n"
        f"Next Steps:\n{next_steps}\n\n"
        "Regards,\nPublishing QA Automation"
    )

    return {
        "recipient_name": recipient_name,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "status": status,
    }
