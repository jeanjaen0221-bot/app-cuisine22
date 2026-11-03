"""Réglages lus dans l'environnement, une seule fois au démarrage."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "oui", "yes", "on"}


@dataclass(frozen=True)
class Reglages:
    environnement: str
    database_url: str
    secret: str
    session_heures: int
    cookie_securise: bool
    fuseau: ZoneInfo
    url_publique: str
    dossier_frontend: str

    @property
    def production(self) -> bool:
        return self.environnement == "production"


def charger() -> Reglages:
    environnement = os.getenv("APP_ENV", "developpement").strip().lower()
    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        if environnement == "production":
            raise RuntimeError("SECRET_KEY doit être défini en production.")
        # Secret temporaire : les sessions sont perdues à chaque redémarrage.
        secret = secrets.token_urlsafe(48)
    url = os.getenv("DATABASE_URL", "sqlite:///./albert_v2.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return Reglages(
        environnement=environnement,
        database_url=url,
        secret=secret,
        session_heures=int(os.getenv("SESSION_HEURES", "12")),
        cookie_securise=_bool("COOKIE_SECURE", environnement == "production"),
        fuseau=ZoneInfo(os.getenv("TZ_RESTAURANT", "Europe/Brussels")),
        url_publique=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        dossier_frontend=os.getenv("FRONTEND_DIST", ""),
    )


reglages = charger()
