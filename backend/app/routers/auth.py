import os

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

# Google may return fewer scopes than requested (e.g. if Gmail API isn't
# enabled on the Cloud project). Don't crash in oauthlib; we validate below.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
from sqlalchemy.orm import Session

from ..config import settings, GMAIL_SCOPES
from ..database import get_db
from ..models import User, OAuthToken
from .. import gmail_service
from ..schemas import MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_flow(state: str | None = None) -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=GMAIL_SCOPES,
        state=state,
        redirect_uri=settings.google_redirect_uri,
    )


@router.get("/login")
def login(request: Request):
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",  # required to get a refresh_token
        include_granted_scopes="true",
        prompt="consent",  # forces refresh_token on every login (fine for MVP)
    )
    request.session["oauth_state"] = state
    return RedirectResponse(auth_url)


@router.get("/callback")
def callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    if state != request.session.get("oauth_state"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    flow = _build_flow(state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials

    gmail_scope = "https://www.googleapis.com/auth/gmail.readonly"
    # creds.scopes can include previously-granted scopes via include_granted_scopes
    # even when this access token was not issued for them — verify the token itself.
    actual_scopes = gmail_service.get_access_token_scopes(creds.token)
    if gmail_scope not in actual_scopes:
        raise HTTPException(
            status_code=403,
            detail=(
                "Gmail read access was not granted. In Google Cloud Console: "
                "(1) enable the Gmail API, "
                "(2) add the gmail.readonly scope under OAuth consent screen > Data Access, "
                "then log in again and approve Gmail access on the consent screen."
            ),
        )

    email, google_sub = gmail_service.fetch_user_email(creds)

    user = db.query(User).filter(User.google_sub == google_sub).first()
    if not user:
        user = User(email=email, google_sub=google_sub)
        db.add(user)
        db.flush()  # get user.id before creating the token row

    token = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
    if not token:
        token = OAuthToken(user_id=user.id)
        db.add(token)

    granted_scopes = sorted(actual_scopes)
    new_scopes = " ".join(granted_scopes)
    old_scopes = set((token.scopes or "").split()) if token.id else set()

    token.access_token = creds.token
    if creds.refresh_token:
        token.refresh_token = creds.refresh_token
    elif old_scopes and set(granted_scopes) != old_scopes:
        # Scopes changed but Google didn't issue a new refresh token.
        # The old refresh token won't include new scopes after the access
        # token expires, which causes "insufficient authentication scopes".
        raise HTTPException(
            status_code=403,
            detail=(
                "Gmail access was updated but your stored refresh token is stale. "
                "Revoke this app at https://myaccount.google.com/permissions, "
                "then log in again."
            ),
        )
    token.scopes = new_scopes
    token.expiry = creds.expiry.replace(tzinfo=None) if creds.expiry else None

    db.commit()

    request.session["user_id"] = user.id
    return RedirectResponse(f"{settings.frontend_url}/dashboard")


@router.get("/me", response_model=MeOut)
def me(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    return MeOut(email=user.email)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}
