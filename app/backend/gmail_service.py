"""Thin Gmail API client for the /api/gpt Gmail endpoints.

Uses a single pre-authorized mailbox (e.g. info@albert.brussels) via a
long-lived OAuth refresh token stored in env vars — there is no per-user
Google login here, this is a shared-service credential analogous to the
GPT_API_KEY_HASH auth used for the rest of /api/gpt.

Required env vars: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN.
Scopes needed on that refresh token: gmail.readonly and gmail.compose.
"""
from __future__ import annotations

import base64
import os
import time
from email.mime.text import MIMEText
from typing import Optional

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

_cached_token: dict = {"value": None, "expires_at": 0.0}


class GmailNotConfigured(Exception):
    pass


def _get_access_token() -> str:
    now = time.time()
    if _cached_token["value"] and now < _cached_token["expires_at"] - 30:
        return _cached_token["value"]

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise GmailNotConfigured(
            "Gmail non configuré : GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / "
            "GOOGLE_REFRESH_TOKEN manquants côté serveur."
        )

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _cached_token["value"] = data["access_token"]
    _cached_token["expires_at"] = now + data.get("expires_in", 3600)
    return _cached_token["value"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_access_token()}"}


def _extract_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text
    return ""


def _simplify_message(msg: dict, include_body: bool = False) -> dict:
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    out = {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "snippet": msg.get("snippet"),
        "from": headers.get("From"),
        "to": headers.get("To"),
        "subject": headers.get("Subject"),
        "date": headers.get("Date"),
    }
    if include_body:
        out["body"] = _extract_body(msg.get("payload", {}))
    return out


def get_message(message_id: str) -> dict:
    resp = requests.get(
        f"{API_BASE}/messages/{message_id}",
        headers=_headers(),
        params={"format": "full"},
        timeout=15,
    )
    resp.raise_for_status()
    return _simplify_message(resp.json(), include_body=True)


def search_messages(query: str, max_results: int = 10) -> list[dict]:
    """Search messages using Gmail's search syntax, e.g. 'from:client@example.com newer_than:30d'."""
    max_results = max(1, min(max_results, 25))
    resp = requests.get(
        f"{API_BASE}/messages",
        headers=_headers(),
        params={"q": query, "maxResults": max_results},
        timeout=15,
    )
    resp.raise_for_status()
    ids = [m["id"] for m in resp.json().get("messages", [])]
    return [get_message(mid) for mid in ids]


def get_thread(thread_id: str) -> dict:
    resp = requests.get(
        f"{API_BASE}/threads/{thread_id}",
        headers=_headers(),
        params={"format": "full"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "id": data["id"],
        "messages": [_simplify_message(m, include_body=True) for m in data.get("messages", [])],
    }


def create_draft(to: str, subject: str, body: str, thread_id: Optional[str] = None) -> dict:
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    payload: dict = {"message": {"raw": raw}}
    if thread_id:
        payload["message"]["threadId"] = thread_id
    resp = requests.post(f"{API_BASE}/drafts", headers=_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return {
        "id": data["id"],
        "message_id": data.get("message", {}).get("id"),
        "thread_id": data.get("message", {}).get("threadId"),
    }
