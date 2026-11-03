"""Lecture de la boîte Gmail du restaurant (aucun envoi, aucun brouillon).

Repris de l'ancienne version (app/backend/gmail_service.py), avec deux corrections :
- la liaison de la boîte n'est possible que pour un administrateur connecté, avec un
  paramètre « state » vérifié au retour de Google (l'ancienne version laissait n'importe qui
  relier une autre boîte) ;
- le jeton de rafraîchissement est chiffré en base avec une clé dérivée de SECRET_KEY.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from ..config import reglages
from ..domain.erreurs import ErreurMetier
from ..models import ConnexionGmail, OAuthAttente
from .contexte import Acteur, journaliser

URL_JETON = "https://oauth2.googleapis.com/token"
URL_AUTORISATION = "https://accounts.google.com/o/oauth2/v2/auth"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
PORTEE = "https://www.googleapis.com/auth/gmail.readonly"

_cache_acces: dict[str, Any] = {}


def _chiffreur() -> Fernet:
    cle = base64.urlsafe_b64encode(hashlib.sha256(("gmail:" + reglages.secret).encode()).digest())
    return Fernet(cle)


def _identifiants() -> tuple[str, str]:
    client_id, secret = os.getenv("GMAIL_CLIENT_ID", ""), os.getenv("GMAIL_CLIENT_SECRET", "")
    if not client_id or not secret:
        raise ErreurMetier("regle_metier", "Gmail n'est pas configuré (GMAIL_CLIENT_ID et GMAIL_CLIENT_SECRET).")
    return client_id, secret


def _retour() -> str:
    return f"{reglages.url_publique}/api/gmail/retour"


def configure() -> bool:
    return bool(os.getenv("GMAIL_CLIENT_ID") and os.getenv("GMAIL_CLIENT_SECRET"))


def etat(session: Session) -> dict[str, Any]:
    c = session.get(ConnexionGmail, 1)
    return {"configure": configure(), "relie": c is not None, "email": c.email if c else None,
            "relie_le": c.relie_le.isoformat() if c else None}


# --------------------------------------------------------------- liaison (administrateur)

def url_liaison(session: Session, acteur: Acteur) -> str:
    acteur.exiger("admin")
    client_id, _ = _identifiants()
    etat_oauth = secrets.token_urlsafe(32)
    session.add(OAuthAttente(cle="gmail:" + etat_oauth, genre="gmail", donnees={"admin": acteur.email},
                             expire_le=datetime.now(timezone.utc) + timedelta(minutes=10)))
    session.commit()
    return URL_AUTORISATION + "?" + urlencode({
        "client_id": client_id, "redirect_uri": _retour(), "response_type": "code", "scope": PORTEE,
        "access_type": "offline", "prompt": "consent", "state": etat_oauth,
        "login_hint": os.getenv("GMAIL_ADRESSE", ""),
    })


def terminer_liaison(session: Session, acteur: Acteur, code: str, etat_oauth: str,
                     poster=requests.post, lire=requests.get) -> ConnexionGmail:
    acteur.exiger("admin")
    attente = session.get(OAuthAttente, "gmail:" + (etat_oauth or ""))
    expire = attente.expire_le.replace(tzinfo=timezone.utc) if attente and attente.expire_le.tzinfo is None else (
        attente.expire_le if attente else None)
    if attente is None or attente.genre != "gmail" or expire < datetime.now(timezone.utc):
        raise ErreurMetier("interdit", "Demande de liaison Gmail inconnue ou expirée : recommencer depuis Paramètres.")
    session.delete(attente)
    client_id, secret = _identifiants()
    reponse = poster(URL_JETON, data={"code": code, "client_id": client_id, "client_secret": secret,
                                      "redirect_uri": _retour(), "grant_type": "authorization_code"}, timeout=15)
    if reponse.status_code != 200:
        raise ErreurMetier("regle_metier", "Google a refusé le code d'autorisation.")
    jetons = reponse.json()
    if not jetons.get("refresh_token"):
        raise ErreurMetier("regle_metier", "Google n'a pas renvoyé de jeton durable : retirer l'accès de l'application "
                                           "dans le compte Google, puis recommencer.")
    profil = lire(f"{API}/profile", headers={"Authorization": f"Bearer {jetons['access_token']}"}, timeout=15)
    email = profil.json().get("emailAddress", "") if profil.status_code == 200 else ""
    connexion = session.get(ConnexionGmail, 1) or ConnexionGmail(id=1)
    connexion.email = email
    connexion.jeton_chiffre = _chiffreur().encrypt(jetons["refresh_token"].encode()).decode()
    connexion.relie_par = acteur.email
    connexion.relie_le = datetime.now(timezone.utc)
    session.add(connexion)
    _cache_acces.clear()
    journaliser(session, acteur, "gmail.relier", "gmail", None, f"Boîte {email} reliée")
    session.commit()
    return connexion


def delier(session: Session, acteur: Acteur) -> None:
    acteur.exiger("admin")
    c = session.get(ConnexionGmail, 1)
    if c is not None:
        session.delete(c)
        journaliser(session, acteur, "gmail.delier", "gmail", None, f"Boîte {c.email} déliée")
        session.commit()
    _cache_acces.clear()


# --------------------------------------------------------------- lecture

def _jeton_acces(session: Session, poster=None) -> str:
    poster = poster or requests.post
    if _cache_acces.get("expire", datetime.min.replace(tzinfo=timezone.utc)) > datetime.now(timezone.utc):
        return _cache_acces["jeton"]
    c = session.get(ConnexionGmail, 1)
    if c is None:
        raise ErreurMetier("regle_metier", "Aucune boîte Gmail reliée (Paramètres → Gmail).")
    try:
        rafraichissement = _chiffreur().decrypt(c.jeton_chiffre.encode()).decode()
    except InvalidToken:
        raise ErreurMetier("regle_metier", "Liaison Gmail à refaire (la clé du serveur a changé).")
    client_id, secret = _identifiants()
    r = poster(URL_JETON, data={"client_id": client_id, "client_secret": secret, "refresh_token": rafraichissement,
                                "grant_type": "refresh_token"}, timeout=15)
    if r.status_code != 200:
        raise ErreurMetier("regle_metier", "Gmail refuse l'accès : refaire la liaison dans Paramètres.")
    d = r.json()
    _cache_acces.update(jeton=d["access_token"],
                        expire=datetime.now(timezone.utc) + timedelta(seconds=int(d.get("expires_in", 3600)) - 60))
    return d["access_token"]


def _get(session: Session, chemin: str, params: Optional[dict] = None, lire=requests.get) -> dict:
    r = lire(f"{API}{chemin}", headers={"Authorization": f"Bearer {_jeton_acces(session)}"}, params=params or {}, timeout=15)
    if r.status_code != 200:
        raise ErreurMetier("regle_metier", f"Erreur Gmail ({r.status_code}).")
    return r.json()


def _entete(entetes: list[dict], nom: str) -> str:
    return next((h.get("value", "") for h in entetes or [] if h.get("name", "").lower() == nom.lower()), "")


def _decoder(donnees: str) -> str:
    try:
        return base64.urlsafe_b64decode(donnees + "=" * (-len(donnees) % 4)).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _texte(charge: dict) -> str:
    if charge.get("mimeType") == "text/plain" and charge.get("body", {}).get("data"):
        return _decoder(charge["body"]["data"])
    for partie in charge.get("parts", []) or []:
        texte = _texte(partie)
        if texte:
            return texte
    return ""


def rechercher(session: Session, q: str, maximum: int = 10, lire=requests.get) -> list[dict[str, Any]]:
    liste = _get(session, "/messages", {"q": q, "maxResults": max(1, min(int(maximum), 25))}, lire)
    sortie = []
    for m in liste.get("messages", []):
        msg = _get(session, f"/messages/{m['id']}", {"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]}, lire)
        e = msg.get("payload", {}).get("headers", [])
        sortie.append({"id": msg["id"], "thread_id": msg.get("threadId"), "de": _entete(e, "From"),
                       "objet": _entete(e, "Subject"), "date": _entete(e, "Date"), "extrait": msg.get("snippet", "")})
    return sortie


def lire_fil(session: Session, thread_id: str, lire=requests.get) -> list[dict[str, Any]]:
    fil = _get(session, f"/threads/{thread_id}", None, lire)
    sortie = []
    for msg in fil.get("messages", []):
        e = msg.get("payload", {}).get("headers", [])
        sortie.append({"id": msg["id"], "de": _entete(e, "From"), "a": _entete(e, "To"), "objet": _entete(e, "Subject"),
                       "date": _entete(e, "Date"), "texte": _texte(msg.get("payload", {}))[:20000]})
    return sortie
