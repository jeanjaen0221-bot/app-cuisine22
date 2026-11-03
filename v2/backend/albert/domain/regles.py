"""Règles des fiches et calcul des devis.

Fonctions pures (aucun accès à la base) : elles lisent les attributs des objets
qu'on leur passe, ce qui les rend faciles à tester. Les mêmes règles servent au
site et à ChatGPT.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Protocol

from .erreurs import ErreurMetier
from .normalisation import LIBELLES_TYPES, TYPES_PLATS

COUVERTS_MAX = 500
QUANTITE_MAX = 5000

ESPACES = ("salle", "City", "Rooftop")

STATUTS_FICHE = ("brouillon", "confirmee", "finale", "realisee", "annulee")
LIBELLES_STATUTS_FICHE = {
    "brouillon": "Brouillon", "confirmee": "Confirmée", "finale": "Finale",
    "realisee": "Réalisée", "annulee": "Annulée",
}
# Fiches figées : on ne les modifie plus (il faut d'abord les rouvrir dans le site).
STATUTS_FIGES = ("finale", "realisee", "annulee")
TRANSITIONS_FICHE = {
    "brouillon": ("confirmee", "annulee"),
    "confirmee": ("brouillon", "finale", "annulee"),
    "finale": ("confirmee", "realisee", "annulee"),
    "realisee": ("finale",),
    "annulee": ("brouillon",),
}

UNITES = ("par_personne", "piece", "forfait", "bouteille")
LIBELLES_UNITES = {"par_personne": "par personne", "piece": "pièce", "forfait": "forfait", "bouteille": "bouteille"}
CATEGORIES_PRODUIT = (
    "formule_repas", "formule_boissons", "coupe", "entree", "plat", "dessert", "supplement", "privatisation",
)
LIBELLES_CATEGORIES = {
    "formule_repas": "Formules repas", "formule_boissons": "Formules boissons", "coupe": "Coupes",
    "entree": "Entrées", "plat": "Plats", "dessert": "Desserts", "supplement": "Suppléments",
    "privatisation": "Privatisations",
}
COMPORTEMENTS_FORMULE = ("services", "carte", "sans_plats")
MODES_BOISSONS = ("formule", "consommation", "aucune")


class LigneLike(Protocol):
    type: str
    quantite: int


# --------------------------------------------------------------- fiche

def verifier_couverts(couverts: Any) -> int:
    try:
        n = int(couverts)
    except (TypeError, ValueError):
        raise ErreurMetier("champ_obligatoire", "Le nombre de couverts est obligatoire.", champ="couverts")
    if not 1 <= n <= COUVERTS_MAX:
        raise ErreurMetier("regle_metier", f"Couverts : entre 1 et {COUVERTS_MAX}.", champ="couverts")
    return n


def verifier_quantite(quantite: Any) -> int:
    try:
        n = int(quantite)
    except (TypeError, ValueError):
        raise ErreurMetier("champ_obligatoire", "La quantité est obligatoire.", champ="quantite")
    if not 1 <= n <= QUANTITE_MAX:
        raise ErreurMetier("regle_metier", f"Quantité : entre 1 et {QUANTITE_MAX}.", champ="quantite")
    return n


def types_plats(lignes: Iterable[LigneLike]) -> list[str]:
    presents = {l.type for l in lignes if l.type in TYPES_PLATS and l.quantite > 0}
    return [t for t in TYPES_PLATS if t in presents]


def appliquer_regles_fiche(couverts: int, formule_repas: Any, lignes: list[LigneLike]) -> tuple[Any, list[str]]:
    """Vérifie une fiche et renvoie (formule repas à enregistrer, alertes).

    - total d'entrées (resp. plats, desserts) ≤ couverts ;
    - formule « sans plats » (Brunch, Sharing) : aucune entrée/plat/dessert ;
    - formule « services » + plats : les plats prévalent, la formule est vidée
      (le devis la retrouve à partir des types de plats) ;
    - « À la carte » : gardée avec les plats, chacun compté à son prix.
    """
    totaux = {t: 0 for t in TYPES_PLATS}
    for l in lignes:
        if l.type in totaux:
            totaux[l.type] += l.quantite
    depassements = [f"{LIBELLES_TYPES[t]}s : {n}" for t, n in totaux.items() if n > couverts]
    if depassements:
        raise ErreurMetier(
            "regle_metier",
            f"Le total par type dépasse le nombre de couverts ({couverts}) : " + ", ".join(depassements) + ".",
            champ="lignes",
        )
    plats = types_plats(lignes)
    alertes: list[str] = []
    if formule_repas is not None:
        if formule_repas.comportement == "sans_plats" and plats:
            raise ErreurMetier(
                "regle_metier",
                f"La formule {formule_repas.nom} ne prend pas d'entrée, de plat ni de dessert : "
                "mettre les extras en suppléments, ou changer de formule.",
                champ="formule_repas",
            )
        if formule_repas.comportement == "services" and plats:
            formule_repas = None  # les plats prévalent
        elif formule_repas.comportement == "carte" and not plats:
            alertes.append("À la carte sans plats : le repas n'apparaîtra pas au devis tant que les plats ne sont pas indiqués.")
    if formule_repas is None and not plats:
        alertes.append("Ni formule repas ni plats : à compléter avant de confirmer la fiche.")
    return formule_repas, alertes


def peut_confirmer(formule_repas: Any, lignes: list[LigneLike]) -> bool:
    return formule_repas is not None or bool(types_plats(lignes))


def verifier_transition(actuel: str, cible: str) -> None:
    if cible not in STATUTS_FICHE:
        raise ErreurMetier("valeur_non_permise", f"Statut inconnu : {cible!r}.", champ="statut",
                           valeurs_permises=list(STATUTS_FICHE))
    if cible not in TRANSITIONS_FICHE.get(actuel, ()):
        raise ErreurMetier(
            "regle_metier",
            f"Impossible de passer de « {LIBELLES_STATUTS_FICHE[actuel]} » à « {LIBELLES_STATUTS_FICHE[cible]} ».",
            champ="statut",
            valeurs_permises=[LIBELLES_STATUTS_FICHE[s] for s in TRANSITIONS_FICHE.get(actuel, ())],
        )


# --------------------------------------------------------------- devis

@dataclass
class LigneCalculee:
    categorie: str
    libelle: str
    quantite: int
    unite: str
    prix_unitaire_centimes: Optional[int]
    produit_id: Any = None

    @property
    def total_centimes(self) -> Optional[int]:
        if self.prix_unitaire_centimes is None:
            return None
        return self.prix_unitaire_centimes * self.quantite


@dataclass
class DevisCalcule:
    lignes: list[LigneCalculee] = field(default_factory=list)
    manques: list[str] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)

    @property
    def total_centimes(self) -> int:
        return sum(l.total_centimes or 0 for l in self.lignes)


def _ligne_produit(calc: DevisCalcule, categorie: str, produit: Any, libelle_defaut: str,
                   quantite: int, unite_defaut: str) -> None:
    prix = getattr(produit, "prix_centimes", None) if produit is not None else None
    libelle = getattr(produit, "nom", None) or libelle_defaut
    unite = getattr(produit, "unite", None) or unite_defaut
    calc.lignes.append(LigneCalculee(categorie, libelle, quantite, unite, prix, getattr(produit, "id", None)))
    if prix is None:
        calc.manques.append(f"Prix manquant : {libelle} (à compléter dans le menu Prix).")


def calculer_devis(fiche: Any, formules_par_services: dict[int, Any]) -> DevisCalcule:
    """Lignes du devis à partir de la fiche, aux prix actuels du catalogue (TVA comprise).

    `formules_par_services` : formules actives de comportement « services », par nombre
    de services (1, 2, 3), pour retrouver la formule quand la fiche liste des plats.
    """
    calc = DevisCalcule()
    couverts = fiche.couverts
    lignes = list(fiche.lignes)
    plats = types_plats(lignes)
    formule = fiche.formule_repas

    # Repas
    if formule is not None and formule.comportement == "carte":
        for l in lignes:
            if l.type in TYPES_PLATS:
                _ligne_produit(calc, l.type, l.produit, l.libelle, l.quantite, "piece")
                if l.produit is None:
                    calc.manques[-1] = f"Prix manquant : {l.libelle} (plat hors carte : le relier à un plat du menu Prix)."
    elif formule is not None:
        _ligne_produit(calc, "formule_repas", formule.produit, formule.nom, couverts, "par_personne")
    elif plats:
        n = len(plats)
        trouvee = formules_par_services.get(n)
        libelle = f"{n} service" + ("s" if n > 1 else "")
        if trouvee is None:
            calc.lignes.append(LigneCalculee("formule_repas", libelle, couverts, "par_personne", None))
            calc.manques.append(f"Aucune formule active « {libelle} » dans le menu Formules.")
        else:
            _ligne_produit(calc, "formule_repas", trouvee.produit, trouvee.nom, couverts, "par_personne")
    else:
        calc.alertes.append("Ni formule repas ni plats sur la fiche : pas de ligne repas.")

    # Boissons
    fb = fiche.formule_boissons
    if fb is not None and fb.mode == "formule":
        if fb.base_produit is not None:
            _ligne_produit(calc, "formule_boissons", fb.base_produit, fb.nom, couverts, "par_personne")
        if fb.coupe_produit is not None:
            _ligne_produit(calc, "coupe", fb.coupe_produit, "Coupe", couverts, "par_personne")
    elif fb is not None and fb.mode == "consommation":
        calc.alertes.append("Boissons à la consommation : elles seront ajoutées au bon pour facturation.")

    # Suppléments
    for l in lignes:
        if l.type == "supplement":
            _ligne_produit(calc, "supplement", l.produit, l.libelle, l.quantite, "piece")
            if l.produit is None:
                calc.manques[-1] = f"Prix manquant : {l.libelle} (supplément hors catalogue : le relier à un produit du menu Prix)."

    # Privatisation
    if fiche.privatisation is not None:
        _ligne_produit(calc, "privatisation", fiche.privatisation, "Privatisation", 1, "forfait")

    return calc


def signature_fiche(fiche: Any) -> str:
    """Empreinte de ce qui compte pour le devis : sert à repérer « devis à mettre à jour »."""
    contenu = {
        "date": str(fiche.date), "heure": str(fiche.heure), "couverts": fiche.couverts,
        "formule_repas": str(fiche.formule_repas_id), "formule_boissons": str(fiche.formule_boissons_id),
        "privatisation": str(fiche.privatisation_id), "espace": fiche.espace,
        "lignes": sorted((l.type, l.libelle, l.quantite, str(l.produit_id)) for l in fiche.lignes),
    }
    return hashlib.sha256(json.dumps(contenu, sort_keys=True).encode()).hexdigest()
