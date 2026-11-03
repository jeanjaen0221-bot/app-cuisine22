"""Boissons, fournisseurs, réassort et bons de commande.

Les prix d'achat restent séparés des prix de vente (menu Prix). Le réassort calcule les
quantités à commander d'après le stock restant ; il prépare un bon de commande en brouillon
par fournisseur (le fournisseur préféré de chaque boisson). L'envoi au fournisseur est
toujours fait par une personne : l'outil marque seulement le bon « envoyé ».
"""
from __future__ import annotations

import csv
import io
import math
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import reglages
from ..domain.argent import format_euros, lire_euros
from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.import_boissons import lire_csv, lire_pdf, lire_texte
from ..domain.normalisation import cle, lire_email, nettoyer_notes, texte_court
from ..models import Boisson, BoissonFournisseur, BonCommande, BonCommandeLigne, Fournisseur
from . import fiches
from .contexte import Acteur, journaliser, prochain_numero, verifier_version

STATUTS = {"brouillon": "Brouillon", "envoye": "Envoyé", "recu": "Reçu", "annule": "Annulé"}
TRANSITIONS = {"brouillon": ("envoye", "annule"), "envoye": ("recu", "brouillon", "annule"), "recu": ("envoye",),
               "annule": ("brouillon",)}


def _entier(valeur: Any, champ: str, minimum: int = 0, maximum: int = 100000) -> int:
    try:
        n = int(valeur)
    except (TypeError, ValueError):
        raise ErreurMetier("valeur_non_permise", f"{champ} : nombre entier attendu.", champ=champ)
    if not minimum <= n <= maximum:
        raise ErreurMetier("regle_metier", f"{champ} : entre {minimum} et {maximum}.", champ=champ)
    return n


# --------------------------------------------------------------- fournisseurs

def fournisseur_dict(f: Fournisseur) -> dict[str, Any]:
    return {"id": str(f.id), "nom": f.nom, "email": f.email, "telephone": f.telephone, "notes": f.notes, "actif": f.actif}


def lister_fournisseurs(session: Session, actifs: bool = False) -> list[Fournisseur]:
    stmt = select(Fournisseur).order_by(Fournisseur.nom)
    if actifs:
        stmt = stmt.where(Fournisseur.actif.is_(True))
    return list(session.scalars(stmt))


def obtenir_fournisseur(session: Session, fid: Any) -> Fournisseur:
    try:
        f = session.get(Fournisseur, uuid.UUID(str(fid)))
    except ValueError:
        f = None
    if f is None:
        raise introuvable("Fournisseur")
    return f


def enregistrer_fournisseur(session: Session, acteur: Acteur, donnees: dict[str, Any], fid: Any = None) -> Fournisseur:
    acteur.exiger("fiches")
    f = obtenir_fournisseur(session, fid) if fid else Fournisseur()
    if "nom" in donnees or not fid:
        nom = texte_court(donnees.get("nom"), "nom", 200, obligatoire=True)
        for autre in lister_fournisseurs(session):
            if autre.id != f.id and cle(autre.nom) == cle(nom):
                raise ErreurMetier("doublon_probable", f"Le fournisseur « {autre.nom} » existe déjà.", champ="nom")
        f.nom = nom
    if "email" in donnees:
        f.email = lire_email(donnees["email"])
    if "telephone" in donnees:
        f.telephone = texte_court(donnees["telephone"], "telephone", 50)
    if "notes" in donnees:
        f.notes = nettoyer_notes(donnees["notes"], 2000)
    if "actif" in donnees:
        f.actif = bool(donnees["actif"])
    session.add(f)
    session.flush()
    journaliser(session, acteur, "fournisseur." + ("modifier" if fid else "creer"), "fournisseur", f.id, f.nom)
    session.commit()
    return f


# --------------------------------------------------------------- boissons

def _offres(session: Session) -> dict[uuid.UUID, list[BoissonFournisseur]]:
    sortie: dict[uuid.UUID, list[BoissonFournisseur]] = {}
    for o in session.scalars(select(BoissonFournisseur).options(selectinload(BoissonFournisseur.fournisseur))):
        sortie.setdefault(o.boisson_id, []).append(o)
    return sortie


def _offre_preferee(offres: list[BoissonFournisseur]) -> Optional[BoissonFournisseur]:
    actives = [o for o in offres if o.fournisseur.actif]
    return next((o for o in actives if o.prefere), actives[0] if len(actives) == 1 else None)


def boisson_dict(b: Boisson, offres: Optional[list[BoissonFournisseur]] = None) -> dict[str, Any]:
    offres = offres or []
    pref = _offre_preferee(offres)
    return {
        "id": str(b.id), "nom": b.nom, "categorie": b.categorie, "unite": b.unite, "stock_min": b.stock_min,
        "stock_max": b.stock_max, "colisage": b.colisage, "reassort": b.reassort, "actif": b.actif,
        "fournisseurs": [{"fournisseur_id": str(o.fournisseur_id), "fournisseur": o.fournisseur.nom,
                          "reference": o.reference, "prix_achat_centimes": o.prix_achat_centimes,
                          "prix_achat": format_euros(o.prix_achat_centimes) if o.prix_achat_centimes is not None else None,
                          "colisage": o.colisage, "prefere": o.prefere} for o in offres],
        "fournisseur_prefere": pref.fournisseur.nom if pref else None,
    }


def lister_boissons(session: Session, q: Optional[str] = None, actives: bool = False) -> list[dict[str, Any]]:
    stmt = select(Boisson).order_by(Boisson.categorie, Boisson.nom)
    if actives:
        stmt = stmt.where(Boisson.actif.is_(True))
    offres = _offres(session)
    liste = list(session.scalars(stmt))
    if q:
        mots = cle(q).split()
        liste = [b for b in liste if all(m in cle(f"{b.nom} {b.categorie or ''}") for m in mots)]
    return [boisson_dict(b, offres.get(b.id)) for b in liste]


def obtenir_boisson(session: Session, bid: Any) -> Boisson:
    try:
        b = session.get(Boisson, uuid.UUID(str(bid)))
    except ValueError:
        b = None
    if b is None:
        raise introuvable("Boisson")
    return b


def enregistrer_boisson(session: Session, acteur: Acteur, donnees: dict[str, Any], bid: Any = None) -> Boisson:
    acteur.exiger("fiches")
    b = obtenir_boisson(session, bid) if bid else Boisson()
    if "nom" in donnees or not bid:
        nom = texte_court(donnees.get("nom"), "nom", 200, obligatoire=True)
        existante = session.scalars(select(Boisson).where(Boisson.nom == nom)).first()
        if existante is not None and existante.id != b.id:
            raise ErreurMetier("doublon_probable", f"La boisson « {nom} » existe déjà.", champ="nom")
        b.nom = nom
    for champ, maximum in (("categorie", 100), ("unite", 50)):
        if champ in donnees:
            setattr(b, champ, texte_court(donnees[champ], champ, maximum))
    for champ in ("stock_min", "stock_max"):
        if champ in donnees:
            setattr(b, champ, _entier(donnees[champ] or 0, champ))
    if "colisage" in donnees:
        b.colisage = _entier(donnees["colisage"], "colisage", 1, 1000) if donnees["colisage"] else None
    for champ in ("reassort", "actif"):
        if champ in donnees:
            setattr(b, champ, bool(donnees[champ]))
    if (b.stock_max or 0) and (b.stock_min or 0) > (b.stock_max or 0):
        raise ErreurMetier("regle_metier", "Le stock minimum dépasse le stock maximum.", champ="stock_min")
    session.add(b)
    session.flush()
    if "fournisseurs" in donnees:
        _remplacer_offres(session, b, donnees["fournisseurs"] or [])
    session.commit()
    return b


def _remplacer_offres(session: Session, b: Boisson, offres: list[dict[str, Any]]) -> None:
    for ancienne in session.scalars(select(BoissonFournisseur).where(BoissonFournisseur.boisson_id == b.id)):
        session.delete(ancienne)
    session.flush()
    vus: set[uuid.UUID] = set()
    prefere = False
    for o in offres:
        f = obtenir_fournisseur(session, o.get("fournisseur_id"))
        if f.id in vus:
            continue
        vus.add(f.id)
        est_prefere = bool(o.get("prefere")) and not prefere
        prefere = prefere or est_prefere
        session.add(BoissonFournisseur(
            boisson_id=b.id, fournisseur_id=f.id, reference=texte_court(o.get("reference"), "reference", 100),
            prix_achat_centimes=lire_euros(o.get("prix_achat")) if "prix_achat" in o else o.get("prix_achat_centimes"),
            colisage=_entier(o["colisage"], "colisage", 1, 1000) if o.get("colisage") else None, prefere=est_prefere))


def importer_boissons(session: Session, acteur: Acteur, nom_fichier: str, contenu: bytes,
                      categorie: Optional[str] = None, unite: Optional[str] = None) -> dict[str, Any]:
    acteur.exiger("fiches")
    extension = nom_fichier.lower().rsplit(".", 1)[-1] if "." in nom_fichier else ""
    if contenu.startswith(b"%PDF") or extension == "pdf":
        trouvees = lire_pdf(contenu, categorie)
    elif extension == "csv":
        trouvees = lire_csv(contenu.decode("utf-8", errors="ignore"), categorie)
    else:
        trouvees = lire_texte(contenu.decode("utf-8", errors="ignore"), categorie)
    existantes = {cle(n) for n in session.scalars(select(Boisson.nom))}
    ajoutees = []
    for nom, cat in trouvees:
        if cle(nom) in existantes:
            continue
        existantes.add(cle(nom))
        session.add(Boisson(nom=nom[:200], categorie=cat, unite=unite))
        ajoutees.append(nom)
    journaliser(session, acteur, "boisson.importer", "boisson", None, f"{len(ajoutees)} boisson(s) importée(s)")
    session.commit()
    return {"lues": len(trouvees), "ajoutees": len(ajoutees), "noms": ajoutees[:50]}


# --------------------------------------------------------------- réassort

def reassort(session: Session, restant: dict[str, Any], cible: str = "max", arrondi_colis: bool = True) -> list[dict[str, Any]]:
    """Quantité à commander = cible (max ou min) - reste en stock, arrondie au colis supérieur."""
    offres = _offres(session)
    sortie = []
    for b in session.scalars(select(Boisson).where(Boisson.actif.is_(True)).order_by(Boisson.categorie, Boisson.nom)):
        reste = max(0, int(restant.get(str(b.id), 0) or 0))
        objectif = b.stock_max if cible == "max" else b.stock_min
        pref = _offre_preferee(offres.get(b.id, []))
        colis = (pref.colisage if pref and pref.colisage else None) or b.colisage
        manque = max(0, objectif - reste) if b.reassort else 0
        if manque and arrondi_colis and colis and colis > 1:
            manque = math.ceil(manque / colis) * colis
        sortie.append({
            "boisson_id": str(b.id), "nom": b.nom, "categorie": b.categorie, "unite": b.unite, "reste": reste,
            "stock_min": b.stock_min, "stock_max": b.stock_max, "colisage": colis, "reassort": b.reassort,
            "sous_le_minimum": reste < b.stock_min, "a_commander": manque,
            "fournisseur_id": str(pref.fournisseur_id) if pref else None,
            "fournisseur": pref.fournisseur.nom if pref else None,
        })
    return sortie


# --------------------------------------------------------------- bons de commande

def bon_dict(b: BonCommande) -> dict[str, Any]:
    total = sum((l.prix_achat_centimes or 0) * l.quantite for l in b.lignes)
    return {
        "id": str(b.id), "numero": b.numero, "version": b.version, "statut": b.statut, "statut_libelle": STATUTS[b.statut],
        "fournisseur_id": str(b.fournisseur_id) if b.fournisseur_id else None,
        "fournisseur": b.fournisseur.nom if b.fournisseur else None,
        "fournisseur_email": b.fournisseur.email if b.fournisseur else None, "note": b.note,
        "lignes": [{"id": str(l.id), "boisson_id": str(l.boisson_id) if l.boisson_id else None, "libelle": l.libelle,
                    "unite": l.unite, "reference": l.reference, "quantite": l.quantite,
                    "prix_achat_centimes": l.prix_achat_centimes,
                    "prix_achat": format_euros(l.prix_achat_centimes) if l.prix_achat_centimes is not None else None}
                   for l in b.lignes],
        "total_achat_centimes": total, "total_achat": format_euros(total),
        "prix_manquants": any(l.prix_achat_centimes is None for l in b.lignes),
        "cree_le": b.cree_le.isoformat(), "envoye_le": b.envoye_le.isoformat() if b.envoye_le else None,
        "recu_le": b.recu_le.isoformat() if b.recu_le else None,
    }


def obtenir_bon(session: Session, bid: Any) -> BonCommande:
    try:
        b = session.scalars(select(BonCommande).where(BonCommande.id == uuid.UUID(str(bid)))
                            .options(selectinload(BonCommande.lignes))).first()
    except ValueError:
        b = None
    if b is None:
        raise introuvable("Bon de commande")
    return b


def lister_bons(session: Session, statut: Optional[str] = None, fournisseur_id: Optional[str] = None) -> list[BonCommande]:
    stmt = select(BonCommande).options(selectinload(BonCommande.lignes))
    if statut:
        stmt = stmt.where(BonCommande.statut.in_(statut.split(",")))
    if fournisseur_id:
        stmt = stmt.where(BonCommande.fournisseur_id == uuid.UUID(str(fournisseur_id)))
    return list(session.scalars(stmt.order_by(BonCommande.cree_le.desc()).limit(300)))


def _ligne(session: Session, fournisseur_id: Optional[uuid.UUID], donnees: dict[str, Any], ordre: int) -> BonCommandeLigne:
    quantite = _entier(donnees.get("quantite"), "quantite", 1, 100000)
    boisson = None
    if donnees.get("boisson_id"):
        boisson = obtenir_boisson(session, donnees["boisson_id"])
    elif donnees.get("nom") or donnees.get("libelle"):
        nom = texte_court(donnees.get("nom") or donnees.get("libelle"), "nom", 200, obligatoire=True)
        boisson = next((b for b in session.scalars(select(Boisson)) if cle(b.nom) == cle(nom)), None)
        if boisson is None:
            return BonCommandeLigne(ordre=ordre, libelle=nom or "", quantite=quantite,
                                    unite=texte_court(donnees.get("unite"), "unite", 50))
    else:
        raise ErreurMetier("champ_obligatoire", "Indiquer la boisson.", champ="boisson_id")
    offre = None
    if fournisseur_id is not None:
        offre = session.get(BoissonFournisseur, (boisson.id, fournisseur_id))
    prix = lire_euros(donnees["prix_achat"]) if donnees.get("prix_achat") not in (None, "") else (
        offre.prix_achat_centimes if offre else None)
    return BonCommandeLigne(ordre=ordre, boisson_id=boisson.id, libelle=boisson.nom, unite=boisson.unite,
                            reference=offre.reference if offre else None, quantite=quantite, prix_achat_centimes=prix)


def creer_bon(session: Session, acteur: Acteur, fournisseur_id: Any, lignes: list[dict[str, Any]],
              note: Optional[str] = None, cle_idempotence: Optional[str] = None) -> BonCommande:
    acteur.exiger("fiches")
    cle_idempotence = texte_court(cle_idempotence, "cle_idempotence", 100)
    if cle_idempotence:
        deja = session.scalars(select(BonCommande).where(BonCommande.cle_idempotence == cle_idempotence)).first()
        if deja is not None:
            return obtenir_bon(session, deja.id)
    if not lignes:
        raise ErreurMetier("champ_obligatoire", "Le bon de commande n'a aucune ligne.", champ="lignes")
    fournisseur = obtenir_fournisseur(session, fournisseur_id) if fournisseur_id else None
    bon = BonCommande(numero=prochain_numero(session, "C", fiches.aujourd_hui().year),
                      fournisseur_id=fournisseur.id if fournisseur else None, statut="brouillon",
                      note=nettoyer_notes(note, 2000), cle_idempotence=cle_idempotence)
    for i, l in enumerate(lignes):
        bon.lignes.append(_ligne(session, bon.fournisseur_id, l, i))
    session.add(bon)
    session.flush()
    journaliser(session, acteur, "commande.creer", "bon_commande", bon.id,
                f"{bon.numero}" + (f" — {fournisseur.nom}" if fournisseur else "") + f", {len(lignes)} ligne(s)")
    session.commit()
    return obtenir_bon(session, bon.id)


def bons_depuis_reassort(session: Session, acteur: Acteur, quantites: dict[str, Any]) -> list[BonCommande]:
    """Un bon en brouillon par fournisseur préféré (et un sans fournisseur pour le reste)."""
    acteur.exiger("fiches")
    offres = _offres(session)
    groupes: dict[Optional[uuid.UUID], list[dict[str, Any]]] = {}
    for bid, q in quantites.items():
        q = int(q or 0)
        if q <= 0:
            continue
        b = obtenir_boisson(session, bid)
        pref = _offre_preferee(offres.get(b.id, []))
        groupes.setdefault(pref.fournisseur_id if pref else None, []).append({"boisson_id": str(b.id), "quantite": q})
    if not groupes:
        raise ErreurMetier("regle_metier", "Rien à commander.")
    return [creer_bon(session, acteur, fid, lignes, "Réassort") for fid, lignes in groupes.items()]


def modifier_bon(session: Session, acteur: Acteur, bid: Any, donnees: dict[str, Any], version: Optional[int] = None) -> BonCommande:
    acteur.exiger("fiches")
    bon = obtenir_bon(session, bid)
    verifier_version(bon, version, "Le bon de commande")
    if bon.statut != "brouillon":
        raise ErreurMetier("regle_metier", f"Le bon est « {STATUTS[bon.statut]} » : le repasser en brouillon pour le modifier.")
    if "fournisseur_id" in donnees:
        bon.fournisseur_id = obtenir_fournisseur(session, donnees["fournisseur_id"]).id if donnees["fournisseur_id"] else None
    if "note" in donnees:
        bon.note = nettoyer_notes(donnees["note"], 2000)
    if "lignes" in donnees:
        bon.lignes.clear()
        session.flush()
        for i, l in enumerate(donnees["lignes"] or []):
            bon.lignes.append(_ligne(session, bon.fournisseur_id, l, i))
    bon.version += 1
    journaliser(session, acteur, "commande.modifier", "bon_commande", bon.id, bon.numero)
    session.commit()
    return obtenir_bon(session, bon.id)


def changer_statut(session: Session, acteur: Acteur, bid: Any, cible: str) -> BonCommande:
    acteur.exiger("fiches")
    if acteur.est_chatgpt:
        raise ErreurMetier("interdit", "L'envoi au fournisseur et la réception se font dans l'outil.")
    bon = obtenir_bon(session, bid)
    if cible not in TRANSITIONS.get(bon.statut, ()):
        raise ErreurMetier("regle_metier", f"Impossible de passer de « {STATUTS[bon.statut]} » à « {STATUTS.get(cible, cible)} ».",
                           valeurs_permises=[STATUTS[s] for s in TRANSITIONS.get(bon.statut, ())])
    if cible == "envoye" and not bon.lignes:
        raise ErreurMetier("regle_metier", "Le bon n'a aucune ligne.")
    maintenant = datetime.now(reglages.fuseau)
    if cible == "envoye":
        bon.envoye_le = maintenant
    if cible == "recu":
        bon.recu_le = maintenant
    avant = bon.statut
    bon.statut = cible
    bon.version += 1
    journaliser(session, acteur, "commande.statut", "bon_commande", bon.id, f"{bon.numero} : {STATUTS[avant]} → {STATUTS[cible]}")
    session.commit()
    return bon


def csv_bon(bon: BonCommande) -> str:
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["Référence", "Article", "Unité", "Quantité", "Prix d'achat unitaire"])
    for l in bon.lignes:
        prix = "" if l.prix_achat_centimes is None else f"{l.prix_achat_centimes / 100:.2f}".replace(".", ",")
        ecrivain.writerow([l.reference or "", l.libelle, l.unite or "", l.quantite, prix])
    return tampon.getvalue()
