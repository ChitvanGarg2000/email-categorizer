from datetime import datetime
from pydantic import BaseModel


class EmailOut(BaseModel):
    gmail_message_id: str
    subject: str
    sender: str
    snippet: str
    category: str
    confidence: float
    method: str
    classified_at: datetime

    class Config:
        from_attributes = True


class MeOut(BaseModel):
    email: str


class SyncResult(BaseModel):
    fetched: int
    newly_classified: int
    emails: list[EmailOut]


class ApplicationOut(BaseModel):
    id: int
    gmail_thread_id: str
    company: str | None
    role: str | None
    stage: str
    last_email_subject: str
    last_email_snippet: str
    last_updated: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationUpdate(BaseModel):
    stage: str | None = None
    company: str | None = None
    role: str | None = None
