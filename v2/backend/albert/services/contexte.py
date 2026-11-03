"""Qui agit, et la trace qu'on en garde dans le journal."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..domain.erreurs import ErreurMetier, interdit
from ..models import Audit, Compteur, Parametre

ROLES = ("admin", "equipe", "compta")
DROITS = ("prix", "chatgpt")


@dataclass
class Acteur:
    """La personne (ou ChatGPT au nom d'une personne) qui fait l'action."""

    utilisateur_id: Optional[uuid.UUID]
    email: str
    role: str
    droits: list[str] = field(default_factory=list)
    canal: str = "site"  # site | chatgpt | systeme
    scopes: Optional[set[str]] = None  # pour ChatGPT : droits accordés à la connexion

    @property
    def est_chatgpt(self) -> bool:
        return self.canal == "chatgpt"

    def peut(self, droit: str) -> bool:
        """Droits fonctionnels.

        lecture, fiches, devis (préparer), devis_valider, compta, prix, admin.
        """
        if droit == "admin":
            return self.role == "admin" and not self.est_chatgpt
        if droit in ("devis_valider", "prix"):
            # Jamais ChatGPT : valider/transmettre et toucher aux prix sont humains.
            if self.est_chatgpt:
                return False
            if droit == "prix":
                return self.role == "admin" or "prix" in self.droits
            return self.role in ("admin", "equipe")
        if droit == "compta":
            return self.role in ("admin", "compta") and not self.est_chatgpt
        if droit in ("fiches", "devis"):
            return self.role in ("admin", "equipe")
        if droit == "lecture":
            return self.role in ("admin", "equipe", "compta")
        return False

    def exiger(self, droit: str) -> None:
        if not self.peut(droit):
            if self.est_chatgpt:
                raise interdit("Cette action se fait dans l'outil, par l'équipe : ChatGPT n'y a pas accès.")
            raise interdit("Vous n'avez pas accès à cette action.")


SYSTEME = Acteur(None, "systeme", "admin", canal="systeme")


def _jsonable(valeur: Any) -> Any:
    if isinstance(valeur, dict):
        return {str(k): _jsonable(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple, set)):
        return [_jsonable(v) for v in valeur]
    if isinstance(valeur, (uuid.UUID, date, datetime, time)):
        return str(valeur)
    if isinstance(valeur, bytes):
        return f"<{len(valeur)} octets>"
    return valeur


def journaliser(
    session: Session,
    acteur: Acteur,
    action: str,
    objet_type: str,
    objet_id: Any = None,
    resume: str = "",
    avant: Optional[dict] = None,
    apres: Optional[dict] = None,
) -> None:
    session.add(
        Audit(
            utilisateur_id=acteur.utilisateur_id,
            utilisateur_email=acteur.email,
            canal=acteur.canal,
            action=action,
            objet_type=objet_type,
            objet_id=str(objet_id) if objet_id is not None else None,
            resume=resume[:500],
            avant=_jsonable(avant) if avant else None,
            apres=_jsonable(apres) if apres else None,
        )
    )


def prochain_numero(session: Session, prefixe: str, annee: int) -> str:
    """D-2026-0001, B-2026-0001… Compteur simple (aucune contrainte légale)."""
    cle = f"{prefixe}-{annee}"
    compteur = session.get(Compteur, cle, with_for_update=True)
    if compteur is None:
        compteur = Compteur(cle=cle, valeur=0)
        session.add(compteur)
    compteur.valeur += 1
    session.flush()
    return f"{prefixe}-{annee}-{compteur.valeur:04d}"


def verifier_version(objet: Any, version_attendue: Optional[int], quoi: str) -> None:
    if version_attendue is None:
        return
    if int(version_attendue) != objet.version:
        raise ErreurMetier(
            "conflit_version",
            f"{quoi} a été modifié(e) entre-temps (version {objet.version}, vous aviez la version "
            f"{version_attendue}). Relire puis recommencer.",
            details={"version_actuelle": objet.version},
        )


# --------------------------------------------------------------- paramètres

PARAMETRES_DEFAUT: dict[str, Any] = {
    "restaurant_nom": "Restaurant Albert",
    "restaurant_adresse": "Bruxelles",
    "restaurant_telephone": "",
    "restaurant_email": "info@albert.brussels",
    "restaurant_tva": "",
    "validite_devis_jours": 30,
    "conditions_paiement_defaut": "Paiement à 30 jours",
    "mentions_devis": "Prix TVA comprise. Devis valable jusqu'à la date indiquée.",
    "heures_proposees": ["12:00", "12:30", "13:00", "13:30", "19:30", "20:00"],
}


def lire_parametres(session: Session) -> dict[str, Any]:
    valeurs = dict(PARAMETRES_DEFAUT)
    for p in session.query(Parametre).all():
        valeurs[p.cle] = p.valeur
    return valeurs


def ecrire_parametres(session: Session, acteur: Acteur, changements: dict[str, Any]) -> dict[str, Any]:
    acteur.exiger("admin")
    inconnus = [k for k in changements if k not in PARAMETRES_DEFAUT]
    if inconnus:
        raise ErreurMetier("valeur_non_permise", f"Paramètre(s) inconnu(s) : {', '.join(inconnus)}.",
                           valeurs_permises=list(PARAMETRES_DEFAUT))
    avant = lire_parametres(session)
    for cle, valeur in changements.items():
        if cle == "validite_devis_jours":
            valeur = int(valeur)
            if not 1 <= valeur <= 365:
                raise ErreurMetier("regle_metier", "Validité d'un devis : entre 1 et 365 jours.", champ=cle)
        ligne = session.get(Parametre, cle)
        if ligne is None:
            session.add(Parametre(cle=cle, valeur=valeur))
        else:
            ligne.valeur = valeur
    journaliser(session, acteur, "parametres.modifier", "parametres", None, "Paramètres modifiés",
                {k: avant.get(k) for k in changements}, changements)
    session.commit()
    return lire_parametres(session)
