"""Dedicated API surface for a Custom GPT Action to manage fiches and factures.

This is a separate FastAPI sub-application (mounted at /api/gpt by main.py) so it gets
its own, small OpenAPI schema (/api/gpt/openapi.json) sized for a GPT Action import,
instead of exposing the full internal API. Every route below is a thin wrapper that
delegates to the existing, already-validated route handlers in routers/reservations.py
and routers/menu_items.py — no business logic (pax/quantity guards, sanitization, date
parsing, billing upsert semantics...) is duplicated here.

Authentication is a single static API key (not the human JWT login), checked by
`require_gpt_api_key` below for every route on this sub-app.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlmodel import Session

from . import gmail_service
from .database import get_session
from .models import (
    BillingInfoRead,
    BillingInfoUpdate,
    ReservationCreateIn,
    ReservationRead,
    ReservationUpdate,
)
from .routers import menu_items as menu_items_router
from .routers import reservations as reservations_router

# A proper FastAPI security scheme (rather than a plain Header param) makes the
# Authorization header show up in the OpenAPI schema as `securitySchemes` +
# `security`, not as a per-operation "authorization" parameter — ChatGPT's
# Action importer otherwise flags/ignores the latter since it already manages
# that header itself via the configured API Key auth.
_bearer_scheme = HTTPBearer(auto_error=False)


def _parse_gpt_date(value: str) -> date:
    """Parse a date from a Custom GPT, which doesn't reliably stick to ISO.

    Accepts ISO (2026-09-17) as well as the day/month/year format a model
    tends to fall back to when echoing a date a user typed in French
    (17/09/2026).
    """
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise HTTPException(422, f"Date invalide : {value!r}. Utiliser le format AAAA-MM-JJ.")


def require_gpt_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)) -> None:
    expected_hash = os.getenv("GPT_API_KEY_HASH", "")
    if credentials is None or not credentials.credentials:
        raise HTTPException(401, "Clé API manquante.")
    if not expected_hash:
        raise HTTPException(401, "Aucune clé API GPT configurée côté serveur.")
    token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(token_hash, expected_hash):
        raise HTTPException(401, "Clé API invalide.")


# ChatGPT's Action importer requires an absolute URL in the OpenAPI `servers`
# entry (a bare "/api/gpt" is rejected with "Impossible de trouver une URL
# valide dans `servers`"). PUBLIC_BASE_URL must be set to the public origin
# (e.g. https://fichesfiches.up.railway.app) for this to resolve correctly.
_public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
_servers = [{"url": f"{_public_base_url}/api/gpt"}] if _public_base_url else None

gpt_app = FastAPI(
    title="FicheCuisineManager - GPT Actions API",
    description=(
        "Surface dédiée pour un Custom GPT : lire, créer, remplir et modifier des "
        "fiches de réservation, gérer leur facturation, consulter le catalogue de "
        "plats, et lire/rechercher des emails ou préparer des brouillons Gmail. "
        "Authentification par clé API statique (Authorization: Bearer <clé>)."
    ),
    servers=_servers,
    # Without this, FastAPI auto-prepends a relative "/api/gpt" server entry
    # (derived from the mount's root_path) ahead of the absolute one above —
    # ChatGPT's Action importer rejects that relative entry outright.
    root_path_in_servers=False,
    dependencies=[Depends(require_gpt_api_key)],
)


@gpt_app.get(
    "/fiches",
    response_model=list[ReservationRead],
    summary="Lister/rechercher les fiches de réservation",
    description=(
        "Par défaut, seules les réservations à venir sont retournées, triées par "
        "date, paginées via page/per_page. Utiliser scope=past pour l'historique. "
        "service_date (jour précis, AAAA-MM-JJ ou JJ/MM/AAAA) ignore scope et "
        "remonte tout ce jour-là."
    ),
)
def list_fiches(
    q: Optional[str] = None,
    service_date: Optional[str] = None,
    scope: str = "upcoming",
    page: int = 1,
    per_page: int = 20,
    session: Session = Depends(get_session),
):
    per_page = max(1, min(per_page, 50))
    page = max(1, page)
    parsed_date = _parse_gpt_date(service_date) if service_date else None
    if parsed_date is not None:
        # A specific day is naturally bounded in size, so the exact-match path
        # (used elsewhere for day exports) is fine here regardless of scope.
        rows = reservations_router.list_reservations(q=q, service_date=parsed_date, session=session)
        start = (page - 1) * per_page
        return rows[start : start + per_page]
    if (scope or "upcoming").lower().strip() == "past":
        return reservations_router.list_past_reservations(q=q, page=page, per_page=per_page, session=session)
    return reservations_router.list_upcoming_reservations(q=q, page=page, per_page=per_page, session=session)


@gpt_app.get("/fiches/{reservation_id}", response_model=ReservationRead, summary="Récupérer une fiche par son id")
def get_fiche(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.get_reservation(reservation_id, session)


@gpt_app.post(
    "/fiches",
    response_model=ReservationRead,
    status_code=201,
    summary="Créer une fiche de réservation",
    description=(
        "Si menu_formula='Brunch' (buffet, sans service à table), ne jamais ajouter "
        "d'items entrée/plat/dessert : mettre uniquement des extras (Champagne, Planche "
        "apéro, Privatisation…) en items type='supplément'."
    ),
)
def create_fiche(payload: ReservationCreateIn, session: Session = Depends(get_session)):
    return reservations_router.create_reservation(payload, session)


@gpt_app.patch(
    "/fiches/{reservation_id}",
    response_model=ReservationRead,
    summary="Modifier ou remplir une fiche (mise à jour partielle)",
    description=(
        "Mise à jour partielle : seuls les champs fournis sont modifiés. "
        "items, si fourni, REMPLACE toute la liste (pas un ajout) — faire un GET avant. "
        "Si menu_formula='Brunch' (buffet), items ne doit contenir que des suppléments "
        "(type='supplément'), jamais d'entrée/plat/dessert."
    ),
)
def update_fiche(reservation_id: uuid.UUID, payload: ReservationUpdate, session: Session = Depends(get_session)):
    return reservations_router.update_reservation(reservation_id, payload, session)


@gpt_app.delete("/fiches/{reservation_id}", summary="Supprimer une fiche de réservation")
def delete_fiche(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.delete_reservation(reservation_id, session)


@gpt_app.post("/fiches/{reservation_id}/duplicate", response_model=ReservationRead, summary="Dupliquer une fiche")
def duplicate_fiche(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.duplicate_reservation(reservation_id, session)


@gpt_app.get("/fiches/{reservation_id}/pdf", summary="Télécharger le PDF de la fiche (et sa facture si elle existe)")
def download_fiche_pdf(
    reservation_id: uuid.UUID,
    variant: Optional[str] = None,
    session: Session = Depends(get_session),
):
    return reservations_router.export_reservation_pdf(reservation_id, variant, session)


@gpt_app.get("/fiches/{reservation_id}/billing", response_model=BillingInfoRead, summary="Récupérer la facturation d'une fiche")
def get_billing(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.get_billing(reservation_id, session)


@gpt_app.put(
    "/fiches/{reservation_id}/billing",
    response_model=BillingInfoRead,
    summary="Créer ou mettre à jour la facturation d'une fiche (upsert)",
)
def upsert_billing(reservation_id: uuid.UUID, payload: BillingInfoUpdate, session: Session = Depends(get_session)):
    return reservations_router.update_billing(reservation_id, payload, session)


@gpt_app.get("/fiches/{reservation_id}/facture-pdf", summary="Télécharger la facture PDF d'une fiche")
def download_invoice_pdf(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.export_invoice_pdf(reservation_id, session)


@gpt_app.get(
    "/menu-items/search",
    summary="Rechercher des plats du catalogue (pour connaître les noms/types valides avant de remplir une fiche)",
)
def search_menu_items(q: Optional[str] = None, type: Optional[str] = None, session: Session = Depends(get_session)):
    return menu_items_router.search_items(q, type, session)


# ===== Gmail (boîte partagée, ex. info@albert.brussels) =====
# Lecture seule + brouillons uniquement : aucune route n'envoie de mail, même si
# le jeton OAuth sous-jacent (scope gmail.compose) le permettrait techniquement.

class DraftCreate(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: Optional[str] = None


@gpt_app.get(
    "/gmail/search",
    summary="Rechercher des emails (syntaxe de recherche Gmail)",
    description=(
        "q utilise la syntaxe de recherche Gmail, ex: 'from:client@exemple.com "
        "newer_than:30d' ou 'subject:facture'. Voir l'aide Gmail pour la syntaxe."
    ),
)
def search_gmail(q: str, max_results: int = 10, session: Session = Depends(get_session)):
    return gmail_service.search_messages(session, q, max_results)


@gpt_app.get(
    "/gmail/client-messages",
    summary="Récupérer les derniers emails échangés avec une adresse cliente",
)
def gmail_client_messages(email: str, max_results: int = 10, session: Session = Depends(get_session)):
    query = f"from:{email} OR to:{email}"
    return gmail_service.search_messages(session, query, max_results)


@gpt_app.get("/gmail/threads/{thread_id}", summary="Lire un fil de discussion complet")
def get_gmail_thread(thread_id: str, session: Session = Depends(get_session)):
    return gmail_service.get_thread(session, thread_id)


@gpt_app.get("/gmail/messages/{message_id}", summary="Lire un email précis")
def get_gmail_message(message_id: str, session: Session = Depends(get_session)):
    return gmail_service.get_message(session, message_id)


@gpt_app.post(
    "/gmail/drafts",
    status_code=201,
    summary="Préparer un brouillon de réponse (jamais envoyé automatiquement)",
    description=(
        "Crée un brouillon visible dans Gmail, à relire et envoyer manuellement. "
        "thread_id (optionnel) place le brouillon dans un fil existant plutôt "
        "que d'en créer un nouveau."
    ),
)
def create_gmail_draft(payload: DraftCreate, session: Session = Depends(get_session)):
    return gmail_service.create_draft(session, payload.to, payload.subject, payload.body, payload.thread_id)
