"""Comptes, mots de passe et sessions."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import reglages
from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import lire_email, texte_court
from ..models import Utilisateur
from .contexte import DROITS, ROLES, Acteur, journaliser

ITERATIONS = 600_000
TENTATIVES_MAX = 5
FENETRE_SECONDES = 15 * 60


def hacher(mot_de_passe: str) -> str:
    sel = secrets.token_bytes(16)
    derive = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), sel, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${sel.hex()}${derive.hex()}"


def verifier(mot_de_passe: str, encode: str) -> bool:
    try:
        algo, iterations, sel, condense = encode.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        candidat = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), bytes.fromhex(sel), int(iterations))
        return hmac.compare_digest(candidat.hex(), condense)
    except (TypeError, ValueError):
        return False


def valider_mot_de_passe(mot_de_passe: str) -> None:
    if len(mot_de_passe or "") < 12:
        raise ErreurMetier("regle_metier", "Le mot de passe doit comporter au moins 12 caractères.", champ="mot_de_passe")


def utilisateur_dict(u: Utilisateur) -> dict[str, Any]:
    return {"id": str(u.id), "email": u.email, "nom": u.nom, "role": u.role, "droits": u.droits or [],
            "actif": u.actif, "derniere_connexion": u.derniere_connexion.isoformat() if u.derniere_connexion else None}


def acteur_de(u: Utilisateur, canal: str = "site", scopes: Optional[set[str]] = None) -> Acteur:
    return Acteur(u.id, u.email, u.role, list(u.droits or []), canal, scopes)


# --------------------------------------------------------------- limitation des tentatives

_echecs: dict[str, deque] = defaultdict(deque)


def _cle_tentative(email: str, ip: str) -> str:
    return f"{email}|{ip}"


def _verifier_limite(cle_t: str) -> None:
    file = _echecs[cle_t]
    while file and file[0] < time.time() - FENETRE_SECONDES:
        file.popleft()
    if len(file) >= TENTATIVES_MAX:
        raise ErreurMetier("interdit", "Trop de tentatives. Réessayer dans un quart d'heure.")


def authentifier(session: Session, email: str, mot_de_passe: str, ip: str = "") -> Utilisateur:
    email = (email or "").strip().lower()
    cle_t = _cle_tentative(email, ip)
    _verifier_limite(cle_t)
    u = session.scalars(select(Utilisateur).where(Utilisateur.email == email)).first()
    if u is None or not u.actif or not verifier(mot_de_passe or "", u.mot_de_passe):
        _echecs[cle_t].append(time.time())
        raise ErreurMetier("non_connecte", "Adresse e-mail ou mot de passe incorrect.")
    _echecs.pop(cle_t, None)
    u.derniere_connexion = datetime.now(timezone.utc)
    session.commit()
    return u


# --------------------------------------------------------------- jetons de session

def emettre_jeton(u: Utilisateur) -> str:
    maintenant = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(u.id), "typ": "session", "iat": maintenant,
                       "exp": maintenant + timedelta(hours=reglages.session_heures)}, reglages.secret, algorithm="HS256")


def lire_jeton(session: Session, jeton: str) -> Utilisateur:
    try:
        contenu = jwt.decode(jeton, reglages.secret, algorithms=["HS256"])
        if contenu.get("typ") != "session":
            raise ValueError
        u = session.get(Utilisateur, uuid.UUID(contenu["sub"]))
    except (jwt.InvalidTokenError, ValueError, KeyError):
        u = None
    if u is None or not u.actif:
        raise ErreurMetier("non_connecte", "Session expirée : se reconnecter.")
    return u


# --------------------------------------------------------------- gestion des comptes

def configuration_requise(session: Session) -> bool:
    return not session.scalar(select(func.count()).select_from(Utilisateur))


def creer_premier_admin(session: Session, email: str, mot_de_passe: str, nom: str = "") -> Utilisateur:
    if not configuration_requise(session):
        raise ErreurMetier("interdit", "Un compte existe déjà.")
    valider_mot_de_passe(mot_de_passe)
    u = Utilisateur(email=lire_email(email) or "", nom=nom or "", mot_de_passe=hacher(mot_de_passe), role="admin")
    if not u.email:
        raise ErreurMetier("champ_obligatoire", "L'e-mail est obligatoire.", champ="email")
    session.add(u)
    session.commit()
    return u


def _droits(valeurs: Any) -> list[str]:
    droits = sorted({d for d in (valeurs or []) if d in DROITS})
    return droits


def creer(session: Session, acteur: Acteur, donnees: dict[str, Any]) -> Utilisateur:
    acteur.exiger("admin")
    email = lire_email(donnees.get("email"))
    if not email:
        raise ErreurMetier("champ_obligatoire", "L'e-mail est obligatoire.", champ="email")
    if session.scalars(select(Utilisateur).where(Utilisateur.email == email)).first():
        raise ErreurMetier("doublon_probable", "Cette adresse e-mail est déjà utilisée.", champ="email")
    role = donnees.get("role") or "equipe"
    if role not in ROLES:
        raise ErreurMetier("valeur_non_permise", "Rôle inconnu.", champ="role", valeurs_permises=list(ROLES))
    valider_mot_de_passe(donnees.get("mot_de_passe") or "")
    u = Utilisateur(email=email, nom=texte_court(donnees.get("nom"), "nom", 200) or "", role=role,
                    droits=_droits(donnees.get("droits")), mot_de_passe=hacher(donnees["mot_de_passe"]))
    session.add(u)
    session.flush()
    journaliser(session, acteur, "utilisateur.creer", "utilisateur", u.id, f"{u.email} ({u.role})")
    session.commit()
    return u


def modifier(session: Session, acteur: Acteur, utilisateur_id: Any, donnees: dict[str, Any]) -> Utilisateur:
    acteur.exiger("admin")
    u = session.get(Utilisateur, uuid.UUID(str(utilisateur_id)))
    if u is None:
        raise introuvable("Utilisateur")
    if "role" in donnees:
        if donnees["role"] not in ROLES:
            raise ErreurMetier("valeur_non_permise", "Rôle inconnu.", champ="role", valeurs_permises=list(ROLES))
        if u.id == acteur.utilisateur_id and donnees["role"] != "admin":
            raise ErreurMetier("regle_metier", "Vous ne pouvez pas retirer votre propre accès administrateur.")
        u.role = donnees["role"]
    if "droits" in donnees:
        u.droits = _droits(donnees["droits"])
    if "nom" in donnees:
        u.nom = texte_court(donnees["nom"], "nom", 200) or ""
    if "actif" in donnees:
        if u.id == acteur.utilisateur_id and not donnees["actif"]:
            raise ErreurMetier("regle_metier", "Vous ne pouvez pas désactiver votre propre compte.")
        u.actif = bool(donnees["actif"])
    if donnees.get("mot_de_passe"):
        valider_mot_de_passe(donnees["mot_de_passe"])
        u.mot_de_passe = hacher(donnees["mot_de_passe"])
    admins_actifs = session.scalar(select(func.count()).select_from(Utilisateur)
                                   .where(Utilisateur.role == "admin", Utilisateur.actif.is_(True)))
    if not admins_actifs:
        raise ErreurMetier("regle_metier", "Au moins un administrateur actif doit être conservé.")
    journaliser(session, acteur, "utilisateur.modifier", "utilisateur", u.id, u.email,
                None, {k: v for k, v in donnees.items() if k != "mot_de_passe"})
    session.commit()
    return u
