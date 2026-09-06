"""
Sync Application rows from newly classified Job/Interview emails (thread-based).
"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from .application_extractor import APPLICATION_STAGES, extract_application_details_batch
from .models import Application


def _apply_details_to_application(
    app: Application,
    details: dict,
    email: dict,
) -> None:
    company = details.get("company")
    role = details.get("role")
    stage = details.get("stage", "Unknown")

    if company:
        app.company = company
    if role:
        app.role = role
    if stage and stage != "Unknown":
        app.stage = stage

    app.last_email_subject = email["subject"]
    app.last_email_snippet = email["snippet"]
    app.last_updated = datetime.utcnow()


def sync_applications_from_job_emails(
    db: Session,
    user_id: int,
    job_emails: list[dict],
) -> None:
    """
    Create or update Application rows from newly classified Job/Interview emails.

    Each email dict must have: id, thread_id, subject, sender, snippet,
    and optionally internal_date for ordering within a thread.
    """
    if not job_emails:
        return

    by_thread: dict[str, list[dict]] = defaultdict(list)
    for email in job_emails:
        thread_id = email.get("thread_id")
        if thread_id:
            by_thread[thread_id].append(email)

    if not by_thread:
        return

    thread_ids = list(by_thread.keys())
    existing_apps = {
        app.gmail_thread_id: app
        for app in db.query(Application)
        .filter(Application.user_id == user_id, Application.gmail_thread_id.in_(thread_ids))
        .all()
    }

    extraction_queue: list[dict] = []
    for thread_id, emails in by_thread.items():
        emails.sort(key=lambda e: e.get("internal_date", 0))
        extraction_queue.extend(emails)

    extractions = extract_application_details_batch(extraction_queue)

    for thread_id, emails in by_thread.items():
        emails.sort(key=lambda e: e.get("internal_date", 0))
        app = existing_apps.get(thread_id)

        if app is None:
            app = Application(
                user_id=user_id,
                gmail_thread_id=thread_id,
                stage="Unknown",
            )
            db.add(app)
            existing_apps[thread_id] = app

        for email in emails:
            details = extractions.get(email["id"], {"company": None, "role": None, "stage": "Unknown"})
            _apply_details_to_application(app, details, email)
