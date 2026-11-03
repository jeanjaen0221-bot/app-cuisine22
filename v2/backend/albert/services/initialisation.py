"""Catalogue de départ : grille de prix fournie le 22/10/2026 (docs/REFONTE_ANALYSE.md §12.3).

Idempotent : ne crée que ce qui manque, ne touche jamais un prix déjà saisi.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FormuleBoissons, FormuleRepas, Produit

# (catégorie, nom, unité, prix TVAC en centimes ou None = à compléter, ordre)
PRODUITS = [
    ("formule_repas", "1 service", "par_personne", 2800, 1),
    ("formule_repas", "2 services", "par_personne", 3200, 2),
    ("formule_repas", "3 services", "par_personne", 4000, 3),
    ("formule_repas", "Sharing", "par_personne", 3200, 4),
    ("formule_repas", "Brunch", "par_personne", 3600, 5),
    ("formule_boissons", "Formule sans alcool", "par_personne", 1000, 1),
    ("formule_boissons", "Formule avec alcool", "par_personne", 2000, 2),
    ("coupe", "Coupe de cava", "par_personne", 600, 1),
    ("coupe", "Coupe de champagne", "par_personne", 1100, 2),
    ("privatisation", "Semi-privatisation", "forfait", None, 1),
    ("privatisation", "Privatisation complète", "forfait", None, 2),
    ("privatisation", "Privatisation City", "forfait", 60000, 3),
    # Donnée à 3,85 € HTVA : le prix TVA comprise est à saisir dans le menu Prix.
    ("supplement", "Planche apéro", "par_personne", None, 1),
    ("supplement", "Coupe de cava", "par_personne", 600, 2),
    ("supplement", "Coupe de champagne", "par_personne", 1100, 3),
]

# (nom, comportement, nb_services, produit, ordre)
FORMULES_REPAS = [
    ("1 service", "services", 1, "1 service", 1),
    ("2 services", "services", 2, "2 services", 2),
    ("3 services", "services", 3, "3 services", 3),
    ("Sharing", "sans_plats", None, "Sharing", 4),
    ("Brunch", "sans_plats", None, "Brunch", 5),
    ("À la carte", "carte", None, None, 6),
]

# (nom, mode, base, coupe, couleur, par défaut, ordre) — couleurs des badges de l'ancienne fiche salle.
FORMULES_BOISSONS = [
    ("sans alcool", "formule", "Formule sans alcool", None, "bleu", True, 1),
    ("avec alcool", "formule", "Formule avec alcool", None, "rouge", False, 2),
    ("sans alcool + cava", "formule", "Formule sans alcool", "Coupe de cava", "cyan", False, 3),
    ("avec alcool + cava", "formule", "Formule avec alcool", "Coupe de cava", "violet", False, 4),
    ("sans alcool + champ", "formule", "Formule sans alcool", "Coupe de champagne", "vert", False, 5),
    ("avec alcool + champ", "formule", "Formule avec alcool", "Coupe de champagne", "ambre", False, 6),
    ("à la carte", "consommation", None, None, "indigo", False, 7),
    ("sans Formule", "aucune", None, None, "gris", False, 8),
]


def initialiser_catalogue(session: Session) -> None:
    existants = {(p.categorie, p.nom): p for p in session.scalars(select(Produit))}
    for categorie, nom, unite, prix, ordre in PRODUITS:
        if (categorie, nom) not in existants:
            p = Produit(categorie=categorie, nom=nom, unite=unite, prix_centimes=prix, ordre=ordre)
            session.add(p)
            existants[(categorie, nom)] = p
    session.flush()

    def produit(categorie: str, nom: Optional[str]) -> Optional[Produit]:
        return existants.get((categorie, nom)) if nom else None

    noms_repas = set(session.scalars(select(FormuleRepas.nom)))
    for nom, comportement, nb, nom_produit, ordre in FORMULES_REPAS:
        if nom not in noms_repas:
            p = produit("formule_repas", nom_produit)
            session.add(FormuleRepas(nom=nom, comportement=comportement, nb_services=nb,
                                     produit_id=p.id if p else None, ordre=ordre))

    noms_boissons = set(session.scalars(select(FormuleBoissons.nom)))
    for nom, mode, base, coupe, couleur, defaut, ordre in FORMULES_BOISSONS:
        if nom not in noms_boissons:
            b, c = produit("formule_boissons", base), produit("coupe", coupe)
            session.add(FormuleBoissons(nom=nom, mode=mode, base_produit_id=b.id if b else None,
                                        coupe_produit_id=c.id if c else None, couleur=couleur,
                                        par_defaut=defaut, ordre=ordre))
    session.commit()
