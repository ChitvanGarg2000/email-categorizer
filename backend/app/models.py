from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    google_sub = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    token = relationship("OAuthToken", back_populates="user", uselist=False, cascade="all, delete-orphan")
    emails = relationship("ClassifiedEmail", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")


class OAuthToken(Base):
    """
    Stores the Gmail OAuth token for one user.

    NOTE (MVP -> production gap): tokens are stored in plaintext here for
    simplicity. Before handling real users' data, encrypt access_token /
    refresh_token at rest (e.g. via a KMS-backed field encryption library)
    and never log these values.
    """

    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_uri = Column(String, default="https://oauth2.googleapis.com/token")
    scopes = Column(String, nullable=False)  # space-separated
    expiry = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="token")


class ClassifiedEmail(Base):
    __tablename__ = "classified_emails"
    __table_args__ = (UniqueConstraint("user_id", "gmail_message_id", name="uq_user_message"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    gmail_message_id = Column(String, nullable=False, index=True)
    gmail_thread_id = Column(String, nullable=True, index=True)
    subject = Column(String, default="")
    sender = Column(String, default="")
    snippet = Column(String, default="")

    category = Column(String, nullable=False)
    confidence = Column(Float, default=0.0)
    method = Column(String, default="llm")  # "rule", "llm", or "sender_cache"

    classified_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="emails")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "gmail_thread_id", name="uq_user_thread"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    gmail_thread_id = Column(String, nullable=False, index=True)
    company = Column(String, nullable=True)
    role = Column(String, nullable=True)
    stage = Column(String, default="Unknown", nullable=False)

    last_email_subject = Column(String, default="")
    last_email_snippet = Column(String, default="")
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="applications")
