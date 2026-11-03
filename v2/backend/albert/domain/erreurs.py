"""Erreurs métier, renvoyées telles quelles au site et à ChatGPT.

Forme de la réponse : {"ok": false, "erreur": {"code", "message", "champ", "valeurs_permises"}}.
"""
from __future__ import annotations

from typing import Any, Optional

STATUT_HTTP = {
    "champ_obligatoire": 422,
    "valeur_non_permise": 422,
    "regle_metier": 422,
    "prix_manquant": 422,
    "doublon_probable": 409,
    "conflit_version": 409,
    "confirmation_requise": 409,
    "interdit": 403,
    "non_connecte": 401,
    "introuvable": 404,
}


class ErreurMetier(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        champ: Optional[str] = None,
        valeurs_permises: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.champ = champ
        self.valeurs_permises = valeurs_permises
        self.details = details

    @property
    def statut_http(self) -> int:
        return STATUT_HTTP.get(self.code, 400)

    def en_dict(self) -> dict[str, Any]:
        erreur: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.champ:
            erreur["champ"] = self.champ
        if self.valeurs_permises is not None:
            erreur["valeurs_permises"] = self.valeurs_permises
        if self.details:
            erreur["details"] = self.details
        return {"ok": False, "erreur": erreur}


def introuvable(quoi: str) -> ErreurMetier:
    return ErreurMetier("introuvable", f"{quoi} introuvable.")


def interdit(message: str) -> ErreurMetier:
    return ErreurMetier("interdit", message)
