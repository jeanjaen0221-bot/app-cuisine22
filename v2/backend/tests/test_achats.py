"""Boissons, fournisseurs, réassort et bons de commande."""
import io

import pytest
from pypdf import PdfReader

from albert.domain.erreurs import ErreurMetier
from albert.domain.import_boissons import lire_csv, lire_texte
from albert.services import achats


def test_lecture_d_une_carte_en_texte():
    carte = """B I E R E S
Bel Pils 25cl 3,50
Vedett IPA 33 cl 5.00
SOFTS
Coca-Cola 2.5 / 5
Bel Pils
"""
    assert lire_texte(carte) == [("Bel Pils", "bière"), ("Vedett IPA", "bière"), ("Coca-Cola", "soft")]
    assert lire_csv("nom;categorie\nOrval;bière\nSpa rouge;eau\n") == [("Orval", "bière"), ("Spa rouge", "eau")]


def _preparer(session, acteur):
    brasseur = achats.enregistrer_fournisseur(session, acteur, {"nom": "Brasserie du Coin", "email": "cmd@brasserie.be"})
    grossiste = achats.enregistrer_fournisseur(session, acteur, {"nom": "Grossiste"})
    pils = achats.enregistrer_boisson(session, acteur, {
        "nom": "Bel Pils", "unite": "fût", "stock_min": 2, "stock_max": 6, "colisage": 1,
        "fournisseurs": [{"fournisseur_id": str(brasseur.id), "prix_achat": "95,00", "reference": "BP-30", "prefere": True}]})
    coca = achats.enregistrer_boisson(session, acteur, {
        "nom": "Coca-Cola", "unite": "bouteille", "stock_min": 24, "stock_max": 72, "colisage": 24,
        "fournisseurs": [{"fournisseur_id": str(grossiste.id), "prix_achat": "0,62", "prefere": True}]})
    eau = achats.enregistrer_boisson(session, acteur, {"nom": "Spa", "stock_min": 10, "stock_max": 20})
    return brasseur, grossiste, pils, coca, eau


def test_reassort_et_bons_par_fournisseur(session, acteur_admin):
    brasseur, grossiste, pils, coca, eau = _preparer(session, acteur_admin)
    liste = {r["nom"]: r for r in achats.reassort(session, {str(pils.id): 1, str(coca.id): 30, str(eau.id): 5})}
    assert liste["Bel Pils"]["a_commander"] == 5 and liste["Bel Pils"]["sous_le_minimum"]
    assert liste["Coca-Cola"]["a_commander"] == 48  # 42 manquants, arrondi à 2 colis de 24
    assert liste["Spa"]["a_commander"] == 15 and liste["Spa"]["fournisseur"] is None
    bons = achats.bons_depuis_reassort(session, acteur_admin, {r["boisson_id"]: r["a_commander"] for r in liste.values()})
    par_fournisseur = {achats.bon_dict(b)["fournisseur"]: achats.bon_dict(b) for b in bons}
    assert set(par_fournisseur) == {"Brasserie du Coin", "Grossiste", None}
    biere = par_fournisseur["Brasserie du Coin"]
    assert biere["lignes"][0]["reference"] == "BP-30" and biere["total_achat_centimes"] == 5 * 9500
    assert par_fournisseur[None]["prix_manquants"]


def test_cycle_d_un_bon(session, acteur_admin, acteur_chatgpt):
    brasseur, _, pils, _, _ = _preparer(session, acteur_admin)
    bon = achats.creer_bon(session, acteur_chatgpt, str(brasseur.id), [{"nom": "bel pils", "quantite": 3}],
                           cle_idempotence="cmd-1")
    assert bon.statut == "brouillon" and bon.lignes[0].boisson_id == pils.id
    assert achats.creer_bon(session, acteur_chatgpt, str(brasseur.id), [{"nom": "bel pils", "quantite": 3}],
                            cle_idempotence="cmd-1").id == bon.id
    with pytest.raises(ErreurMetier):
        achats.changer_statut(session, acteur_chatgpt, bon.id, "envoye")  # jamais par ChatGPT
    achats.changer_statut(session, acteur_admin, bon.id, "envoye")
    with pytest.raises(ErreurMetier):
        achats.modifier_bon(session, acteur_admin, bon.id, {"note": "x"})
    achats.changer_statut(session, acteur_admin, bon.id, "recu")
    assert achats.obtenir_bon(session, bon.id).recu_le is not None


def test_api_achats(http_admin):
    f = http_admin.post("/api/achats/fournisseurs", json={"nom": "Brasserie", "email": "cmd@brasserie.be"}).json()
    assert http_admin.post("/api/achats/fournisseurs", json={"nom": "brasserie"}).status_code == 409
    carte = "BIERES\nOrval 33cl 6,50\nWestmalle Tripel 7\n".encode()
    r = http_admin.post("/api/achats/boissons/import", files={"fichier": ("carte.txt", carte, "text/plain")})
    assert r.json()["ajoutees"] == 2
    orval = next(b for b in http_admin.get("/api/achats/boissons").json() if b["nom"] == "Orval")
    http_admin.patch(f"/api/achats/boissons/{orval['id']}", json={
        "stock_max": 48, "colisage": 24, "fournisseurs": [{"fournisseur_id": f["id"], "prix_achat": "1,10", "prefere": True}]})
    reassort = http_admin.post("/api/achats/reassort", json={"restant": {orval["id"]: 10}}).json()
    assert next(r for r in reassort if r["nom"] == "Orval")["a_commander"] == 48
    bons = http_admin.post("/api/achats/reassort/commander", json={"quantites": {orval["id"]: 48}}).json()
    bon = bons[0]
    assert bon["fournisseur"] == "Brasserie" and bon["total_achat"] == "52,80 €"
    pdf = http_admin.get(f"/api/achats/commandes/{bon['id']}/pdf")
    assert "Orval" in PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    csv = http_admin.get(f"/api/achats/commandes/{bon['id']}/csv").text
    assert "Orval;" in csv and "1,10" in csv
    r = http_admin.post(f"/api/achats/commandes/{bon['id']}/statut", json={"statut": "recu"})
    assert r.status_code == 422  # il faut d'abord l'envoyer
