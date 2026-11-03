"""Plaintes (rapports d'incident client) et notes de l'équipe.

Une plainte est rattachée, si on les connaît, au client et à la fiche concernés.
ChatGPT peut en rédiger une en brouillon à partir du récit de l'utilisateur ;
l'équipe la relit, la passe en « ouverte », puis en « traitée ».
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import cle, lire_date, lire_heure, nettoyer_notes, texte_court
from ..models import Note, Plainte
from . import clients, fiches
from .contexte import Acteur, journaliser, verifier_version

GRAVITES = {"faible": "Faible", "moyen": "Moyen", "eleve": "Élevé"}
STATUTS = {"brouillon": "Brouillon", "ouverte": "Ouverte", "traitee": "Traitée"}
TEXTES = ("recit_brut", "contexte", "description", "reaction_personnel", "consequences", "mesures_prises", "observations")
NON_PRECISE = "non precise"


def plainte_dict(p: Plainte) -> dict[str, Any]:
    return {
        "id": str(p.id), "version": p.version, "date": p.date.isoformat(),
        "heure": p.heure.strftime("%H:%M") if p.heure else None, "lieu": p.lieu, "employes": p.employes,
        "client_nom": p.client_nom or (p.client.nom if p.client else None),
        "client_id": str(p.client_id) if p.client_id else None, "fiche_id": str(p.fiche_id) if p.fiche_id else None,
        **{t: getattr(p, t) for t in TEXTES},
        "gravite": p.gravite, "gravite_libelle": GRAVITES[p.gravite],
        "statut": p.statut, "statut_libelle": STATUTS[p.statut],
        "cree_le": p.cree_le.isoformat(), "modifie_le": p.modifie_le.isoformat() if p.modifie_le else None,
    }


def obtenir(session: Session, plainte_id: Any) -> Plainte:
    try:
        p = session.get(Plainte, uuid.UUID(str(plainte_id)))
    except ValueError:
        p = None
    if p is None:
        raise introuvable("Plainte")
    return p


def lister(session: Session, q: Optional[str] = None, statut: Optional[str] = None,
           client_id: Optional[str] = None, limite: int = 200) -> list[Plainte]:
    stmt = select(Plainte)
    if statut:
        stmt = stmt.where(Plainte.statut.in_(statut.split(",")))
    if client_id:
        stmt = stmt.where(Plainte.client_id == uuid.UUID(str(client_id)))
    liste = list(session.scalars(stmt.order_by(Plainte.date.desc(), Plainte.cree_le.desc())))
    if q:
        mots = cle(q).split()
        liste = [p for p in liste if all(m in cle(" ".join(filter(None, [p.client_nom, p.lieu, p.employes, p.recit_brut,
                                                                         p.description]))) for m in mots)]
    return liste[:limite]


def _lire_gravite(valeur: Any) -> str:
    k = cle(valeur).replace("elevee", "eleve").replace("moyenne", "moyen").replace("grave", "eleve")
    if k not in GRAVITES:
        raise ErreurMetier("valeur_non_permise", "Gravité inconnue.", champ="gravite", valeurs_permises=list(GRAVITES.values()))
    return k


def _appliquer(session: Session, p: Plainte, donnees: dict[str, Any], nouvelle: bool) -> None:
    if "date" in donnees or nouvelle:
        p.date = lire_date(donnees.get("date") or fiches.aujourd_hui())
    if "heure" in donnees:
        h = donnees.get("heure")
        p.heure = None if not h or cle(h) == NON_PRECISE else lire_heure(h)
    for champ, maximum in (("lieu", 200), ("employes", 500), ("client_nom", 200)):
        if champ in donnees:
            valeur = texte_court(donnees[champ], champ, maximum)
            setattr(p, champ, None if valeur and cle(valeur) == NON_PRECISE else valeur)
    for champ in TEXTES:
        if champ in donnees:
            setattr(p, champ, nettoyer_notes(donnees[champ], 8000))
    if "gravite" in donnees or nouvelle:
        p.gravite = _lire_gravite(donnees.get("gravite") or "faible")
    if "fiche_id" in donnees:
        if donnees["fiche_id"]:
            fiche = fiches.obtenir(session, donnees["fiche_id"])
            p.fiche_id = fiche.id
            p.client_id = p.client_id or fiche.client_id
        else:
            p.fiche_id = None
    if "client_id" in donnees:
        p.client_id = clients.obtenir(session, donnees["client_id"]).id if donnees["client_id"] else None
    if not (p.recit_brut or p.description):
        raise ErreurMetier("champ_obligatoire", "Décrire ce qui s'est passé (récit ou description).", champ="recit_brut")


def creer(session: Session, acteur: Acteur, donnees: dict[str, Any]) -> Plainte:
    acteur.exiger("fiches")
    # Rédigée par ChatGPT : toujours un brouillon, à relire par l'équipe.
    statut = "brouillon" if acteur.est_chatgpt else (donnees.get("statut") or "ouverte")
    if statut not in STATUTS:
        raise ErreurMetier("valeur_non_permise", "Statut inconnu.", champ="statut", valeurs_permises=list(STATUTS))
    p = Plainte(statut=statut, version=1)
    with session.no_autoflush:
        _appliquer(session, p, donnees, nouvelle=True)
    session.add(p)
    session.flush()
    journaliser(session, acteur, "plainte.creer", "plainte", p.id,
                f"Plainte du {p.date:%d/%m/%Y}" + (f" — {p.client_nom}" if p.client_nom else ""))
    session.commit()
    return p


def modifier(session: Session, acteur: Acteur, plainte_id: Any, donnees: dict[str, Any],
             version: Optional[int] = None) -> Plainte:
    acteur.exiger("fiches")
    p = obtenir(session, plainte_id)
    verifier_version(p, version, "La plainte")
    if "statut" in donnees:
        if acteur.est_chatgpt:
            raise ErreurMetier("interdit", "Le statut d'une plainte se change dans l'outil.")
        if donnees["statut"] not in STATUTS:
            raise ErreurMetier("valeur_non_permise", "Statut inconnu.", champ="statut", valeurs_permises=list(STATUTS))
        p.statut = donnees["statut"]
    if acteur.est_chatgpt and p.statut != "brouillon":
        raise ErreurMetier("interdit", "Cette plainte a été validée par l'équipe : elle se modifie dans l'outil.")
    _appliquer(session, p, donnees, nouvelle=False)
    p.version += 1
    journaliser(session, acteur, "plainte.modifier", "plainte", p.id, f"Plainte du {p.date:%d/%m/%Y} ({STATUTS[p.statut]})")
    session.commit()
    return p


def supprimer(session: Session, acteur: Acteur, plainte_id: Any) -> None:
    acteur.exiger("admin")
    p = obtenir(session, plainte_id)
    journaliser(session, acteur, "plainte.supprimer", "plainte", p.id, f"Plainte du {p.date:%d/%m/%Y} supprimée",
                plainte_dict(p))
    session.delete(p)
    session.commit()


# --------------------------------------------------------------- notes

def note_dict(n: Note) -> dict[str, Any]:
    return {"id": str(n.id), "auteur": n.auteur, "contenu": n.contenu, "epinglee": n.epinglee,
            "cree_le": n.cree_le.isoformat(), "modifie_le": n.modifie_le.isoformat() if n.modifie_le else None}


def lister_notes(session: Session) -> list[Note]:
    return list(session.scalars(select(Note).order_by(Note.epinglee.desc(), Note.modifie_le.desc()).limit(200)))


def enregistrer_note(session: Session, acteur: Acteur, donnees: dict[str, Any], note_id: Any = None) -> Note:
    acteur.exiger("fiches")
    if note_id:
        n = session.get(Note, uuid.UUID(str(note_id)))
        if n is None:
            raise introuvable("Note")
    else:
        n = Note(auteur=acteur.email)
        session.add(n)
    if "contenu" in donnees or not note_id:
        contenu = nettoyer_notes(donnees.get("contenu"), 2000)
        if not contenu:
            raise ErreurMetier("champ_obligatoire", "La note est vide.", champ="contenu")
        n.contenu = contenu
    if "epinglee" in donnees:
        n.epinglee = bool(donnees["epinglee"])
    session.commit()
    return n


def supprimer_note(session: Session, acteur: Acteur, note_id: Any) -> None:
    acteur.exiger("fiches")
    n = session.get(Note, uuid.UUID(str(note_id)))
    if n is None:
        raise introuvable("Note")
    session.delete(n)
    session.commit()
