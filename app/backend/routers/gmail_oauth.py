"""One-time browser flow to connect info@albert.brussels' Gmail to this backend.

Public by design (exempted from the JWT middleware in main.py, like /api/auth/*):
/start builds Google's consent URL and redirects to it; /callback exchanges the
returned code for a refresh_token and stores it (see models.GmailToken). No
password or token ever passes through this app's UI or an AI assistant — the
user authenticates directly with Google in their own browser.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from ..database import session_context
from ..gmail_service import TOKEN_URL, client_credentials
from ..models import GmailToken

router = APIRouter(prefix="/api/gmail/oauth", tags=["gmail-oauth"])

SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose"


def _redirect_uri() -> str:
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        raise HTTPException(500, "PUBLIC_BASE_URL non configuré côté serveur.")
    return f"{base}/api/gmail/oauth/callback"


@router.get("/start")
def start():
    client_id, _ = client_credentials()
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": "info@albert.brussels",
    }
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@router.get("/callback")
def callback(code: str = Query(default=""), error: str = Query(default="")):
    if error:
        return HTMLResponse(f"<h1>Autorisation refusée</h1><p>{error}</p>", status_code=400)
    if not code:
        raise HTTPException(400, "Code d'autorisation manquant.")

    client_id, client_secret = client_credentials()
    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        return HTMLResponse(f"<h1>Échec de l'échange du code</h1><pre>{resp.text[:1000]}</pre>", status_code=502)
    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return HTMLResponse(
            "<h1>Aucun refresh_token reçu</h1>"
            "<p>Google n'en renvoie qu'à la toute première autorisation d'une app. "
            "Révoque l'accès existant sur <a href='https://myaccount.google.com/permissions'>"
            "myaccount.google.com/permissions</a> (cherche l'app Gmail créée), puis relance "
            "<code>/api/gmail/oauth/start</code>.</p>",
            status_code=409,
        )

    with session_context() as session:  # type: Session
        row = session.get(GmailToken, 1)
        if row is None:
            row = GmailToken(id=1, email="info@albert.brussels", refresh_token=refresh_token)
        else:
            row.refresh_token = refresh_token
        session.add(row)
        session.commit()

    return HTMLResponse(
        "<h1>Gmail connecté ✅</h1>"
        "<p>info@albert.brussels est maintenant relié au backend. Tu peux fermer cet onglet "
        "et retourner dans ChatGPT.</p>"
    )
