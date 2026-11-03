"""Fiches et devis, au niveau des services (mêmes règles pour le site et ChatGPT)."""
import pytest
from sqlalchemy import select

from albert.domain.erreurs import ErreurMetier
from albert.models import Audit, Produit
from albert.services import catalogue, devis, fiches

from .conftest import nouveau_client


def creer_fiche(session, acteur, **donnees):
    client = nouveau_client(session, acteur, donnees.pop("nom_client", "Dupont"))
    base = {"client_id": str(client.id), "date": "2030-06-12", "heure": "19h30", "couverts": 20}
    base.update(donnees)
    fiche, alertes = fiches.creer(session, acteur, base)
    return fiche, alertes


def total(session, acteur, fiche):
    d, _ = devis.preparer(session, acteur, fiche.id)
    return d


def test_exemple_de_la_grille_1920_euros(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, formule_repas="3 services", formule_boissons="avec alcool + cava",
                           privatisation="Privatisation City")
    d = total(session, acteur_admin, fiche)
    assert [(l.libelle, l.quantite, l.prix_unitaire_centimes) for l in d.lignes] == [
        ("3 services", 20, 4000), ("Formule avec alcool", 20, 2000), ("Coupe de cava", 20, 600),
        ("Privatisation City", 1, 60000)]
    assert d.total_centimes == 192000
    assert devis.devis_dict(session, d)["total"] == "1 920,00 €"


def test_formule_deduite_des_plats(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, couverts=10, formule_repas="2 services", lignes=[
        {"type": "entrée", "libelle": "Carpaccio", "quantite": 10},
        {"type": "plat", "libelle": "Steak", "quantite": 10},
        {"type": "dessert", "libelle": "Moelleux", "quantite": 10}])
    assert fiche.formule_repas is None  # les plats prévalent
    d = total(session, acteur_admin, fiche)
    repas = d.lignes[0]
    assert (repas.libelle, repas.quantite, repas.total_centimes) == ("3 services", 10, 40000)


def test_un_service(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, couverts=15, formule_repas="1 service", formule_boissons="sans Formule")
    assert total(session, acteur_admin, fiche).total_centimes == 42000


def test_brunch_et_planche_sans_prix(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, couverts=30, formule_repas="Brunch", formule_boissons="sans Formule",
                           lignes=[{"type": "supplément", "libelle": "planche apéro", "quantite": 30}])
    d = total(session, acteur_admin, fiche)
    assert d.lignes[1].libelle == "Planche apéro" and d.lignes[1].prix_unitaire_centimes is None
    assert d.total_centimes == 30 * 3600
    dd = devis.devis_dict(session, d)
    assert any("Planche apéro" in m for m in dd["manques"])
    with pytest.raises(ErreurMetier) as e:
        devis.valider(session, acteur_admin, d.id)
    assert e.value.code == "prix_manquant"
    # Le prix est complété dans le menu Prix, puis le devis est actualisé.
    planche = session.scalars(select(Produit).where(Produit.nom == "Planche apéro",
                                                    Produit.categorie == "supplement")).one()
    catalogue.modifier_produit(session, acteur_admin, planche.id, {"prix": "4,31"})
    d, _ = devis.actualiser(session, acteur_admin, d.id)
    assert d.total_centimes == 30 * 3600 + 30 * 431
    devis.valider(session, acteur_admin, d.id)


def test_sharing_refuse_les_plats(session, acteur_admin):
    with pytest.raises(ErreurMetier) as e:
        creer_fiche(session, acteur_admin, couverts=12, formule_repas="Sharing",
                    lignes=[{"type": "plat", "libelle": "Steak", "quantite": 1}])
    assert e.value.code == "regle_metier"


def test_a_la_carte_compte_chaque_plat(session, acteur_admin):
    steak = catalogue.creer_produit(session, acteur_admin, {"nom": "Steak frites", "categorie": "plat", "prix": "24,50"})
    fiche, _ = creer_fiche(session, acteur_admin, couverts=4, formule_repas="À la carte", formule_boissons="à la carte",
                           lignes=[{"type": "plat", "libelle": "steak frites", "quantite": 3},
                                   {"type": "plat", "libelle": "Carpaccio", "quantite": 1}])
    assert fiche.formule_repas.nom == "À la carte"
    assert fiche.lignes[0].produit_id == steak.id and fiche.lignes[0].libelle == "Steak frites"
    d = total(session, acteur_admin, fiche)
    assert d.lignes[0].total_centimes == 7350
    assert d.lignes[1].prix_unitaire_centimes is None  # Carpaccio hors carte
    assert d.total_centimes == 7350


def test_devis_transmis_ne_change_plus(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, formule_repas="2 services")
    d = total(session, acteur_admin, fiche)
    devis.valider(session, acteur_admin, d.id)
    devis.transmettre(session, acteur_admin, d.id)
    assert d.pdf and d.pdf.startswith(b"%PDF")
    fiches.modifier(session, acteur_admin, fiche.id, {"couverts": 25})
    dd = devis.devis_dict(session, devis.obtenir(session, d.id))
    assert dd["a_mettre_a_jour"] and dd["total_centimes"] == 20 * (3200 + 1000)
    with pytest.raises(ErreurMetier):
        devis.preparer(session, acteur_admin, fiche.id)
    v2, _ = devis.nouvelle_version(session, acteur_admin, d.id)
    assert (v2.numero, v2.version, v2.couverts) == (d.numero, 2, 25)
    assert devis.obtenir(session, d.id).statut == "remplace"


def test_chatgpt_ne_valide_pas(session, acteur_admin, acteur_chatgpt):
    fiche, _ = creer_fiche(session, acteur_admin, formule_repas="2 services")
    d, _ = devis.preparer(session, acteur_chatgpt, fiche.id)
    with pytest.raises(ErreurMetier) as e:
        devis.valider(session, acteur_chatgpt, d.id)
    assert e.value.code == "interdit"
    with pytest.raises(ErreurMetier):
        catalogue.modifier_produit(session, acteur_chatgpt, d.lignes[0].produit_id, {"prix": "1"})


def test_annulation_en_deux_temps(session, acteur_admin, acteur_chatgpt):
    fiche, _ = creer_fiche(session, acteur_admin, formule_repas="2 services")
    with pytest.raises(ErreurMetier) as e:
        fiches.annuler(session, acteur_chatgpt, fiche.id, "client désiste")
    assert e.value.code == "confirmation_requise"
    jeton = e.value.details["jeton_confirmation"]
    with pytest.raises(ErreurMetier):
        fiches.annuler(session, acteur_chatgpt, fiche.id, "client désiste", "mauvais-jeton")
    fiches.annuler(session, acteur_chatgpt, fiche.id, "client désiste", jeton)
    assert fiches.obtenir(session, fiche.id).statut == "annulee"
    trace = session.scalars(select(Audit).where(Audit.action == "fiche.annuler")).one()
    assert trace.canal == "chatgpt"


def test_conflit_de_version_et_idempotence(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, formule_repas="2 services", cle_idempotence="abc")
    meme, alertes = fiches.creer(session, acteur_admin, {"cle_idempotence": "abc"})
    assert meme.id == fiche.id and alertes
    fiches.modifier(session, acteur_admin, fiche.id, {"couverts": 21}, version=1)
    with pytest.raises(ErreurMetier) as e:
        fiches.modifier(session, acteur_admin, fiche.id, {"couverts": 22}, version=1)
    assert e.value.code == "conflit_version"


def test_fiche_figee(session, acteur_admin, acteur_chatgpt):
    fiche, _ = creer_fiche(session, acteur_admin, formule_repas="2 services")
    fiches.changer_statut(session, acteur_admin, fiche.id, "confirmee")
    fiches.changer_statut(session, acteur_admin, fiche.id, "finale")
    with pytest.raises(ErreurMetier) as e:
        fiches.modifier(session, acteur_chatgpt, fiche.id, {"couverts": 5})
    assert e.value.code == "interdit"
    with pytest.raises(ErreurMetier):
        fiches.changer_statut(session, acteur_chatgpt, fiche.id, "confirmee")


def test_confirmer_demande_un_repas(session, acteur_admin):
    fiche, alertes = creer_fiche(session, acteur_admin)
    assert any("Ni formule" in a for a in alertes)
    with pytest.raises(ErreurMetier):
        fiches.changer_statut(session, acteur_admin, fiche.id, "confirmee")


def test_ajout_et_retrait_d_une_ligne(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, couverts=8)
    fiches.ajouter_ligne(session, acteur_admin, fiche.id, {"type": "plat", "libelle": "Steak", "quantite": 3})
    fiches.ajouter_ligne(session, acteur_admin, fiche.id, {"type": "plat", "libelle": "steak", "quantite": 5})
    f = fiches.obtenir(session, fiche.id)
    assert [(l.libelle, l.quantite) for l in f.lignes] == [("Steak", 5)]
    fiches.retirer_ligne(session, acteur_admin, fiche.id, "plat", "STEAK")
    assert fiches.obtenir(session, fiche.id).lignes == []


def test_formule_boissons_composee_dans_le_menu(session, acteur_admin):
    produits = {(p.categorie, p.nom): p for p in catalogue.lister_produits(session)}
    nouvelle = catalogue.enregistrer_formule_boissons(session, acteur_admin, {
        "nom": "avec alcool + cava (terrasse)", "mode": "formule",
        "base_produit_id": str(produits[("formule_boissons", "Formule avec alcool")].id),
        "coupe_produit_id": str(produits[("coupe", "Coupe de cava")].id)})
    assert catalogue.formule_boissons_dict(nouvelle)["prix_centimes"] == 2600
    with pytest.raises(ErreurMetier) as e:
        catalogue.enregistrer_formule_boissons(session, acteur_admin, {"nom": "Avec alcool", "mode": "formule"})
    assert e.value.code == "doublon_probable"


def test_fiche_modifiee_apres_validation(session, acteur_admin):
    fiche, _ = creer_fiche(session, acteur_admin, formule_repas="2 services")
    d = total(session, acteur_admin, fiche)
    devis.valider(session, acteur_admin, d.id)
    fiches.modifier(session, acteur_admin, fiche.id, {"couverts": 30})
    with pytest.raises(ErreurMetier):
        devis.transmettre(session, acteur_admin, d.id)
    d, _ = devis.actualiser(session, acteur_admin, d.id)
    assert d.statut == "brouillon" and d.couverts == 30
