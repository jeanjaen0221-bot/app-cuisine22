"""Règles pures : montants, saisies, règles des fiches."""
from datetime import date, time
from types import SimpleNamespace as N

import pytest

from albert.domain.argent import format_euros, lire_euros
from albert.domain.erreurs import ErreurMetier
from albert.domain.normalisation import (
    choisir,
    cle_nom_client,
    lire_allergenes,
    lire_date,
    lire_heure,
    lire_tva,
    lire_type_ligne,
    nettoyer_notes,
)
from albert.domain.regles import appliquer_regles_fiche, peut_confirmer, verifier_transition


@pytest.mark.parametrize("saisie,centimes", [
    ("4,31", 431), ("4.31", 431), ("32", 3200), ("1 234,50", 123450), ("1.234,50", 123450),
    ("0", 0), ("6,5", 650), ("11 €", 1100), (431, 431), ("", None), (None, None),
])
def test_lire_euros(saisie, centimes):
    assert lire_euros(saisie) == centimes


@pytest.mark.parametrize("saisie", ["abc", "-3", "4,315", "4,3,1"])
def test_lire_euros_refuse(saisie):
    with pytest.raises(ErreurMetier):
        lire_euros(saisie)


def test_format_euros():
    assert format_euros(192000) == "1 920,00 €"
    assert format_euros(431) == "4,31 €"
    assert format_euros(None) == "prix manquant"


def test_dates_et_heures():
    assert lire_date("17/09/2026") == date(2026, 9, 17)
    assert lire_date("2026-09-17") == date(2026, 9, 17)
    assert lire_heure("19h30") == time(19, 30)
    assert lire_heure("19h") == time(19, 0)
    assert lire_heure("1930") == time(19, 30)
    with pytest.raises(ErreurMetier) as e:
        lire_heure("")
    assert e.value.code == "champ_obligatoire"
    with pytest.raises(ErreurMetier):
        lire_heure("25:00")


def test_allergenes():
    assert lire_allergenes(["lactose", "Sans gluten", "allergie aux arachides", "noix"]) == [
        "lait", "gluten", "arachides", "fruits_a_coque"]
    assert lire_allergenes("lait, lait") == ["lait"]
    with pytest.raises(ErreurMetier) as e:
        lire_allergenes(["kiwi"])
    assert e.value.code == "valeur_non_permise"
    assert "lait" in e.value.valeurs_permises


def test_types_de_ligne():
    assert lire_type_ligne("Main course") == "plat"
    assert lire_type_ligne("Entrées") == "entree"
    assert lire_type_ligne("extra") == "supplement"
    with pytest.raises(ErreurMetier):
        lire_type_ligne("apéritif")


def test_choisir_formule_avec_alias():
    options = [("3 services", 3), ("Brunch", "b"), ("avec alcool + champ", "ac")]
    assert choisir("3 Services", options, "f") == 3
    assert choisir("trois services", options, "f") == 3
    assert choisir("buffet", options, "f") == "b"
    assert choisir("Avec alcool + champagne", options, "f") == "ac"
    assert choisir("", options, "f", vide_permis=True) is None
    with pytest.raises(ErreurMetier) as e:
        choisir("4 services", options, "f")
    assert e.value.valeurs_permises == ["3 services", "Brunch", "avec alcool + champ"]


def test_tva_belge():
    assert lire_tva("BE 0123.456.749") == "BE0123456749"
    assert lire_tva("0123456749") == "BE0123456749"
    with pytest.raises(ErreurMetier):
        lire_tva("BE0123456748")  # mauvaise clé de contrôle
    assert lire_tva("FR12345678901") == "FR12345678901"


def test_doublons_de_nom():
    assert cle_nom_client("Dupont S.A.") == cle_nom_client("dupont sa") == "dupont"
    assert cle_nom_client("Volta SRL") == cle_nom_client("VOLTA")


def test_notes():
    assert nettoyer_notes("# Titre\n* point\n**gras**") == "Titre\n- point\n**gras**"


SERVICES = N(nom="3 services", comportement="services")
BRUNCH = N(nom="Brunch", comportement="sans_plats")
SHARING = N(nom="Sharing", comportement="sans_plats")
CARTE = N(nom="À la carte", comportement="carte")


def L(type_, quantite=1):
    return N(type=type_, quantite=quantite)


def test_total_par_type_limite_aux_couverts():
    with pytest.raises(ErreurMetier) as e:
        appliquer_regles_fiche(10, None, [L("plat", 12)])
    assert e.value.code == "regle_metier"
    appliquer_regles_fiche(10, None, [L("plat", 6), L("plat", 4)])


def test_les_plats_prevalent_sur_une_formule_services():
    formule, _ = appliquer_regles_fiche(10, SERVICES, [L("entree", 10), L("plat", 10), L("dessert", 10)])
    assert formule is None


@pytest.mark.parametrize("formule", [BRUNCH, SHARING])
def test_brunch_et_sharing_sans_plats(formule):
    with pytest.raises(ErreurMetier):
        appliquer_regles_fiche(12, formule, [L("plat", 1)])
    retenue, _ = appliquer_regles_fiche(12, formule, [L("supplement", 12)])
    assert retenue is formule


def test_a_la_carte_garde_les_plats():
    formule, _ = appliquer_regles_fiche(4, CARTE, [L("plat", 4)])
    assert formule is CARTE


def test_confirmation_et_transitions():
    assert not peut_confirmer(None, [L("supplement")])
    assert peut_confirmer(BRUNCH, [])
    verifier_transition("brouillon", "confirmee")
    with pytest.raises(ErreurMetier):
        verifier_transition("brouillon", "realisee")
