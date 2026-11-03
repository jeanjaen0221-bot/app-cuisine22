"""Menus « Prix » (produits) et « Formules » (formules repas et boissons)."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.argent import format_euros, lire_euros
from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import ALLERGENES, cle, lire_allergenes, texte_court
from ..domain.regles import (
    CATEGORIES_PRODUIT,
    COMPORTEMENTS_FORMULE,
    ESPACES,
    LIBELLES_CATEGORIES,
    LIBELLES_STATUTS_FICHE,
    LIBELLES_UNITES,
    MODES_BOISSONS,
    UNITES,
)
from ..models import Fiche, FormuleBoissons, FormuleRepas, Produit
from .contexte import Acteur, journaliser, lire_parametres

COULEURS_BOISSONS = ("bleu", "rouge", "cyan", "violet", "vert", "ambre", "indigo", "gris")


# --------------------------------------------------------------- produits

def produit_dict(p: Produit) -> dict[str, Any]:
    return {
        "id": str(p.id), "nom": p.nom, "categorie": p.categorie, "unite": p.unite,
        "unite_libelle": LIBELLES_UNITES.get(p.unite, p.unite),
        "prix_centimes": p.prix_centimes, "prix": format_euros(p.prix_centimes),
        "prix_manquant": p.prix_centimes is None, "allergenes": p.allergenes or [],
        "actif": p.actif, "ordre": p.ordre,
    }


def lister_produits(session: Session, categorie: Optional[str] = None, q: Optional[str] = None,
                    manquants: bool = False, actifs_seulement: bool = False) -> list[Produit]:
    stmt = select(Produit)
    if categorie:
        stmt = stmt.where(Produit.categorie == categorie)
    if manquants:
        stmt = stmt.where(Produit.prix_centimes.is_(None), Produit.actif.is_(True))
    if actifs_seulement:
        stmt = stmt.where(Produit.actif.is_(True))
    produits = list(session.scalars(stmt.order_by(Produit.categorie, Produit.ordre, Produit.nom)))
    if q:
        mots = cle(q).split()
        produits = [p for p in produits if all(m in cle(p.nom) for m in mots)]
    return produits


def compter_prix_manquants(session: Session) -> int:
    return session.scalar(
        select(func.count()).select_from(Produit).where(Produit.prix_centimes.is_(None), Produit.actif.is_(True))
    ) or 0


def _valider_produit(donnees: dict[str, Any], partiel: bool) -> dict[str, Any]:
    sortie: dict[str, Any] = {}
    if "nom" in donnees or not partiel:
        sortie["nom"] = texte_court(donnees.get("nom"), "nom", 200, obligatoire=True)
    if "categorie" in donnees or not partiel:
        c = donnees.get("categorie")
        if c not in CATEGORIES_PRODUIT:
            raise ErreurMetier("valeur_non_permise", f"Catégorie inconnue : {c!r}.", champ="categorie",
                               valeurs_permises=list(CATEGORIES_PRODUIT))
        sortie["categorie"] = c
    if "unite" in donnees or not partiel:
        u = donnees.get("unite") or "piece"
        if u not in UNITES:
            raise ErreurMetier("valeur_non_permise", f"Unité inconnue : {u!r}.", champ="unite",
                               valeurs_permises=list(UNITES))
        sortie["unite"] = u
    if "prix" in donnees:
        sortie["prix_centimes"] = lire_euros(donnees["prix"])
    elif "prix_centimes" in donnees:
        sortie["prix_centimes"] = lire_euros(donnees["prix_centimes"]) if donnees["prix_centimes"] is not None else None
    if "allergenes" in donnees:
        sortie["allergenes"] = lire_allergenes(donnees["allergenes"])
    for champ in ("actif",):
        if champ in donnees:
            sortie[champ] = bool(donnees[champ])
    if "ordre" in donnees:
        sortie["ordre"] = int(donnees["ordre"] or 0)
    return sortie


def _doublon_produit(session: Session, categorie: str, nom: str, sauf: Optional[uuid.UUID] = None) -> None:
    for p in session.scalars(select(Produit).where(Produit.categorie == categorie)):
        if p.id != sauf and cle(p.nom) == cle(nom):
            raise ErreurMetier("doublon_probable", f"« {p.nom} » existe déjà dans {LIBELLES_CATEGORIES[categorie]}.",
                               champ="nom", details={"produit_id": str(p.id)})


def creer_produit(session: Session, acteur: Acteur, donnees: dict[str, Any]) -> Produit:
    acteur.exiger("prix")
    valeurs = _valider_produit(donnees, partiel=False)
    _doublon_produit(session, valeurs["categorie"], valeurs["nom"])
    produit = Produit(**valeurs)
    session.add(produit)
    session.flush()
    journaliser(session, acteur, "produit.creer", "produit", produit.id,
                f"{produit.nom} ({format_euros(produit.prix_centimes)})", None, produit_dict(produit))
    session.commit()
    return produit


def modifier_produit(session: Session, acteur: Acteur, produit_id: uuid.UUID, donnees: dict[str, Any]) -> Produit:
    acteur.exiger("prix")
    produit = session.get(Produit, produit_id)
    if produit is None:
        raise introuvable("Produit")
    avant = produit_dict(produit)
    valeurs = _valider_produit(donnees, partiel=True)
    if "nom" in valeurs or "categorie" in valeurs:
        _doublon_produit(session, valeurs.get("categorie", produit.categorie), valeurs.get("nom", produit.nom), produit.id)
    for k, v in valeurs.items():
        setattr(produit, k, v)
    session.flush()
    resume = produit.nom
    if avant["prix_centimes"] != produit.prix_centimes:
        resume += f" : {avant['prix']} → {format_euros(produit.prix_centimes)}"
    journaliser(session, acteur, "produit.modifier", "produit", produit.id, resume, avant, produit_dict(produit))
    session.commit()
    return produit


# --------------------------------------------------------------- formules

def formule_repas_dict(f: FormuleRepas) -> dict[str, Any]:
    if f.comportement == "carte":
        prix = "prix de la carte"
        centimes = None
    else:
        centimes = f.produit.prix_centimes if f.produit else None
        prix = format_euros(centimes) + " par personne" if centimes is not None else "prix manquant"
    return {
        "id": str(f.id), "nom": f.nom, "comportement": f.comportement, "nb_services": f.nb_services,
        "produit_id": str(f.produit_id) if f.produit_id else None, "prix_centimes": centimes,
        "prix": prix, "actif": f.actif, "ordre": f.ordre,
    }


def formule_boissons_dict(f: FormuleBoissons) -> dict[str, Any]:
    parts = [p for p in (f.base_produit, f.coupe_produit) if p is not None]
    if f.mode != "formule":
        centimes, prix = None, ("à la consommation" if f.mode == "consommation" else "aucune ligne")
    elif any(p.prix_centimes is None for p in parts):
        centimes, prix = None, "prix manquant"
    else:
        centimes = sum(p.prix_centimes for p in parts)  # type: ignore[misc]
        detail = " + ".join(format_euros(p.prix_centimes) for p in parts)
        prix = f"{format_euros(centimes)} par personne" + (f" ({detail})" if len(parts) > 1 else "")
    return {
        "id": str(f.id), "nom": f.nom, "mode": f.mode,
        "base_produit_id": str(f.base_produit_id) if f.base_produit_id else None,
        "coupe_produit_id": str(f.coupe_produit_id) if f.coupe_produit_id else None,
        "base": f.base_produit.nom if f.base_produit else None,
        "coupe": f.coupe_produit.nom if f.coupe_produit else None,
        "prix_centimes": centimes, "prix": prix, "couleur": f.couleur, "par_defaut": f.par_defaut,
        "actif": f.actif, "ordre": f.ordre,
    }


def lister_formules_repas(session: Session, actives: bool = False) -> list[FormuleRepas]:
    stmt = select(FormuleRepas).order_by(FormuleRepas.ordre, FormuleRepas.nom)
    if actives:
        stmt = stmt.where(FormuleRepas.actif.is_(True))
    return list(session.scalars(stmt))


def lister_formules_boissons(session: Session, actives: bool = False) -> list[FormuleBoissons]:
    stmt = select(FormuleBoissons).order_by(FormuleBoissons.ordre, FormuleBoissons.nom)
    if actives:
        stmt = stmt.where(FormuleBoissons.actif.is_(True))
    return list(session.scalars(stmt))


def formules_par_services(session: Session) -> dict[int, FormuleRepas]:
    sortie: dict[int, FormuleRepas] = {}
    for f in lister_formules_repas(session, actives=True):
        if f.comportement == "services" and f.nb_services and f.nb_services not in sortie:
            sortie[f.nb_services] = f
    return sortie


def _produit_de(session: Session, produit_id: Any, categories: tuple[str, ...], champ: str) -> Optional[Produit]:
    if produit_id in (None, ""):
        return None
    try:
        produit = session.get(Produit, uuid.UUID(str(produit_id)))
    except ValueError:
        produit = None
    if produit is None or produit.categorie not in categories:
        raise ErreurMetier("valeur_non_permise", f"{champ} : produit introuvable dans le menu Prix.", champ=champ)
    return produit


def enregistrer_formule_repas(session: Session, acteur: Acteur, donnees: dict[str, Any],
                              formule_id: Optional[uuid.UUID] = None) -> FormuleRepas:
    acteur.exiger("prix")
    formule = session.get(FormuleRepas, formule_id) if formule_id else FormuleRepas()
    if formule is None:
        raise introuvable("Formule")
    avant = formule_repas_dict(formule) if formule_id else None
    if "nom" in donnees or not formule_id:
        nom = texte_court(donnees.get("nom"), "nom", 100, obligatoire=True)
        for autre in lister_formules_repas(session):
            if autre.id != formule.id and cle(autre.nom) == cle(nom):
                raise ErreurMetier("doublon_probable", f"La formule « {autre.nom} » existe déjà.", champ="nom")
        formule.nom = nom
    if "comportement" in donnees or not formule_id:
        c = donnees.get("comportement")
        if c not in COMPORTEMENTS_FORMULE:
            raise ErreurMetier("valeur_non_permise", "Comportement inconnu.", champ="comportement",
                               valeurs_permises=list(COMPORTEMENTS_FORMULE))
        formule.comportement = c
    if "nb_services" in donnees:
        n = donnees.get("nb_services")
        formule.nb_services = int(n) if n not in (None, "") else None
    if formule.comportement == "services" and formule.nb_services not in (1, 2, 3):
        raise ErreurMetier("regle_metier", "Une formule « services » indique 1, 2 ou 3 services.", champ="nb_services")
    if formule.comportement != "services":
        formule.nb_services = None
    if "produit_id" in donnees:
        produit = _produit_de(session, donnees.get("produit_id"), ("formule_repas",), "produit_id")
        formule.produit_id = produit.id if produit else None
    if formule.comportement == "carte":
        formule.produit_id = None
    elif formule.produit_id is None:
        # Crée le produit correspondant dans le menu Prix (prix à compléter).
        existant = next((p for p in lister_produits(session, "formule_repas") if cle(p.nom) == cle(formule.nom)), None)
        if existant is None:
            existant = Produit(nom=formule.nom, categorie="formule_repas", unite="par_personne", prix_centimes=None)
            session.add(existant)
            session.flush()
        formule.produit_id = existant.id
    for champ in ("actif",):
        if champ in donnees:
            setattr(formule, champ, bool(donnees[champ]))
    if "ordre" in donnees:
        formule.ordre = int(donnees["ordre"] or 0)
    session.add(formule)
    session.flush()
    session.refresh(formule)
    journaliser(session, acteur, "formule_repas." + ("modifier" if formule_id else "creer"), "formule_repas",
                formule.id, formule.nom, avant, formule_repas_dict(formule))
    session.commit()
    return formule


def enregistrer_formule_boissons(session: Session, acteur: Acteur, donnees: dict[str, Any],
                                 formule_id: Optional[uuid.UUID] = None) -> FormuleBoissons:
    acteur.exiger("prix")
    formule = session.get(FormuleBoissons, formule_id) if formule_id else FormuleBoissons()
    if formule is None:
        raise introuvable("Formule")
    avant = formule_boissons_dict(formule) if formule_id else None
    if "nom" in donnees or not formule_id:
        nom = texte_court(donnees.get("nom"), "nom", 100, obligatoire=True)
        for autre in lister_formules_boissons(session):
            if autre.id != formule.id and cle(autre.nom) == cle(nom):
                raise ErreurMetier("doublon_probable", f"La formule « {autre.nom} » existe déjà.", champ="nom")
        formule.nom = nom
    if "mode" in donnees or not formule_id:
        m = donnees.get("mode") or "formule"
        if m not in MODES_BOISSONS:
            raise ErreurMetier("valeur_non_permise", "Mode inconnu.", champ="mode", valeurs_permises=list(MODES_BOISSONS))
        formule.mode = m
    if "base_produit_id" in donnees:
        p = _produit_de(session, donnees.get("base_produit_id"), ("formule_boissons",), "base_produit_id")
        formule.base_produit_id = p.id if p else None
    if "coupe_produit_id" in donnees:
        p = _produit_de(session, donnees.get("coupe_produit_id"), ("coupe",), "coupe_produit_id")
        formule.coupe_produit_id = p.id if p else None
    if formule.mode != "formule":
        formule.base_produit_id = None
        formule.coupe_produit_id = None
    elif formule.base_produit_id is None and formule.coupe_produit_id is None:
        raise ErreurMetier("regle_metier", "Une formule boissons a une base et/ou une coupe.", champ="base_produit_id")
    if "couleur" in donnees:
        if donnees["couleur"] not in COULEURS_BOISSONS:
            raise ErreurMetier("valeur_non_permise", "Couleur inconnue.", champ="couleur",
                               valeurs_permises=list(COULEURS_BOISSONS))
        formule.couleur = donnees["couleur"]
    if "actif" in donnees:
        formule.actif = bool(donnees["actif"])
    if "ordre" in donnees:
        formule.ordre = int(donnees["ordre"] or 0)
    if donnees.get("par_defaut"):
        for autre in lister_formules_boissons(session):
            autre.par_defaut = False
        formule.par_defaut = True
    session.add(formule)
    session.flush()
    session.refresh(formule)
    journaliser(session, acteur, "formule_boissons." + ("modifier" if formule_id else "creer"), "formule_boissons",
                formule.id, formule.nom, avant, formule_boissons_dict(formule))
    session.commit()
    return formule


# --------------------------------------------------------------- références

def references(session: Session) -> dict[str, Any]:
    """Tout ce qu'on peut choisir sur une fiche (formulaire du site et ChatGPT)."""
    params = lire_parametres(session)
    return {
        "formules_repas": [formule_repas_dict(f) for f in lister_formules_repas(session, actives=True)],
        "formules_boissons": [formule_boissons_dict(f) for f in lister_formules_boissons(session, actives=True)],
        "privatisations": [produit_dict(p) for p in lister_produits(session, "privatisation", actifs_seulement=True)],
        "espaces": list(ESPACES),
        "types_ligne": [{"cle": "entree", "libelle": "entrée"}, {"cle": "plat", "libelle": "plat"},
                        {"cle": "dessert", "libelle": "dessert"}, {"cle": "supplement", "libelle": "supplément"}],
        "allergenes": [{"cle": k, "libelle": v} for k, v in ALLERGENES.items()],
        "statuts_fiche": [{"cle": k, "libelle": v} for k, v in LIBELLES_STATUTS_FICHE.items()],
        "heures_proposees": params.get("heures_proposees", []),
        "unites": [{"cle": k, "libelle": v} for k, v in LIBELLES_UNITES.items()],
        "categories": [{"cle": k, "libelle": v} for k, v in LIBELLES_CATEGORIES.items()],
        "couleurs_boissons": list(COULEURS_BOISSONS),
    }


def formule_utilisee(session: Session, formule: Any) -> bool:
    colonne = Fiche.formule_repas_id if isinstance(formule, FormuleRepas) else Fiche.formule_boissons_id
    return bool(session.scalar(select(func.count()).select_from(Fiche).where(colonne == formule.id)))
