"""Devis (TVA comprise) préparés depuis une fiche, puis transmis à la comptabilité.

Cycle : brouillon → validé → transmis → envoyé (par la compta) → accepté / refusé.
Un devis transmis ne change plus : on crée une nouvelle version (l'ancienne passe en « remplacé »).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import reglages
from ..domain.argent import format_euros
from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import lire_date, nettoyer_notes
from ..domain.regles import LIBELLES_UNITES, calculer_devis, signature_fiche
from ..models import Devis, DevisLigne
from ..pdf.documents import pdf_devis
from . import catalogue, clients, fiches
from .contexte import Acteur, journaliser, lire_parametres, prochain_numero

LIBELLES_STATUTS = {
    "brouillon": "Brouillon", "valide": "Validé", "transmis": "Transmis à la compta",
    "envoye": "Envoyé au client", "accepte": "Accepté", "refuse": "Refusé", "remplace": "Remplacé",
}


def obtenir(session: Session, devis_id: Any) -> Devis:
    try:
        did = uuid.UUID(str(devis_id))
    except ValueError:
        raise introuvable("Devis")
    devis = session.scalars(select(Devis).where(Devis.id == did).options(selectinload(Devis.lignes))).first()
    if devis is None:
        raise introuvable("Devis")
    return devis


def manques(devis: Devis) -> list[str]:
    sortie = [f"Prix manquant : {l.libelle} (à compléter dans le menu Prix, puis « Actualiser »)."
              for l in devis.lignes if l.prix_unitaire_centimes is None]
    sortie += [f"Client : {m} manquant(e)." for m in clients.manques_facturation(devis.client)]
    if not devis.lignes:
        sortie.append("Le devis n'a aucune ligne.")
    return sortie


def devis_dict(session: Session, d: Devis) -> dict[str, Any]:
    aujourd_hui = fiches.aujourd_hui()
    expire = d.statut in ("transmis", "envoye") and d.date_validite < aujourd_hui
    a_jour = d.signature_fiche == signature_fiche(d.fiche) if d.statut != "remplace" else True
    return {
        "id": str(d.id), "numero": d.numero, "version": d.version, "reference": f"{d.numero} v{d.version}",
        "statut": d.statut, "statut_libelle": LIBELLES_STATUTS[d.statut] + (" (expiré)" if expire else ""),
        "expire": expire, "fiche_id": str(d.fiche_id), "client_id": str(d.client_id), "client_nom": d.client.nom,
        "date_evenement": d.fiche.date.isoformat(), "heure_evenement": d.fiche.heure.strftime("%H:%M"),
        "couverts": d.couverts, "date_validite": d.date_validite.isoformat(),
        "total_centimes": d.total_centimes, "total": format_euros(d.total_centimes),
        "remarques_client": d.remarques_client, "remarques_compta": d.remarques_compta,
        "lignes": [
            {"id": str(l.id), "categorie": l.categorie, "libelle": l.libelle, "quantite": l.quantite,
             "unite": l.unite, "unite_libelle": LIBELLES_UNITES.get(l.unite, l.unite),
             "produit_id": str(l.produit_id) if l.produit_id else None,
             "prix_unitaire_centimes": l.prix_unitaire_centimes, "prix_unitaire": format_euros(l.prix_unitaire_centimes),
             "total_centimes": l.total_centimes, "total": format_euros(l.total_centimes)}
            for l in d.lignes
        ],
        "manques": manques(d) if d.statut in ("brouillon", "valide") else [],
        "a_mettre_a_jour": not a_jour,
        "transmis_le": d.transmis_le.isoformat() if d.transmis_le else None, "transmis_par": d.transmis_par,
        "envoye_le": d.envoye_le.isoformat() if d.envoye_le else None,
        "reponse_le": d.reponse_le.isoformat() if d.reponse_le else None,
        "version_suivante_id": str(d.version_suivante_id) if d.version_suivante_id else None,
        "cree_le": d.cree_le.isoformat(), "mention": "Prix TVA comprise",
    }


def lister(session: Session, statut: Optional[str] = None, client_id: Optional[str] = None,
           fiche_id: Optional[str] = None, inclure_remplaces: bool = False) -> list[Devis]:
    stmt = select(Devis).options(selectinload(Devis.lignes))
    if statut:
        stmt = stmt.where(Devis.statut.in_(statut.split(",")))
    elif not inclure_remplaces:
        stmt = stmt.where(Devis.statut != "remplace")
    if client_id:
        stmt = stmt.where(Devis.client_id == uuid.UUID(str(client_id)))
    if fiche_id:
        stmt = stmt.where(Devis.fiche_id == uuid.UUID(str(fiche_id)))
    return list(session.scalars(stmt.order_by(Devis.cree_le.desc())))


def _remplir(session: Session, devis: Devis) -> list[str]:
    """(Re)calcule les lignes depuis la fiche, aux prix actuels du menu Prix."""
    fiche = devis.fiche
    calcul = calculer_devis(fiche, catalogue.formules_par_services(session))
    devis.lignes.clear()
    session.flush()
    for i, l in enumerate(calcul.lignes):
        devis.lignes.append(DevisLigne(
            ordre=i, categorie=l.categorie, produit_id=l.produit_id, libelle=l.libelle, quantite=l.quantite,
            unite=l.unite, prix_unitaire_centimes=l.prix_unitaire_centimes, total_centimes=l.total_centimes,
        ))
    devis.couverts = fiche.couverts
    devis.client_id = fiche.client_id
    devis.total_centimes = calcul.total_centimes
    devis.signature_fiche = signature_fiche(fiche)
    return calcul.alertes


def preparer(session: Session, acteur: Acteur, fiche_id: Any, donnees: Optional[dict[str, Any]] = None) -> tuple[Devis, list[str]]:
    """Crée le devis d'une fiche (ou actualise le brouillon existant)."""
    acteur.exiger("devis")
    donnees = donnees or {}
    fiche = fiches.obtenir(session, fiche_id)
    if fiche.statut == "annulee":
        raise ErreurMetier("regle_metier", "La fiche est annulée : pas de devis.")
    courant = fiches.devis_courant(session, fiche.id)
    if courant is not None:
        if courant.statut in ("brouillon", "valide"):
            return actualiser(session, acteur, courant.id, donnees)
        raise ErreurMetier(
            "regle_metier",
            f"Le devis {courant.numero} v{courant.version} est déjà « {LIBELLES_STATUTS[courant.statut]} ». "
            "Pour un changement, créer une nouvelle version.",
            details={"devis_id": str(courant.id)},
        )
    params = lire_parametres(session)
    devis = Devis(
        numero=prochain_numero(session, "D", fiches.aujourd_hui().year), version=1, fiche_id=fiche.id,
        client_id=fiche.client_id, statut="brouillon", couverts=fiche.couverts,
        date_validite=fiches.aujourd_hui() + timedelta(days=int(params["validite_devis_jours"])),
    )
    devis.fiche = fiche
    session.add(devis)
    _modifier_champs(devis, donnees)
    alertes = _remplir(session, devis)
    session.flush()
    journaliser(session, acteur, "devis.preparer", "devis", devis.id,
                f"{devis.numero} v1 — {fiche.client.nom} — {format_euros(devis.total_centimes)}")
    session.commit()
    return obtenir(session, devis.id), alertes


def _modifier_champs(devis: Devis, donnees: dict[str, Any]) -> None:
    if "remarques_client" in donnees:
        devis.remarques_client = nettoyer_notes(donnees["remarques_client"], 2000)
    if "remarques_compta" in donnees:
        devis.remarques_compta = nettoyer_notes(donnees["remarques_compta"], 2000)
    if donnees.get("validite_jours"):
        devis.date_validite = fiches.aujourd_hui() + timedelta(days=max(1, min(int(donnees["validite_jours"]), 365)))
    if donnees.get("date_validite"):
        devis.date_validite = lire_date(donnees["date_validite"], "date_validite")


def _exiger_statut(devis: Devis, *statuts: str) -> None:
    if devis.statut not in statuts:
        permis = ", ".join(LIBELLES_STATUTS[s] for s in statuts)
        raise ErreurMetier("regle_metier",
                           f"Le devis est « {LIBELLES_STATUTS[devis.statut]} » : action possible seulement s'il est {permis}.")


def actualiser(session: Session, acteur: Acteur, devis_id: Any, donnees: Optional[dict[str, Any]] = None) -> tuple[Devis, list[str]]:
    """Recalcule un devis en brouillon depuis la fiche actuelle (un devis validé redevient brouillon)."""
    acteur.exiger("devis")
    devis = obtenir(session, devis_id)
    _exiger_statut(devis, "brouillon", "valide")
    avant_total = devis.total_centimes
    devis.statut = "brouillon"
    _modifier_champs(devis, donnees or {})
    alertes = _remplir(session, devis)
    journaliser(session, acteur, "devis.actualiser", "devis", devis.id,
                f"{devis.numero} v{devis.version} : {format_euros(avant_total)} → {format_euros(devis.total_centimes)}")
    session.commit()
    return obtenir(session, devis.id), alertes


def modifier(session: Session, acteur: Acteur, devis_id: Any, donnees: dict[str, Any]) -> Devis:
    acteur.exiger("devis")
    devis = obtenir(session, devis_id)
    _exiger_statut(devis, "brouillon", "valide")
    _modifier_champs(devis, donnees)
    journaliser(session, acteur, "devis.modifier", "devis", devis.id, f"{devis.numero} v{devis.version}")
    session.commit()
    return devis


def valider(session: Session, acteur: Acteur, devis_id: Any) -> Devis:
    acteur.exiger("devis_valider")
    devis = obtenir(session, devis_id)
    _exiger_statut(devis, "brouillon")
    if devis.signature_fiche != signature_fiche(devis.fiche):
        raise ErreurMetier("regle_metier", "La fiche a changé depuis le calcul : « Actualiser » le devis d'abord.")
    restants = manques(devis)
    if restants:
        raise ErreurMetier("prix_manquant" if any("Prix" in m for m in restants) else "regle_metier",
                           "Le devis ne peut pas être validé : " + " ".join(restants), details={"manques": restants})
    devis.statut = "valide"
    journaliser(session, acteur, "devis.valider", "devis", devis.id, f"{devis.numero} v{devis.version}")
    session.commit()
    return devis


def devalider(session: Session, acteur: Acteur, devis_id: Any) -> Devis:
    acteur.exiger("devis_valider")
    devis = obtenir(session, devis_id)
    _exiger_statut(devis, "valide")
    devis.statut = "brouillon"
    journaliser(session, acteur, "devis.devalider", "devis", devis.id, f"{devis.numero} v{devis.version}")
    session.commit()
    return devis


def _evenement(devis: Devis) -> dict[str, Any]:
    f = devis.fiche
    return {"date": f.date.isoformat(), "heure": f.heure.strftime("%H:%M"), "espace": f.espace}


def generer_pdf(session: Session, devis: Devis) -> bytes:
    """PDF figé s'il a été transmis ; sinon aperçu marqué BROUILLON."""
    if devis.pdf:
        return devis.pdf
    params = lire_parametres(session)
    return pdf_devis(devis_dict(session, devis), clients.client_dict(devis.client), _evenement(devis), params,
                     brouillon=True)


def transmettre(session: Session, acteur: Acteur, devis_id: Any) -> Devis:
    """Transmet à la compta : coordonnées figées, PDF stocké, plus de modification."""
    acteur.exiger("devis_valider")
    devis = obtenir(session, devis_id)
    _exiger_statut(devis, "valide")
    if devis.signature_fiche != signature_fiche(devis.fiche):
        raise ErreurMetier("regle_metier", "La fiche a changé depuis la validation : « Actualiser » puis valider à nouveau.")
    restants = manques(devis)
    if restants:
        raise ErreurMetier("regle_metier", "Le devis ne peut pas être transmis : " + " ".join(restants))
    params = lire_parametres(session)
    client = clients.client_dict(devis.client)
    devis.statut = "transmis"
    devis.transmis_le = datetime.now(reglages.fuseau)
    devis.transmis_par = acteur.email
    devis.instantane = {"client": client, "evenement": _evenement(devis),
                        "restaurant": {k: v for k, v in params.items() if k.startswith("restaurant_")}}
    devis.pdf = pdf_devis(devis_dict(session, devis), client, _evenement(devis), params, brouillon=False)
    journaliser(session, acteur, "devis.transmettre", "devis", devis.id,
                f"{devis.numero} v{devis.version} transmis à la compta — {format_euros(devis.total_centimes)}")
    session.commit()
    return devis


def marquer_envoye(session: Session, acteur: Acteur, devis_id: Any) -> Devis:
    acteur.exiger("compta")
    devis = obtenir(session, devis_id)
    _exiger_statut(devis, "transmis")
    devis.statut = "envoye"
    devis.envoye_le = datetime.now(reglages.fuseau)
    journaliser(session, acteur, "devis.envoye", "devis", devis.id, f"{devis.numero} v{devis.version} envoyé au client")
    session.commit()
    return devis


def repondre(session: Session, acteur: Acteur, devis_id: Any, accepte: bool) -> Devis:
    """Le client a répondu : à indiquer par la compta ou par l'équipe."""
    if not (acteur.peut("compta") or acteur.peut("devis_valider")):
        acteur.exiger("devis_valider")
    devis = obtenir(session, devis_id)
    _exiger_statut(devis, "transmis", "envoye")
    devis.statut = "accepte" if accepte else "refuse"
    devis.reponse_le = datetime.now(reglages.fuseau)
    journaliser(session, acteur, "devis.reponse", "devis", devis.id,
                f"{devis.numero} v{devis.version} {'accepté' if accepte else 'refusé'}")
    session.commit()
    return devis


def nouvelle_version(session: Session, acteur: Acteur, devis_id: Any) -> tuple[Devis, list[str]]:
    acteur.exiger("devis")
    ancien = obtenir(session, devis_id)
    _exiger_statut(ancien, "transmis", "envoye", "accepte", "refuse")
    if ancien.fiche.statut == "annulee":
        raise ErreurMetier("regle_metier", "La fiche est annulée : pas de nouvelle version.")
    params = lire_parametres(session)
    nouveau = Devis(
        numero=ancien.numero, version=ancien.version + 1, fiche_id=ancien.fiche_id, client_id=ancien.client_id,
        statut="brouillon", couverts=ancien.fiche.couverts, remarques_client=ancien.remarques_client,
        remarques_compta=ancien.remarques_compta,
        date_validite=fiches.aujourd_hui() + timedelta(days=int(params["validite_devis_jours"])),
    )
    nouveau.fiche = ancien.fiche
    session.add(nouveau)
    alertes = _remplir(session, nouveau)
    session.flush()
    ancien.statut = "remplace"
    ancien.version_suivante_id = nouveau.id
    journaliser(session, acteur, "devis.nouvelle_version", "devis", nouveau.id,
                f"{nouveau.numero} v{nouveau.version} (remplace v{ancien.version})")
    session.commit()
    return obtenir(session, nouveau.id), alertes
