"""Dépendances communes des routes : session, utilisateur connecté, réponses PDF."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import obtenir_session
from ..domain.erreurs import ErreurMetier
from ..services import comptes
from ..services.contexte import Acteur

COOKIE_SESSION = "albert_session"


def session_db(session: Session = Depends(obtenir_session)) -> Session:
    return session


def acteur_connecte(request: Request, session: Session = Depends(session_db)) -> Acteur:
    jeton = request.cookies.get(COOKIE_SESSION)
    if not jeton:
        raise ErreurMetier("non_connecte", "Connexion requise.")
    return comptes.acteur_de(comptes.lire_jeton(session, jeton))


def reponse_pdf(contenu: bytes, nom: str, telecharger: bool = False) -> Response:
    disposition = "attachment" if telecharger else "inline"
    return Response(contenu, media_type="application/pdf",
                    headers={"Content-Disposition": f'{disposition}; filename="{nom}"',
                             "Cache-Control": "no-store"})


def corps(donnees: Any) -> dict[str, Any]:
    if not isinstance(donnees, dict):
        raise ErreurMetier("valeur_non_permise", "Le corps de la requête doit être un objet JSON.")
    return donnees
