"""Synchronisation des réservations de groupe depuis Zenchef.

Même appel que l'ancienne version (GET /v1/reservations, filtré sur la période). Différences :
- le jeton d'accès est une variable d'environnement (ZENCHEF_API_TOKEN, ZENCHEF_RESTAURANT_ID),
  plus stocké en clair dans la base ;
- chaque réservation importée retrouve (ou crée) son client, et devient une fiche en brouillon ;
- une réservation déjà importée n'est jamais recréée (clé « zenchef:<id> » sur la fiche).
"""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.erreurs import ErreurMetier
from ..domain.normalisation import cle_nom_client, lire_date
from ..models import Client, Fiche
from . import clients, fiches
from .contexte import Acteur, journaliser, lire_parametres

URL = "https://api.zenchef.com/v1/reservations"


def configure() -> bool:
    return bool(os.getenv("ZENCHEF_API_TOKEN") and os.getenv("ZENCHEF_RESTAURANT_ID"))


def _appel_http(params: dict[str, Any]) -> dict[str, Any]:
    reponse = requests.get(URL, params=params, timeout=30,
                           headers={"Authorization": f"Bearer {os.getenv('ZENCHEF_API_TOKEN')}"})
    if reponse.status_code >= 400:
        raise ErreurMetier("regle_metier", f"Zenchef a refusé la demande ({reponse.status_code}).")
    return reponse.json() or {}


def _debut(valeur: str) -> tuple[date, Any]:
    texte = (valeur or "").replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(texte)
        return moment.date(), moment.time().replace(second=0, microsecond=0, tzinfo=None)
    except ValueError:
        raise ErreurMetier("valeur_non_permise", f"Heure Zenchef illisible : {valeur!r}.")


def _client_pour(session: Session, acteur: Acteur, client_zenchef: dict[str, Any]) -> Client:
    prenom = (client_zenchef.get("firstname") or "").strip()
    nom_famille = (client_zenchef.get("lastname") or "").strip()
    societe = (client_zenchef.get("company") or "").strip()
    nom = societe or f"{prenom} {nom_famille}".strip() or "Groupe Zenchef"
    email = (client_zenchef.get("email") or "").strip().lower() or None
    telephone = (client_zenchef.get("phone") or client_zenchef.get("phoneNumber") or "").strip() or None
    if email:
        trouve = session.scalars(select(Client).where(Client.email == email)).first()
        if trouve:
            return trouve
    trouve = session.scalars(select(Client).where(Client.nom_cle == cle_nom_client(nom))).first()
    if trouve:
        return trouve
    return clients.creer(session, acteur, {
        "type": "entreprise" if societe else "particulier", "nom": nom, "contact_prenom": prenom or None,
        "contact_nom": nom_famille or None, "email": email, "telephone": telephone,
        "notes": "Créé par la synchronisation Zenchef.", "confirmer_doublon": True,
    }, exiger_contact=False)


def synchroniser(session: Session, acteur: Acteur, du: Any = None, au: Any = None,
                 appel: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None) -> dict[str, Any]:
    acteur.exiger("fiches")
    if appel is None:
        if not configure():
            raise ErreurMetier("regle_metier", "Zenchef n'est pas configuré (ZENCHEF_API_TOKEN et ZENCHEF_RESTAURANT_ID).")
        appel = _appel_http
    debut = lire_date(du) if du else fiches.aujourd_hui()
    fin = lire_date(au) if au else debut + timedelta(days=60)
    seuil = int(lire_parametres(session).get("zenchef_seuil_couverts", 10))
    creees, deja, ignorees = [], 0, 0
    page = 1
    while True:
        donnees = appel({"restaurantId": os.getenv("ZENCHEF_RESTAURANT_ID", ""), "fromDate": debut.isoformat(),
                         "toDate": fin.isoformat(), "perPage": 250, "page": page})
        liste = donnees.get("reservations") or []
        for r in liste:
            couverts = int(r.get("numberOfPeople") or 0)
            if couverts <= seuil or str(r.get("status") or "").lower() in ("canceled", "cancelled", "annulee"):
                ignorees += 1
                continue
            jour, heure = _debut(r.get("startTime") or "")
            ident = r.get("id") or hashlib.sha1(f"{r.get('startTime')}|{couverts}|{r.get('customer')}".encode()).hexdigest()[:16]
            cle = f"zenchef:{ident}"
            if session.scalars(select(Fiche.id).where(Fiche.cle_idempotence == cle)).first():
                deja += 1
                continue
            client = _client_pour(session, acteur, r.get("customer") or {})
            fiche, _ = fiches.creer(session, acteur, {
                "client_id": str(client.id), "date": jour, "heure": heure, "couverts": min(couverts, 500),
                "cle_idempotence": cle, "notes_salle": "Importée de Zenchef." + (
                    f"\n{r['comment']}" if r.get("comment") else ""),
            })
            creees.append({"fiche_id": str(fiche.id), "client": client.nom, "date": jour.isoformat(),
                           "heure": heure.strftime("%H:%M"), "couverts": couverts})
        if len(liste) < 250:
            break
        page += 1
    journaliser(session, acteur, "zenchef.synchroniser", "zenchef", None,
                f"Zenchef {debut:%d/%m} → {fin:%d/%m} : {len(creees)} fiche(s) créée(s), {deja} déjà importée(s)")
    session.commit()
    return {"creees": creees, "deja_importees": deja, "ignorees": ignorees, "du": debut.isoformat(), "au": fin.isoformat()}
