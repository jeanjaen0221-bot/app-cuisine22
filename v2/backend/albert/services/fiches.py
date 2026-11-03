"""Fiches d'événement (cuisine et salle)."""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import reglages
from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import (
    LIBELLES_TYPES,
    TYPES_PLATS,
    choisir,
    cle,
    lire_allergenes,
    lire_date,
    lire_heure,
    lire_type_ligne,
    nettoyer_notes,
    texte_court,
)
from ..domain.regles import (
    ESPACES,
    LIBELLES_STATUTS_FICHE,
    STATUTS_FIGES,
    appliquer_regles_fiche,
    peut_confirmer,
    signature_fiche,
    verifier_couverts,
    verifier_quantite,
    verifier_transition,
)
from ..models import BonFacturation, Devis, Fiche, FicheLigne, Produit
from . import catalogue, clients
from .contexte import Acteur, journaliser, verifier_version


def aujourd_hui() -> date:
    return datetime.now(reglages.fuseau).date()


# --------------------------------------------------------------- lecture

def _charger(session: Session, fiche_id: Any) -> Fiche:
    try:
        fid = uuid.UUID(str(fiche_id))
    except ValueError:
        raise introuvable("Fiche")
    fiche = session.scalars(
        select(Fiche).where(Fiche.id == fid).options(selectinload(Fiche.lignes).selectinload(FicheLigne.produit))
    ).first()
    if fiche is None:
        raise introuvable("Fiche")
    return fiche


obtenir = _charger


def devis_courant(session: Session, fiche_id: uuid.UUID) -> Optional[Devis]:
    return session.scalars(
        select(Devis).where(Devis.fiche_id == fiche_id, Devis.statut != "remplace").order_by(Devis.version.desc())
    ).first()


def fiche_dict(session: Session, f: Fiche, complet: bool = True) -> dict[str, Any]:
    alertes: list[str] = []
    if f.statut != "annulee":
        try:
            _, alertes = appliquer_regles_fiche(f.couverts, f.formule_repas, list(f.lignes))
        except ErreurMetier as erreur:  # données d'avant une règle : on le signale sans bloquer la lecture
            alertes = [erreur.message]
    sortie: dict[str, Any] = {
        "id": str(f.id), "version": f.version, "statut": f.statut, "statut_libelle": LIBELLES_STATUTS_FICHE[f.statut],
        "date": f.date.isoformat(), "heure": f.heure.strftime("%H:%M"), "couverts": f.couverts, "espace": f.espace,
        "client": {"id": str(f.client.id), "nom": f.client.nom, "type": f.client.type},
        "formule_repas": f.formule_repas.nom if f.formule_repas else None,
        "formule_repas_id": str(f.formule_repas_id) if f.formule_repas_id else None,
        "formule_boissons": f.formule_boissons.nom if f.formule_boissons else None,
        "formule_boissons_id": str(f.formule_boissons_id) if f.formule_boissons_id else None,
        "couleur_boissons": f.formule_boissons.couleur if f.formule_boissons else "gris",
        "privatisation": f.privatisation.nom if f.privatisation else None,
        "privatisation_id": str(f.privatisation_id) if f.privatisation_id else None,
        "allergenes": f.allergenes or [],
        "lignes": [
            {"id": str(l.id), "type": l.type, "type_libelle": LIBELLES_TYPES[l.type], "libelle": l.libelle,
             "quantite": l.quantite, "commentaire": l.commentaire,
             "produit_id": str(l.produit_id) if l.produit_id else None, "hors_catalogue": l.produit_id is None}
            for l in f.lignes
        ],
        "figee": f.statut in STATUTS_FIGES,
        "alertes": alertes,
    }
    if complet:
        sortie.update({
            "notes_salle": f.notes_salle, "notes_cuisine": f.notes_cuisine,
            "contact_sur_place": f.contact_sur_place, "telephone_sur_place": f.telephone_sur_place,
            "motif_annulation": f.motif_annulation,
            "dernier_pdf_le": f.dernier_pdf_le.isoformat() if f.dernier_pdf_le else None,
        })
        devis = devis_courant(session, f.id)
        if devis is not None:
            a_jour = devis.signature_fiche == signature_fiche(f)
            sortie["devis"] = {"id": str(devis.id), "numero": devis.numero, "version": devis.version,
                               "statut": devis.statut, "a_mettre_a_jour": not a_jour}
            if not a_jour and devis.statut != "brouillon":
                sortie["alertes"].append("Devis à mettre à jour : la fiche a changé depuis le devis.")
        else:
            sortie["devis"] = None
        bon = session.scalars(select(BonFacturation).where(BonFacturation.fiche_id == f.id)
                              .order_by(BonFacturation.cree_le.desc())).first()
        sortie["bon"] = {"id": str(bon.id), "numero": bon.numero, "statut": bon.statut} if bon else None
    return sortie


def lister(session: Session, q: Optional[str] = None, client_id: Optional[str] = None,
           jour: Any = None, du: Any = None, au: Any = None, statut: Optional[str] = None,
           espace: Optional[str] = None, periode: str = "a_venir", limite: int = 50, decalage: int = 0) -> list[Fiche]:
    stmt = select(Fiche).options(selectinload(Fiche.lignes))
    if jour:
        stmt = stmt.where(Fiche.date == lire_date(jour))
    else:
        if du:
            stmt = stmt.where(Fiche.date >= lire_date(du, "du"))
        if au:
            stmt = stmt.where(Fiche.date <= lire_date(au, "au"))
        if not du and not au:
            if periode == "a_venir":
                stmt = stmt.where(Fiche.date >= aujourd_hui())
            elif periode == "passees":
                stmt = stmt.where(Fiche.date < aujourd_hui())
    if client_id:
        stmt = stmt.where(Fiche.client_id == clients.obtenir(session, client_id).id)
    if statut:
        stmt = stmt.where(Fiche.statut == statut)
    if espace:
        stmt = stmt.where(Fiche.espace == espace)
    descendant = periode == "passees" and not (jour or du or au)
    ordre = (Fiche.date.desc(), Fiche.heure.desc()) if descendant else (Fiche.date, Fiche.heure)
    fiches = list(session.scalars(stmt.order_by(*ordre)))
    if q:
        mots = cle(q).split()
        fiches = [f for f in fiches if all(m in cle(" ".join(filter(None, [
            f.client.nom, f.client.contact_nom, f.client.contact_prenom, f.contact_sur_place]))) for m in mots)]
    return fiches[decalage: decalage + limite]


# --------------------------------------------------------------- écriture

class _Ligne:
    def __init__(self, type: str, libelle: str, quantite: int, commentaire: Optional[str], produit: Optional[Produit]):
        self.type, self.libelle, self.quantite, self.commentaire, self.produit = type, libelle, quantite, commentaire, produit


def _produit_pour_ligne(session: Session, type_ligne: str, nom: str, produit_id: Any) -> Optional[Produit]:
    categories = (type_ligne,) if type_ligne in TYPES_PLATS else ("supplement", "coupe")
    if produit_id:
        try:
            p = session.get(Produit, uuid.UUID(str(produit_id)))
        except ValueError:
            p = None
        if p is None or p.categorie not in categories:
            raise ErreurMetier("valeur_non_permise", f"Produit introuvable pour « {nom} ».", champ="produit_id")
        return p
    for p in session.scalars(select(Produit).where(Produit.categorie.in_(categories), Produit.actif.is_(True))):
        if cle(p.nom) == cle(nom):
            return p
    return None


def _lire_lignes(session: Session, brutes: list[dict[str, Any]]) -> list[_Ligne]:
    lignes: list[_Ligne] = []
    for brute in brutes:
        t = lire_type_ligne(brute.get("type"))
        nom = texte_court(brute.get("libelle") or brute.get("nom"), "libellé", 200, obligatoire=True)
        produit = _produit_pour_ligne(session, t, nom or "", brute.get("produit_id"))
        lignes.append(_Ligne(t, produit.nom if produit else nom, verifier_quantite(brute.get("quantite")),
                             texte_court(brute.get("commentaire"), "commentaire", 500), produit))
    return lignes


def _choisir_formules(session: Session, donnees: dict[str, Any], fiche: Optional[Fiche]) -> dict[str, Any]:
    v: dict[str, Any] = {}
    if "formule_repas" in donnees or "formule_repas_id" in donnees:
        valeur = donnees.get("formule_repas_id") or donnees.get("formule_repas")
        options = [(f.nom, f) for f in catalogue.lister_formules_repas(session, actives=True)]
        options += [(str(f.id), f) for _, f in options]
        v["formule_repas"] = choisir(valeur, options, "formule_repas", vide_permis=True)
    if "formule_boissons" in donnees or "formule_boissons_id" in donnees:
        valeur = donnees.get("formule_boissons_id") or donnees.get("formule_boissons")
        options = [(f.nom, f) for f in catalogue.lister_formules_boissons(session, actives=True)]
        options += [(str(f.id), f) for _, f in options]
        v["formule_boissons"] = choisir(valeur, options, "formule_boissons", vide_permis=True)
    elif fiche is None:
        defaut = next((f for f in catalogue.lister_formules_boissons(session, actives=True) if f.par_defaut), None)
        v["formule_boissons"] = defaut
    if "privatisation" in donnees or "privatisation_id" in donnees:
        valeur = donnees.get("privatisation_id") or donnees.get("privatisation")
        if cle(valeur) in ("aucune", "non", "sans"):
            valeur = None
        options = [(p.nom, p) for p in catalogue.lister_produits(session, "privatisation", actifs_seulement=True)]
        options += [(str(p.id), p) for _, p in options]
        v["privatisation"] = choisir(valeur, options, "privatisation", vide_permis=True)
    return v


def _appliquer(session: Session, fiche: Fiche, donnees: dict[str, Any], nouvelle: bool) -> list[str]:
    if "client_id" in donnees or nouvelle:
        if not donnees.get("client_id"):
            raise ErreurMetier("champ_obligatoire", "Le client est obligatoire (le chercher ou le créer d'abord).",
                               champ="client_id")
        fiche.client_id = clients.obtenir(session, donnees["client_id"]).id
    if "date" in donnees or nouvelle:
        fiche.date = lire_date(donnees.get("date"))
    if "heure" in donnees or nouvelle:
        fiche.heure = lire_heure(donnees.get("heure"))
    if "couverts" in donnees or nouvelle:
        fiche.couverts = verifier_couverts(donnees.get("couverts"))
    if "espace" in donnees:
        espace = choisir(donnees.get("espace") or "salle", [(e, e) for e in ESPACES], "espace")
        fiche.espace = espace
    elif nouvelle:
        fiche.espace = "salle"
    if "allergenes" in donnees:
        fiche.allergenes = lire_allergenes(donnees["allergenes"])
    for champ in ("notes_salle", "notes_cuisine"):
        if champ in donnees:
            setattr(fiche, champ, nettoyer_notes(donnees[champ]))
    if "contact_sur_place" in donnees:
        fiche.contact_sur_place = texte_court(donnees["contact_sur_place"], "contact_sur_place", 200)
    if "telephone_sur_place" in donnees:
        fiche.telephone_sur_place = texte_court(donnees["telephone_sur_place"], "telephone_sur_place", 50)

    formules = _choisir_formules(session, donnees, None if nouvelle else fiche)
    for cle_formule in ("formule_boissons", "privatisation"):
        if cle_formule in formules:
            setattr(fiche, cle_formule, formules[cle_formule])
    formule_repas = formules["formule_repas"] if "formule_repas" in formules else fiche.formule_repas

    if "lignes" in donnees:
        nouvelles = _lire_lignes(session, donnees.get("lignes") or [])
        if not any(l.type == "supplement" for l in nouvelles) and donnees.get("garder_supplements", False):
            nouvelles += [_Ligne(l.type, l.libelle, l.quantite, l.commentaire, l.produit)
                          for l in fiche.lignes if l.type == "supplement"]
    else:
        nouvelles = [_Ligne(l.type, l.libelle, l.quantite, l.commentaire, l.produit) for l in fiche.lignes]

    formule_repas, alertes = appliquer_regles_fiche(fiche.couverts, formule_repas, nouvelles)
    fiche.formule_repas = formule_repas
    if "lignes" in donnees:
        fiche.lignes.clear()
        session.flush()
        for i, l in enumerate(nouvelles):
            fiche.lignes.append(FicheLigne(type=l.type, libelle=l.libelle, quantite=l.quantite,
                                           commentaire=l.commentaire, produit=l.produit, ordre=i))
    return alertes


def _verifier_modifiable(acteur: Acteur, fiche: Fiche) -> None:
    if fiche.statut in STATUTS_FIGES:
        message = f"La fiche est « {LIBELLES_STATUTS_FICHE[fiche.statut]} » : elle ne se modifie plus."
        message += " Elle doit être rouverte dans l'outil." if acteur.est_chatgpt else " La rouvrir d'abord."
        raise ErreurMetier("interdit", message)


def creer(session: Session, acteur: Acteur, donnees: dict[str, Any]) -> tuple[Fiche, list[str]]:
    acteur.exiger("fiches")
    cle_idem = texte_court(donnees.get("cle_idempotence"), "cle_idempotence", 100)
    if cle_idem:
        existante = session.scalars(select(Fiche).where(Fiche.cle_idempotence == cle_idem)).first()
        if existante is not None:
            return existante, ["Fiche déjà créée avec cette clé d'idempotence : aucune nouvelle fiche."]
    fiche = Fiche(statut="brouillon", version=1, cle_idempotence=cle_idem)
    # La fiche n'entre dans la session qu'une fois complète : sinon une requête de
    # recherche (client, formule…) déclencherait l'écriture d'une fiche à moitié remplie.
    with session.no_autoflush:
        alertes = _appliquer(session, fiche, donnees, nouvelle=True)
    session.add(fiche)
    session.flush()
    session.refresh(fiche)
    journaliser(session, acteur, "fiche.creer", "fiche", fiche.id,
                f"{fiche.client.nom} — {fiche.date:%d/%m/%Y} {fiche.heure:%H:%M}, {fiche.couverts} couverts",
                None, fiche_dict(session, fiche, complet=False))
    session.commit()
    return fiche, alertes


def modifier(session: Session, acteur: Acteur, fiche_id: Any, donnees: dict[str, Any],
             version: Optional[int] = None) -> tuple[Fiche, list[str]]:
    acteur.exiger("fiches")
    fiche = _charger(session, fiche_id)
    verifier_version(fiche, version, "La fiche")
    _verifier_modifiable(acteur, fiche)
    if "statut" in donnees:
        raise ErreurMetier("regle_metier", "Le statut se change avec l'action dédiée.", champ="statut")
    avant = fiche_dict(session, fiche, complet=False)
    alertes = _appliquer(session, fiche, donnees, nouvelle=False)
    fiche.version += 1
    fiche.dernier_pdf_le = None  # à réimprimer
    session.flush()
    session.refresh(fiche)
    journaliser(session, acteur, "fiche.modifier", "fiche", fiche.id, f"{fiche.client.nom} — {fiche.date:%d/%m/%Y}",
                avant, fiche_dict(session, fiche, complet=False))
    session.commit()
    return fiche, alertes


def ajouter_ligne(session: Session, acteur: Acteur, fiche_id: Any, ligne: dict[str, Any],
                  version: Optional[int] = None) -> tuple[Fiche, list[str]]:
    """Ajoute une ligne ; si même type et même nom, remplace la quantité (et le commentaire)."""
    fiche = _charger(session, fiche_id)
    nouvelle = _lire_lignes(session, [ligne])[0]
    lignes = []
    remplacee = False
    for l in fiche.lignes:
        d = {"type": l.type, "libelle": l.libelle, "quantite": l.quantite, "commentaire": l.commentaire,
             "produit_id": l.produit_id}
        if l.type == nouvelle.type and cle(l.libelle) == cle(nouvelle.libelle):
            d["quantite"] = nouvelle.quantite
            if nouvelle.commentaire is not None:
                d["commentaire"] = nouvelle.commentaire
            remplacee = True
        lignes.append(d)
    if not remplacee:
        lignes.append({"type": nouvelle.type, "libelle": nouvelle.libelle, "quantite": nouvelle.quantite,
                       "commentaire": nouvelle.commentaire, "produit_id": nouvelle.produit.id if nouvelle.produit else None})
    return modifier(session, acteur, fiche_id, {"lignes": lignes}, version)


def retirer_ligne(session: Session, acteur: Acteur, fiche_id: Any, type_ligne: str, nom: str,
                  version: Optional[int] = None) -> tuple[Fiche, list[str]]:
    fiche = _charger(session, fiche_id)
    t = lire_type_ligne(type_ligne)
    restantes = [l for l in fiche.lignes if not (l.type == t and cle(l.libelle) == cle(nom))]
    if len(restantes) == len(fiche.lignes):
        raise ErreurMetier("introuvable", f"Aucune ligne {LIBELLES_TYPES[t]} « {nom} » sur cette fiche.")
    lignes = [{"type": l.type, "libelle": l.libelle, "quantite": l.quantite, "commentaire": l.commentaire,
               "produit_id": l.produit_id} for l in restantes]
    return modifier(session, acteur, fiche_id, {"lignes": lignes}, version)


def changer_statut(session: Session, acteur: Acteur, fiche_id: Any, cible: str,
                   version: Optional[int] = None, motif: Optional[str] = None) -> Fiche:
    acteur.exiger("fiches")
    if acteur.est_chatgpt:
        raise ErreurMetier("interdit", "Le statut d'une fiche se change dans l'outil, par l'équipe "
                                       "(pour annuler, utiliser l'annulation en deux temps).")
    fiche = _charger(session, fiche_id)
    verifier_version(fiche, version, "La fiche")
    verifier_transition(fiche.statut, cible)
    if cible == "confirmee" and fiche.statut == "brouillon" and not peut_confirmer(fiche.formule_repas, list(fiche.lignes)):
        raise ErreurMetier("regle_metier", "Pour confirmer, indiquer une formule repas ou au moins un plat.",
                           champ="formule_repas")
    if cible == "annulee":
        fiche.motif_annulation = texte_court(motif, "motif", 500, obligatoire=True)
    avant = fiche.statut
    fiche.statut = cible
    fiche.version += 1
    journaliser(session, acteur, "fiche.statut", "fiche", fiche.id,
                f"{fiche.client.nom} : {LIBELLES_STATUTS_FICHE[avant]} → {LIBELLES_STATUTS_FICHE[cible]}",
                {"statut": avant}, {"statut": cible, "motif": fiche.motif_annulation})
    session.commit()
    return fiche


def _jeton_annulation(fiche: Fiche) -> str:
    message = f"annuler:{fiche.id}:{fiche.version}".encode()
    return hmac.new(reglages.secret.encode(), message, hashlib.sha256).hexdigest()[:24]


def annuler(session: Session, acteur: Acteur, fiche_id: Any, motif: Optional[str],
            jeton_confirmation: Optional[str] = None) -> Fiche:
    """Annulation en deux temps : sans jeton valide, renvoie un aperçu et le jeton à renvoyer."""
    acteur.exiger("fiches")
    fiche = _charger(session, fiche_id)
    verifier_transition(fiche.statut, "annulee")
    motif = texte_court(motif, "motif", 500, obligatoire=True)
    attendu = _jeton_annulation(fiche)
    if not jeton_confirmation or not hmac.compare_digest(jeton_confirmation, attendu):
        raise ErreurMetier(
            "confirmation_requise",
            f"Annuler la fiche de {fiche.client.nom} du {fiche.date:%d/%m/%Y} à {fiche.heure:%H:%M} "
            f"({fiche.couverts} couverts) ? Demander un « oui » explicite, puis renvoyer ce jeton.",
            details={"jeton_confirmation": attendu, "apercu": fiche_dict(session, fiche, complet=False)},
        )
    fiche.motif_annulation = motif
    avant = fiche.statut
    fiche.statut = "annulee"
    fiche.version += 1
    journaliser(session, acteur, "fiche.annuler", "fiche", fiche.id, f"{fiche.client.nom} : annulée ({motif})",
                {"statut": avant}, {"statut": "annulee", "motif": motif})
    session.commit()
    return fiche


def dupliquer(session: Session, acteur: Acteur, fiche_id: Any, nouvelle_date: Any = None) -> Fiche:
    acteur.exiger("fiches")
    source = _charger(session, fiche_id)
    copie = Fiche(
        client_id=source.client_id, date=lire_date(nouvelle_date) if nouvelle_date else source.date,
        heure=source.heure, couverts=source.couverts, espace=source.espace, privatisation_id=source.privatisation_id,
        formule_repas_id=source.formule_repas_id, formule_boissons_id=source.formule_boissons_id,
        allergenes=list(source.allergenes or []), notes_salle=source.notes_salle, notes_cuisine=source.notes_cuisine,
        contact_sur_place=source.contact_sur_place, telephone_sur_place=source.telephone_sur_place,
        statut="brouillon", version=1,
    )
    for i, l in enumerate(source.lignes):
        copie.lignes.append(FicheLigne(type=l.type, libelle=l.libelle, quantite=l.quantite,
                                       commentaire=l.commentaire, produit_id=l.produit_id, ordre=i))
    session.add(copie)
    session.flush()
    journaliser(session, acteur, "fiche.dupliquer", "fiche", copie.id, f"Copie de la fiche {source.id}")
    session.commit()
    return _charger(session, copie.id)


def marquer_imprimee(session: Session, fiche: Fiche) -> None:
    fiche.dernier_pdf_le = datetime.now(reglages.fuseau)
    session.commit()


def rappels(session: Session, jours: int = 7) -> list[Fiche]:
    """Fiches des prochains jours sans formule ni plat."""
    debut = aujourd_hui()
    fin = debut + timedelta(days=jours)
    fiches = session.scalars(select(Fiche).where(Fiche.date >= debut, Fiche.date <= fin,
                                                 Fiche.statut.in_(("brouillon", "confirmee"))))
    return [f for f in fiches if not peut_confirmer(f.formule_repas, list(f.lignes))]
