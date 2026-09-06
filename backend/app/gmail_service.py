"""
Thin wrapper around the Gmail API: build a credentialed client for a stored
user token, and fetch a batch of unread messages with just the fields we
need for classification (subject, sender, snippet).
"""
import httpx
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import settings
from .models import OAuthToken

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
REAUTH_MESSAGE = (
    "Gmail access expired or was not fully granted. Revoke this app at "
    "https://myaccount.google.com/permissions, then log in again."
)


def get_access_token_scopes(access_token: str) -> set[str]:
    """Return the scopes actually granted on an access token (not metadata)."""
    response = httpx.get(
        "https://www.googleapis.com/oauth2/v1/tokeninfo",
        params={"access_token": access_token},
        timeout=10.0,
    )
    if response.status_code != 200:
        return set()
    return set(response.json().get("scope", "").split())


def credentials_from_token(token: OAuthToken) -> Credentials:
    stored_scopes = token.scopes.split()
    if GMAIL_READONLY_SCOPE not in stored_scopes:
        raise HTTPException(status_code=403, detail=REAUTH_MESSAGE)

    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=stored_scopes,
    )
    # Refresh if expired -- Gmail access tokens are short-lived (~1hr),
    # the refresh_token is what makes this work without re-login each time.
    try:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token.access_token = creds.token
            if creds.expiry:
                token.expiry = creds.expiry.replace(tzinfo=None)
    except RefreshError:
        raise HTTPException(status_code=403, detail=REAUTH_MESSAGE) from None

    actual_scopes = get_access_token_scopes(creds.token)
    if GMAIL_READONLY_SCOPE not in actual_scopes:
        raise HTTPException(status_code=403, detail=REAUTH_MESSAGE)

    return creds


def _raise_for_gmail_http_error(exc: HttpError) -> None:
    """Turn Gmail API 403s into actionable HTTP errors instead of 500s."""
    status = exc.resp.status if exc.resp else 0
    if status != 403:
        raise exc

    body = str(exc).lower()
    if "insufficient authentication scopes" in body or "insufficientpermission" in body:
        raise HTTPException(status_code=403, detail=REAUTH_MESSAGE) from exc
    if "accessnotconfigured" in body or "has not been used in project" in body:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gmail API is not enabled for your Google Cloud project. "
                "Enable it at APIs & Services > Library > Gmail API, wait "
                "a minute, then try syncing again."
            ),
        ) from exc
    raise exc


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def fetch_unread_messages(token: OAuthToken, max_results: int = 20) -> list[dict]:
    """
    Returns a list of dicts: {id, thread_id, internal_date, subject, sender, snippet}
    for up to `max_results` unread messages in the inbox.
    """
    creds = credentials_from_token(token)
    service = build("gmail", "v1", credentials=creds)

    try:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread in:inbox", maxResults=max_results)
            .execute()
        )
    except HttpError as exc:
        _raise_for_gmail_http_error(exc)

    message_refs = resp.get("messages", [])

    results = []
    for ref in message_refs:
        try:
            msg = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=ref["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From"],
                )
                .execute()
            )
        except HttpError as exc:
            _raise_for_gmail_http_error(exc)
        headers = msg.get("payload", {}).get("headers", [])
        results.append(
            {
                "id": msg["id"],
                "thread_id": msg.get("threadId", ""),
                "internal_date": int(msg.get("internalDate", "0")),
                "subject": _get_header(headers, "Subject"),
                "sender": _get_header(headers, "From"),
                "snippet": msg.get("snippet", ""),
            }
        )
    return results


def fetch_user_email(creds: Credentials) -> str:
    """Used once at login time to identify the user (via the OIDC userinfo endpoint)."""
    from googleapiclient.discovery import build as build_client

    oauth2_service = build_client("oauth2", "v2", credentials=creds)
    info = oauth2_service.userinfo().get().execute()
    return info["email"], info["id"]
