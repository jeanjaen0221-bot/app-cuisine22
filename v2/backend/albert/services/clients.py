"""Clients : une seule fiche par client, réutilisée pour toutes ses réservations."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import cle, cle_nom_client, lire_email, lire_tva, nettoyer_notes, texte_court
from ..models import Client
from .contexte import Acteur, journaliser, verifier_version

CHAMPS_TEXTE = {
    "contact_prenom": 100, "contact_nom": 100, "telephone": 50, "rue": 200, "numero": 20, "boite": 20,
    "code_postal": 20, "ville": 100, "pays": 100, "reference_po": 100, "conditions_paiement": 200,
}


def client_dict(c: Client) -> dict[str, Any]:
    return {
        "id": str(c.id), "type": c.type, "nom": c.nom, "contact_prenom": c.contact_prenom,
        "contact_nom": c.contact_nom, "email": c.email, "telephone": c.telephone, "langue": c.langue,
        "rue": c.rue, "numero": c.numero, "boite": c.boite, "code_postal": c.code_postal, "ville": c.ville,
        "pays": c.pays, "tva": c.tva, "reference_po": c.reference_po, "conditions_paiement": c.conditions_paiement,
        "notes": c.notes, "preferences": c.preferences, "archive": c.archive, "version": c.version,
        "adresse_complete": adresse_complete(c), "manques_facturation": manques_facturation(c),
    }


def adresse_complete(c: Client) -> bool:
    return all([c.rue, c.numero, c.code_postal, c.ville, c.pays])


def manques_facturation(c: Client) -> list[str]:
    """Ce qu'il faut pour qu'un devis puisse être validé."""
    manques = []
    if not (c.email or c.telephone):
        manques.append("email ou téléphone")
    if c.type == "entreprise":
        for champ, libelle in (("rue", "rue"), ("numero", "numéro"), ("code_postal", "code postal"),
                               ("ville", "ville"), ("pays", "pays")):
            if not getattr(c, champ):
                manques.append(libelle)
    return manques


def rechercher(session: Session, q: Optional[str] = None, email: Optional[str] = None, tva: Optional[str] = None,
               inclure_archives: bool = False, limite: int = 50, decalage: int = 0) -> list[Client]:
    stmt = select(Client)
    if not inclure_archives:
        stmt = stmt.where(Client.archive.is_(False))
    if email:
        stmt = stmt.where(Client.email == email.strip().lower())
    if tva:
        try:
            stmt = stmt.where(Client.tva == lire_tva(tva))
        except ErreurMetier:
            stmt = stmt.where(Client.tva == tva)
    clients = list(session.scalars(stmt.order_by(Client.nom)))
    if q:
        mots = cle(q).split()

        def correspond(c: Client) -> bool:
            texte = cle(" ".join(filter(None, [c.nom, c.contact_prenom, c.contact_nom, c.email, c.telephone, c.tva])))
            return all(m in texte for m in mots)

        clients = [c for c in clients if correspond(c)]
    return clients[decalage: decalage + limite]


def _doublons(session: Session, nom_cle: str, email: Optional[str], tva: Optional[str],
              sauf: Optional[uuid.UUID]) -> list[Client]:
    conditions = [Client.nom_cle == nom_cle]
    if email:
        conditions.append(Client.email == email)
    if tva:
        conditions.append(Client.tva == tva)
    stmt = select(Client).where(or_(*conditions))
    return [c for c in session.scalars(stmt) if c.id != sauf]


def _valider(donnees: dict[str, Any], partiel: bool) -> dict[str, Any]:
    v: dict[str, Any] = {}
    if "type" in donnees or not partiel:
        t = donnees.get("type") or "particulier"
        if t not in ("particulier", "entreprise"):
            raise ErreurMetier("valeur_non_permise", "Type de client inconnu.", champ="type",
                               valeurs_permises=["particulier", "entreprise"])
        v["type"] = t
    if "nom" in donnees or not partiel:
        v["nom"] = texte_court(donnees.get("nom"), "nom", 200, obligatoire=True)
        v["nom_cle"] = cle_nom_client(v["nom"])
    if "email" in donnees:
        v["email"] = lire_email(donnees["email"])
    if "tva" in donnees:
        v["tva"] = lire_tva(donnees["tva"])
    if "langue" in donnees:
        langue = donnees["langue"] or "fr"
        if langue not in ("fr", "nl", "en"):
            raise ErreurMetier("valeur_non_permise", "Langue inconnue.", champ="langue", valeurs_permises=["fr", "nl", "en"])
        v["langue"] = langue
    for champ, maximum in CHAMPS_TEXTE.items():
        if champ in donnees:
            v[champ] = texte_court(donnees[champ], champ, maximum)
    if v.get("pays") is None and "pays" in v:
        v["pays"] = "Belgique"
    for champ in ("notes", "preferences"):
        if champ in donnees:
            v[champ] = nettoyer_notes(donnees[champ], 4000)
    if "archive" in donnees:
        v["archive"] = bool(donnees["archive"])
    return v


def creer(session: Session, acteur: Acteur, donnees: dict[str, Any], exiger_contact: bool = True) -> Client:
    """exiger_contact=False seulement pour un import (Zenchef, reprise) : le client est complété ensuite."""
    acteur.exiger("fiches")
    v = _valider(donnees, partiel=False)
    if exiger_contact and not (v.get("email") or v.get("telephone")):
        raise ErreurMetier("champ_obligatoire", "Indiquer au moins un email ou un téléphone.", champ="email")
    if not donnees.get("confirmer_doublon"):
        proches = _doublons(session, v["nom_cle"], v.get("email"), v.get("tva"), None)
        if proches:
            raise ErreurMetier(
                "doublon_probable",
                "Un client proche existe déjà : " + ", ".join(c.nom for c in proches[:5])
                + ". Utiliser ce client, ou confirmer la création d'un nouveau.",
                details={"clients": [{"id": str(c.id), "nom": c.nom, "email": c.email} for c in proches[:5]]},
            )
    client = Client(**v)
    session.add(client)
    session.flush()
    journaliser(session, acteur, "client.creer", "client", client.id, client.nom, None, client_dict(client))
    session.commit()
    return client


def modifier(session: Session, acteur: Acteur, client_id: uuid.UUID, donnees: dict[str, Any],
             version: Optional[int] = None) -> Client:
    acteur.exiger("fiches")
    client = obtenir(session, client_id)
    verifier_version(client, version, "Le client")
    avant = client_dict(client)
    v = _valider(donnees, partiel=True)
    if "archive" in v and acteur.est_chatgpt:
        raise ErreurMetier("interdit", "L'archivage d'un client se fait dans l'outil.")
    for k, valeur in v.items():
        setattr(client, k, valeur)
    if not (client.email or client.telephone):
        raise ErreurMetier("champ_obligatoire", "Indiquer au moins un email ou un téléphone.", champ="email")
    client.version += 1
    session.flush()
    journaliser(session, acteur, "client.modifier", "client", client.id, client.nom, avant, client_dict(client))
    session.commit()
    return client


def obtenir(session: Session, client_id: Any) -> Client:
    try:
        client = session.get(Client, uuid.UUID(str(client_id)))
    except ValueError:
        client = None
    if client is None:
        raise introuvable("Client")
    return client
