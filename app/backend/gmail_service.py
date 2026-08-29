"""Gmail API access for info@albert.brussels, authenticated via a single stored
OAuth refresh token (see routers/gmail_oauth.py for the one-time setup flow).

Scopes granted: gmail.readonly (search/read) and gmail.compose (create drafts,
never send). No business logic beyond talking to Gmail lives here.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional

import requests
from fastapi import HTTPException
from sqlmodel import Session

from .models import GmailToken

TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def client_credentials() -> tuple[str, str]:
    client_id = os.getenv("GMAIL_CLIENT_ID", "")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(500, "GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET non configurés côté serveur.")
    return client_id, client_secret


def get_access_token(session: Session) -> str:
    """Return a valid access token, refreshing it from the stored refresh_token
    if the cached one is missing or about to expire."""
    token_row = session.get(GmailToken, 1)
    if token_row is None:
        raise HTTPException(
            409,
            "Gmail n'est pas encore connecté. Ouvrir /api/gmail/oauth/start dans un navigateur "
            "connecté à info@albert.brussels pour l'autoriser.",
        )
    now = datetime.utcnow()
    if token_row.access_token and token_row.access_token_expires_at and token_row.access_token_expires_at > now + timedelta(seconds=60):
        return token_row.access_token

    client_id, client_secret = client_credentials()
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": token_row.refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise HTTPException(502, f"Échec du rafraîchissement du token Gmail : {resp.text[:300]}")
    data = resp.json()
    token_row.access_token = data["access_token"]
    token_row.access_token_expires_at = now + timedelta(seconds=int(data.get("expires_in", 3600)))
    token_row.updated_at = now
    session.add(token_row)
    session.commit()
    return token_row.access_token


def _gmail_get(session: Session, path: str, params: Optional[dict] = None) -> dict:
    token = get_access_token(session)
    resp = requests.get(
        f"{GMAIL_API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=15,
    )
    if resp.status_code != 200:
        raise HTTPException(502, f"Erreur Gmail API ({resp.status_code}) : {resp.text[:300]}")
    return resp.json()


def _gmail_post(session: Session, path: str, json_body: dict) -> dict:
    token = get_access_token(session)
    resp = requests.post(
        f"{GMAIL_API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=json_body,
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"Erreur Gmail API ({resp.status_code}) : {resp.text[:300]}")
    return resp.json()


def _header(headers: list[dict], name: str) -> str:
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _b64url_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_plain_text(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if mime_type == "text/plain" and body_data:
        return _b64url_decode(body_data)
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return _b64url_decode(part["body"]["data"])
    # Fall back to the first text/plain found anywhere in nested parts (multipart/alternative etc.)
    for part in payload.get("parts", []) or []:
        text = _extract_plain_text(part)
        if text:
            return text
    return ""


def search_messages(session: Session, q: str, max_results: int = 10) -> list[dict]:
    max_results = max(1, min(max_results, 25))
    listing = _gmail_get(session, "/messages", params={"q": q, "maxResults": max_results})
    results = []
    for item in listing.get("messages", []):
        msg = _gmail_get(
            session,
            f"/messages/{item['id']}",
            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
        )
        headers = msg.get("payload", {}).get("headers", [])
        results.append(
            {
                "id": msg["id"],
                "thread_id": msg.get("threadId"),
                "from": _header(headers, "From"),
                "subject": _header(headers, "Subject"),
                "date": _header(headers, "Date"),
                "snippet": msg.get("snippet", ""),
            }
        )
    return results


def get_thread(session: Session, thread_id: str) -> list[dict]:
    thread = _gmail_get(session, f"/threads/{thread_id}")
    out = []
    for msg in thread.get("messages", []):
        headers = msg.get("payload", {}).get("headers", [])
        out.append(
            {
                "id": msg["id"],
                "from": _header(headers, "From"),
                "to": _header(headers, "To"),
                "subject": _header(headers, "Subject"),
                "date": _header(headers, "Date"),
                "body": _extract_plain_text(msg.get("payload", {})),
            }
        )
    return out


def get_message(session: Session, message_id: str) -> dict:
    msg = _gmail_get(session, f"/messages/{message_id}")
    headers = msg.get("payload", {}).get("headers", [])
    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "subject": _header(headers, "Subject"),
        "date": _header(headers, "Date"),
        "body": _extract_plain_text(msg.get("payload", {})),
    }


def create_draft(
    session: Session,
    to: str,
    subject: str,
    body: str,
    thread_id: Optional[str] = None,
    in_reply_to_message_id: Optional[str] = None,
) -> dict:
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    if in_reply_to_message_id:
        mime["In-Reply-To"] = in_reply_to_message_id
        mime["References"] = in_reply_to_message_id
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
    message_body: dict = {"raw": raw}
    if thread_id:
        message_body["threadId"] = thread_id
    result = _gmail_post(session, "/drafts", {"message": message_body})
    return {"draft_id": result.get("id"), "message_id": result.get("message", {}).get("id"), "thread_id": result.get("message", {}).get("threadId")}
