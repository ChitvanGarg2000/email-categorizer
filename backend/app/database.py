from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def migrate_schema() -> None:
    """Apply lightweight SQLite schema updates for existing MVP databases."""
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        email_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(classified_emails)")).fetchall()
        }
        if email_cols and "gmail_thread_id" not in email_cols:
            conn.execute(
                text("ALTER TABLE classified_emails ADD COLUMN gmail_thread_id VARCHAR")
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
