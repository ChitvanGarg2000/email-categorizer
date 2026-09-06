from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine, migrate_schema
from .routers import auth, emails, applications

Base.metadata.create_all(bind=engine)
migrate_schema()

app = FastAPI(title="Email Categorizer MVP")

# Cross-origin deploy (e.g. Vercel frontend + Railway backend) requires
# SameSite=None + Secure so the session cookie is sent on API fetch calls.
_is_https = settings.frontend_url.startswith("https://")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="none" if _is_https else "lax",
    https_only=_is_https,
)

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
