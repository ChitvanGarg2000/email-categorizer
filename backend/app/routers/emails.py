from fastapi import APIRouter, Request, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application_sync import sync_applications_from_job_emails
from ..database import get_db
from ..models import User, OAuthToken, ClassifiedEmail
from ..schemas import EmailOut, SyncResult
from .. import gmail_service
from ..classifier import build_sender_history, classify_batch

router = APIRouter(prefix="/emails", tags=["emails"])


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


@router.post("/sync", response_model=SyncResult)
def sync_emails(
    max_results: int = Query(default=20, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Pulls unread inbox messages from the last gmail_sync_days from Gmail,
    classifies any we haven't seen before (checked by gmail_message_id so
    re-syncing doesn't burn LLM calls re-classifying the same email), and
    returns the full set.
    """
    token = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
    if not token:
        raise HTTPException(status_code=400, detail="No Gmail token on file -- log in again")

    access_token_before = token.access_token
    messages = gmail_service.fetch_unread_messages(token, max_results=max_results)
    # Persist a refreshed access token so the next request doesn't re-refresh.
    if token.access_token != access_token_before:
        db.commit()

    existing_ids = {
        row.gmail_message_id
        for row in db.query(ClassifiedEmail.gmail_message_id).filter(
            ClassifiedEmail.user_id == user.id
        )
    }

    new_messages = [msg for msg in messages if msg["id"] not in existing_ids]

    prior_rows = (
        db.query(ClassifiedEmail.sender, ClassifiedEmail.category)
        .filter(ClassifiedEmail.user_id == user.id)
        .all()
    )
    sender_history = build_sender_history(prior_rows)

    classifications = classify_batch(
        [
            {
                "id": msg["id"],
                "subject": msg["subject"],
                "sender": msg["sender"],
                "snippet": msg["snippet"],
            }
            for msg in new_messages
        ],
        sender_history=sender_history,
    )

    newly_classified = 0
    new_job_emails: list[dict] = []

    for msg in new_messages:
        category, confidence, method = classifications[msg["id"]]
        db.add(
            ClassifiedEmail(
                user_id=user.id,
                gmail_message_id=msg["id"],
                gmail_thread_id=msg.get("thread_id"),
                subject=msg["subject"],
                sender=msg["sender"],
                snippet=msg["snippet"],
                category=category,
                confidence=confidence,
                method=method,
            )
        )
        newly_classified += 1

        if category == "Job/Interview":
            new_job_emails.append(
                {
                    "id": msg["id"],
                    "thread_id": msg.get("thread_id"),
                    "internal_date": msg.get("internal_date", 0),
                    "subject": msg["subject"],
                    "sender": msg["sender"],
                    "snippet": msg["snippet"],
                }
            )

    sync_applications_from_job_emails(db, user.id, new_job_emails)

    db.commit()

    all_emails = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id)
        .order_by(ClassifiedEmail.classified_at.desc())
        .all()
    )

    return SyncResult(
        fetched=len(messages),
        newly_classified=newly_classified,
        emails=[EmailOut.model_validate(e) for e in all_emails],
    )


@router.get("/", response_model=list[EmailOut])
def list_emails(
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ClassifiedEmail).filter(ClassifiedEmail.user_id == user.id)
    if category:
        query = query.filter(ClassifiedEmail.category == category)
    rows = query.order_by(ClassifiedEmail.classified_at.desc()).all()
    return [EmailOut.model_validate(r) for r in rows]
