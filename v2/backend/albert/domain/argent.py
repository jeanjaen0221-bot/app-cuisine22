"""Montants en centimes entiers, TVA comprise."""
from __future__ import annotations

import re
from typing import Optional

from .erreurs import ErreurMetier


def lire_euros(saisie: object) -> Optional[int]:
    """'4,31' / '4.31' / '1 234,50' / 431 (déjà en centimes si int) -> centimes.

    Une saisie vide renvoie None (« prix manquant »).
    """
    if saisie is None:
        return None
    if isinstance(saisie, bool):
        raise ErreurMetier("valeur_non_permise", "Prix invalide.", champ="prix")
    if isinstance(saisie, int):
        if saisie < 0:
            raise ErreurMetier("valeur_non_permise", "Un prix ne peut pas être négatif.", champ="prix")
        return saisie
    texte = str(saisie).strip().replace("€", "").replace(" ", " ").replace(" ", "")
    if not texte:
        return None
    if "," in texte and "." in texte:
        texte = texte.replace(".", "")  # 1.234,50
    texte = texte.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", texte):
        raise ErreurMetier(
            "valeur_non_permise",
            f"Prix invalide : {saisie!r}. Écrire par exemple 4,31.",
            champ="prix",
        )
    euros, _, cents = texte.partition(".")
    return int(euros) * 100 + int((cents + "00")[:2])


def format_euros(centimes: Optional[int]) -> str:
    """431 -> '4,31 €' ; 123450 -> '1 234,50 €' ; None -> 'prix manquant'."""
    if centimes is None:
        return "prix manquant"
    signe = "-" if centimes < 0 else ""
    centimes = abs(centimes)
    euros, reste = divmod(centimes, 100)
    groupes = f"{euros:,}".replace(",", " ")
    return f"{signe}{groupes},{reste:02d} €"
