"""Bons pour facturation : ce qui a réellement été servi, transmis à la compta qui facture.

Cycle : brouillon → validé → transmis → facturé (par la compta).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import reglages
from ..domain.argent import format_euros
from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import cle, nettoyer_notes, texte_court
from ..domain.regles import LIBELLES_UNITES, verifier_couverts, verifier_quantite
from ..models import BonFacturation, BonLigne, Produit
from ..pdf.documents import pdf_bon
from . import clients, devis as devis_service, fiches
from .contexte import Acteur, journaliser, lire_parametres, prochain_numero, verifier_version

LIBELLES_STATUTS = {"brouillon": "Brouillon", "valide": "Validé", "transmis": "Transmis à la compta",
                    "facture": "Facturé"}
CATEGORIES_EXTRAS = ("supplement", "coupe", "formule_boissons", "entree", "plat", "dessert", "privatisation")


def obtenir(session: Session, bon_id: Any) -> BonFacturation:
    try:
        bid = uuid.UUID(str(bon_id))
    except ValueError:
        raise introuvable("Bon pour facturation")
    bon = session.scalars(select(BonFacturation).where(BonFacturation.id == bid)
                          .options(selectinload(BonFacturation.lignes))).first()
    if bon is None:
        raise introuvable("Bon pour facturation")
    return bon


def bon_dict(session: Session, b: BonFacturation) -> dict[str, Any]:
    total_devis = b.devis.total_centimes
    return {
        "id": str(b.id), "numero": b.numero, "version": b.version, "statut": b.statut,
        "statut_libelle": LIBELLES_STATUTS[b.statut], "devis_id": str(b.devis_id),
        "devis_reference": f"{b.devis.numero} v{b.devis.version}", "fiche_id": str(b.fiche_id),
        "client_id": str(b.client_id), "client_nom": b.client.nom,
        "date_evenement": b.fiche.date.isoformat(), "heure_evenement": b.fiche.heure.strftime("%H:%M"),
        "couverts_devis": b.devis.couverts, "couverts_reels": b.couverts_reels,
        "total_centimes": b.total_centimes, "total": format_euros(b.total_centimes),
        "total_devis_centimes": total_devis, "total_devis": format_euros(total_devis),
        "ecart_centimes": b.total_centimes - total_devis, "ecart": format_euros(b.total_centimes - total_devis),
        "remarques_compta": b.remarques_compta,
        "lignes": [
            {"id": str(l.id), "categorie": l.categorie, "libelle": l.libelle, "quantite_devis": l.quantite_devis,
             "quantite": l.quantite, "unite": l.unite, "unite_libelle": LIBELLES_UNITES.get(l.unite, l.unite),
             "extra": l.quantite_devis == 0,
             "prix_unitaire_centimes": l.prix_unitaire_centimes, "prix_unitaire": format_euros(l.prix_unitaire_centimes),
             "total_centimes": l.total_centimes, "total": format_euros(l.total_centimes)}
            for l in b.lignes
        ],
        "manques": [f"Prix manquant : {l.libelle}." for l in b.lignes if l.prix_unitaire_centimes is None],
        "transmis_le": b.transmis_le.isoformat() if b.transmis_le else None, "transmis_par": b.transmis_par,
        "facture_le": b.facture_le.isoformat() if b.facture_le else None,
        "numero_facture_compta": b.numero_facture_compta, "mention": "Prix TVA comprise",
    }


def lister(session: Session, statut: Optional[str] = None, client_id: Optional[str] = None) -> list[BonFacturation]:
    stmt = select(BonFacturation)
    if statut:
        stmt = stmt.where(BonFacturation.statut.in_(statut.split(",")))
    if client_id:
        stmt = stmt.where(BonFacturation.client_id == uuid.UUID(str(client_id)))
    return list(session.scalars(stmt.order_by(BonFacturation.cree_le.desc())))


def _recalculer(bon: BonFacturation) -> None:
    for l in bon.lignes:
        l.total_centimes = None if l.prix_unitaire_centimes is None else l.prix_unitaire_centimes * l.quantite
    bon.total_centimes = sum(l.total_centimes or 0 for l in bon.lignes)


def _modifiable(bon: BonFacturation) -> None:
    if bon.statut != "brouillon":
        raise ErreurMetier("regle_metier", f"Le bon est « {LIBELLES_STATUTS[bon.statut]} » : il ne se modifie plus.")


def _produit_extra(session: Session, extra: dict[str, Any]) -> Produit:
    if extra.get("produit_id"):
        try:
            produit = session.get(Produit, uuid.UUID(str(extra["produit_id"])))
        except ValueError:
            produit = None
        if produit is not None:
            return produit
    nom = texte_court(extra.get("nom") or extra.get("libelle"), "nom", 200, obligatoire=True)
    candidats = session.scalars(select(Produit).where(Produit.categorie.in_(CATEGORIES_EXTRAS), Produit.actif.is_(True)))
    mots = cle(nom).split()
    trouves = [p for p in candidats if all(m in cle(p.nom) for m in mots)]
    exact = [p for p in trouves if cle(p.nom) == cle(nom)]
    if exact:
        return exact[0]
    if len(trouves) == 1:
        return trouves[0]
    raise ErreurMetier("valeur_non_permise",
                       f"Produit « {nom} » introuvable ou ambigu dans le menu Prix.", champ="nom",
                       valeurs_permises=[p.nom for p in trouves][:20] or None)


def _ajouter_extra(session: Session, bon: BonFacturation, extra: dict[str, Any]) -> BonLigne:
    produit = _produit_extra(session, extra)
    quantite = verifier_quantite(extra.get("quantite"))
    for l in bon.lignes:
        if l.produit_id == produit.id and l.quantite_devis == 0:
            l.quantite = quantite
            return l
    ligne = BonLigne(ordre=len(bon.lignes), categorie=produit.categorie, produit_id=produit.id, libelle=produit.nom,
                     quantite_devis=0, quantite=quantite, unite=produit.unite,
                     prix_unitaire_centimes=produit.prix_centimes)
    bon.lignes.append(ligne)
    return ligne


def _appliquer_couverts(bon: BonFacturation, couverts: int) -> None:
    """Les lignes « par personne » prévues pour tous les couverts suivent les couverts réels."""
    prevus = bon.devis.couverts
    for l in bon.lignes:
        if l.unite == "par_personne" and l.quantite_devis == prevus:
            l.quantite = couverts
    bon.couverts_reels = couverts


def preparer(session: Session, acteur: Acteur, devis_id: Any, couverts_reels: Any = None,
             extras: Optional[list[dict[str, Any]]] = None, remarques_compta: Optional[str] = None) -> tuple[BonFacturation, list[str]]:
    acteur.exiger("devis")
    devis = devis_service.obtenir(session, devis_id)
    if devis.statut != "accepte":
        raise ErreurMetier("regle_metier",
                           f"Le devis doit être accepté par le client (il est « {devis_service.LIBELLES_STATUTS[devis.statut]} »).")
    existant = session.scalars(select(BonFacturation).where(BonFacturation.devis_id == devis.id)).first()
    if existant is not None:
        _modifiable(existant)
        bon = existant
    else:
        bon = BonFacturation(numero=prochain_numero(session, "B", fiches.aujourd_hui().year), devis_id=devis.id,
                             fiche_id=devis.fiche_id, client_id=devis.client_id, statut="brouillon",
                             couverts_reels=devis.couverts)
        bon.devis = devis
        session.add(bon)
        for l in devis.lignes:
            bon.lignes.append(BonLigne(ordre=l.ordre, categorie=l.categorie, produit_id=l.produit_id, libelle=l.libelle,
                                       quantite_devis=l.quantite, quantite=l.quantite, unite=l.unite,
                                       prix_unitaire_centimes=l.prix_unitaire_centimes))
    if couverts_reels is not None:
        _appliquer_couverts(bon, verifier_couverts(couverts_reels))
    for extra in extras or []:
        _ajouter_extra(session, bon, extra)
    if remarques_compta is not None:
        bon.remarques_compta = nettoyer_notes(remarques_compta, 2000)
    _recalculer(bon)
    session.flush()
    alertes = []
    if devis.fiche.date > fiches.aujourd_hui():
        alertes.append("L'événement n'a pas encore eu lieu : le bon reprend les quantités prévues.")
    journaliser(session, acteur, "bon.preparer", "bon", bon.id,
                f"{bon.numero} — {devis.client.nom} — {format_euros(bon.total_centimes)}")
    session.commit()
    return obtenir(session, bon.id), alertes


def modifier(session: Session, acteur: Acteur, bon_id: Any, donnees: dict[str, Any],
             version: Optional[int] = None) -> BonFacturation:
    """donnees : couverts_reels, remarques_compta, lignes [{id, quantite}], ajouter [{produit_id|nom, quantite}],
    retirer [id] (seulement les extras)."""
    acteur.exiger("devis")
    bon = obtenir(session, bon_id)
    verifier_version(bon, version, "Le bon")
    _modifiable(bon)
    if "couverts_reels" in donnees:
        _appliquer_couverts(bon, verifier_couverts(donnees["couverts_reels"]))
    par_id = {str(l.id): l for l in bon.lignes}
    for changement in donnees.get("lignes") or []:
        ligne = par_id.get(str(changement.get("id")))
        if ligne is None:
            raise introuvable("Ligne")
        q = int(changement.get("quantite", ligne.quantite))
        if q < 0 or q > 5000:
            raise ErreurMetier("regle_metier", "Quantité : entre 0 et 5000.", champ="quantite")
        ligne.quantite = q
    for ligne_id in donnees.get("retirer") or []:
        ligne = par_id.get(str(ligne_id))
        if ligne is None:
            raise introuvable("Ligne")
        if ligne.quantite_devis:
            raise ErreurMetier("regle_metier", "Une ligne du devis ne se retire pas : mettre sa quantité à 0.")
        bon.lignes.remove(ligne)
    for extra in donnees.get("ajouter") or []:
        _ajouter_extra(session, bon, extra)
    if "remarques_compta" in donnees:
        bon.remarques_compta = nettoyer_notes(donnees["remarques_compta"], 2000)
    _recalculer(bon)
    bon.version += 1
    journaliser(session, acteur, "bon.modifier", "bon", bon.id, f"{bon.numero} — {format_euros(bon.total_centimes)}")
    session.commit()
    return obtenir(session, bon.id)


def _evenement(bon: BonFacturation) -> dict[str, Any]:
    f = bon.fiche
    return {"date": f.date.isoformat(), "heure": f.heure.strftime("%H:%M"), "espace": f.espace}


def generer_pdf(session: Session, bon: BonFacturation) -> bytes:
    if bon.pdf:
        return bon.pdf
    return pdf_bon(bon_dict(session, bon), clients.client_dict(bon.client), _evenement(bon), lire_parametres(session),
                   brouillon=True)


def valider(session: Session, acteur: Acteur, bon_id: Any) -> BonFacturation:
    acteur.exiger("devis_valider")
    bon = obtenir(session, bon_id)
    if bon.statut != "brouillon":
        raise ErreurMetier("regle_metier", "Seul un bon en brouillon se valide.")
    manquants = [l.libelle for l in bon.lignes if l.prix_unitaire_centimes is None and l.quantite > 0]
    if manquants:
        raise ErreurMetier("prix_manquant", "Prix manquant : " + ", ".join(manquants) + ".")
    bon.statut = "valide"
    journaliser(session, acteur, "bon.valider", "bon", bon.id, bon.numero)
    session.commit()
    return bon


def devalider(session: Session, acteur: Acteur, bon_id: Any) -> BonFacturation:
    acteur.exiger("devis_valider")
    bon = obtenir(session, bon_id)
    if bon.statut != "valide":
        raise ErreurMetier("regle_metier", "Seul un bon validé repasse en brouillon.")
    bon.statut = "brouillon"
    journaliser(session, acteur, "bon.devalider", "bon", bon.id, bon.numero)
    session.commit()
    return bon


def transmettre(session: Session, acteur: Acteur, bon_id: Any) -> BonFacturation:
    acteur.exiger("devis_valider")
    bon = obtenir(session, bon_id)
    if bon.statut != "valide":
        raise ErreurMetier("regle_metier", "Valider le bon avant de le transmettre.")
    params = lire_parametres(session)
    client = clients.client_dict(bon.client)
    bon.statut = "transmis"
    bon.transmis_le = datetime.now(reglages.fuseau)
    bon.transmis_par = acteur.email
    bon.instantane = {"client": client, "evenement": _evenement(bon)}
    bon.pdf = pdf_bon(bon_dict(session, bon), client, _evenement(bon), params, brouillon=False)
    journaliser(session, acteur, "bon.transmettre", "bon", bon.id,
                f"{bon.numero} transmis à la compta — {format_euros(bon.total_centimes)}")
    session.commit()
    return bon


def marquer_facture(session: Session, acteur: Acteur, bon_id: Any, numero_facture: Optional[str]) -> BonFacturation:
    acteur.exiger("compta")
    bon = obtenir(session, bon_id)
    if bon.statut != "transmis":
        raise ErreurMetier("regle_metier", "Seul un bon transmis se marque « facturé ».")
    bon.statut = "facture"
    bon.facture_le = datetime.now(reglages.fuseau)
    bon.numero_facture_compta = texte_court(numero_facture, "numero_facture", 100)
    journaliser(session, acteur, "bon.facture", "bon", bon.id,
                f"{bon.numero} facturé" + (f" ({bon.numero_facture_compta})" if bon.numero_facture_compta else ""))
    session.commit()
    return bon
