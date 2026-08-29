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
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlmodel import Session

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


def require_gpt_api_key(authorization: str = Header(default="")) -> None:
    scheme, _, token = authorization.partition(" ")
    expected_hash = os.getenv("GPT_API_KEY_HASH", "")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Clé API manquante.")
    if not expected_hash:
        raise HTTPException(401, "Aucune clé API GPT configurée côté serveur.")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(token_hash, expected_hash):
        raise HTTPException(401, "Clé API invalide.")


gpt_app = FastAPI(
    title="FicheCuisineManager - GPT Actions API",
    description=(
        "Surface dédiée pour un Custom GPT : lire, créer, remplir et modifier des "
        "fiches de réservation, gérer leur facturation et consulter le catalogue de "
        "plats. Authentification par clé API statique (Authorization: Bearer <clé>)."
    ),
    dependencies=[Depends(require_gpt_api_key)],
)


@gpt_app.get("/fiches", response_model=list[ReservationRead], summary="Lister/rechercher les fiches de réservation")
def list_fiches(
    q: Optional[str] = None,
    service_date: Optional[date] = None,
    session: Session = Depends(get_session),
):
    return reservations_router.list_reservations(q=q, service_date=service_date, session=session)


@gpt_app.get("/fiches/{reservation_id}", response_model=ReservationRead, summary="Récupérer une fiche par son id")
def get_fiche(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.get_reservation(reservation_id, session)


@gpt_app.post("/fiches", response_model=ReservationRead, status_code=201, summary="Créer une fiche de réservation")
def create_fiche(payload: ReservationCreateIn, session: Session = Depends(get_session)):
    return reservations_router.create_reservation(payload, session)


@gpt_app.patch(
    "/fiches/{reservation_id}",
    response_model=ReservationRead,
    summary="Modifier ou remplir une fiche (mise à jour partielle)",
    description=(
        "Mise à jour partielle : seuls les champs fournis sont modifiés. "
        "Attention : si `items` est fourni, il REMPLACE ENTIÈREMENT la liste des plats "
        "existante (ce n'est pas un ajout). Pour ajouter un plat sans perdre les autres, "
        "commencer par un GET /fiches/{id} puis renvoyer la liste complète avec le nouvel "
        "item inclus."
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
