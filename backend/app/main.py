from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine, migrate_schema
from .routers import auth, emails, applications

Base.metadata.create_all(bind=engine)
migrate_schema()

app = FastAPI(title="Email Categorizer MVP")

# NOTE: SessionMiddleware here uses a simple signed cookie for the MVP.
# It's fine for a single-instance demo; a production/multi-instance deploy
# should move session state to a shared store (e.g. Redis) instead.
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(applications.router)


@app.get("/health")
def health():
    return {"status": "ok"}
