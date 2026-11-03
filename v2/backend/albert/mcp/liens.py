"""Liens PDF temporaires (15 minutes) donnés à ChatGPT : signés, sans session ni cookie."""
from __future__ import annotations

import time
from typing import Any

import jwt

from ..config import reglages
from ..domain.erreurs import ErreurMetier

TYPES = ("fiche_salle", "fiche_cuisine", "fiche_complete", "devis", "bon")
DUREE = 15 * 60


def lien_pdf(type_document: str, identifiant: Any) -> str:
    if type_document not in TYPES:
        raise ErreurMetier("valeur_non_permise", "Type de document inconnu.", champ="type", valeurs_permises=list(TYPES))
    jeton = jwt.encode({"typ": "pdf", "doc": type_document, "id": str(identifiant), "exp": int(time.time()) + DUREE},
                       reglages.secret, algorithm="HS256")
    return f"{reglages.url_publique}/api/pdf/{jeton}"


def lire_lien(jeton: str) -> tuple[str, str]:
    try:
        contenu = jwt.decode(jeton, reglages.secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise ErreurMetier("introuvable", "Lien expiré ou invalide : en demander un nouveau.")
    if contenu.get("typ") != "pdf" or contenu.get("doc") not in TYPES:
        raise ErreurMetier("introuvable", "Lien invalide.")
    return contenu["doc"], contenu["id"]
