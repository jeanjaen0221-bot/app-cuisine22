"""Parcours complet par l'API du site, et droits d'accès."""
from fastapi.testclient import TestClient
from pypdf import PdfReader
import io

from albert.main import creer_app


def _client(http, nom="Volta SRL", **extra):
    r = http.post("/api/clients", json={"type": "entreprise", "nom": nom, "email": "events@volta.be",
                                        "rue": "Rue Haute", "numero": "12", "code_postal": "1000",
                                        "ville": "Bruxelles", "tva": "BE0123456749", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_premier_compte_puis_connexion(session):
    http = TestClient(creer_app(avec_mcp=False))
    http.headers["X-Albert"] = "1"
    assert http.get("/api/auth/etat").json() == {"configuration_requise": True}
    r = http.post("/api/auth/configuration", json={"email": "patron@albert.be", "mot_de_passe": "court"})
    assert r.status_code == 422
    r = http.post("/api/auth/configuration", json={"email": "patron@albert.be", "mot_de_passe": "x" * 12})
    assert r.status_code == 200 and "albert_session" in r.cookies
    assert http.get("/api/auth/moi").json()["role"] == "admin"
    assert http.post("/api/auth/configuration", json={"email": "b@b.be", "mot_de_passe": "y" * 12}).status_code == 403


def test_connexion_limitee(session, admin):
    http = TestClient(creer_app(avec_mcp=False))
    http.headers["X-Albert"] = "1"
    for _ in range(5):
        assert http.post("/api/auth/connexion", json={"email": admin.email, "mot_de_passe": "faux"}).status_code == 401
    r = http.post("/api/auth/connexion", json={"email": admin.email, "mot_de_passe": "mot-de-passe-solide"})
    assert r.status_code == 403  # trop de tentatives


def test_entete_anti_csrf_obligatoire(http_admin):
    del http_admin.headers["X-Albert"]
    r = http_admin.post("/api/clients", json={"nom": "X", "email": "x@x.be"})
    assert r.status_code == 403


def test_non_connecte(session):
    http = TestClient(creer_app(avec_mcp=False))
    r = http.get("/api/fiches")
    assert r.status_code == 401 and r.json()["erreur"]["code"] == "non_connecte"


def test_doublon_client(http_admin):
    _client(http_admin)
    r = http_admin.post("/api/clients", json={"type": "entreprise", "nom": "VOLTA s.r.l.", "telephone": "02 000 00 00"})
    assert r.status_code == 409
    assert r.json()["erreur"]["code"] == "doublon_probable"
    r = http_admin.post("/api/clients", json={"type": "entreprise", "nom": "VOLTA s.r.l.", "telephone": "02",
                                              "confirmer_doublon": True})
    assert r.status_code == 201


def test_parcours_complet_jusqu_a_la_compta(http_admin, http_compta):
    client = _client(http_admin)
    r = http_admin.post("/api/fiches", json={
        "client_id": client["id"], "date": "17/09/2030", "heure": "19h30", "couverts": 20,
        "formule_repas": "3 Services", "formule_boissons": "avec alcool + champagne", "privatisation": "City",
        "allergenes": ["lactose"], "notes_salle": "## Anniversaire\n* gâteau à 22h",
    })
    assert r.status_code == 422  # « City » n'est pas le nom exact
    assert "Privatisation City" in r.json()["erreur"]["valeurs_permises"]
    r = http_admin.post("/api/fiches", json={
        "client_id": client["id"], "date": "17/09/2030", "heure": "19h30", "couverts": 20,
        "formule_repas": "3 Services", "formule_boissons": "avec alcool + champagne",
        "privatisation": "Privatisation City", "allergenes": ["lactose"],
        "notes_salle": "## Anniversaire\n* gâteau à 22h", "espace": "city",
    })
    assert r.status_code == 201, r.text
    fiche = r.json()
    assert fiche["formule_repas"] == "3 services" and fiche["allergenes"] == ["lait"]
    assert fiche["notes_salle"] == "Anniversaire\n- gâteau à 22h" and fiche["espace"] == "City"

    pdf = http_admin.get(f"/api/fiches/{fiche['id']}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert len(PdfReader(io.BytesIO(pdf.content)).pages) == 2  # salle + cuisine (pas de desserts listés)

    d = http_admin.post(f"/api/fiches/{fiche['id']}/devis").json()
    assert d["total_centimes"] == 20 * (4000 + 2000 + 1100) + 60000
    for action in ("valider", "transmettre"):
        r = http_admin.post(f"/api/devis/{d['id']}/{action}")
        assert r.status_code == 200, r.text

    # La compta voit le devis à envoyer, le marque envoyé puis accepté.
    compta = http_compta.get("/api/compta").json()
    assert [x["id"] for x in compta["a_envoyer"]] == [d["id"]]
    texte = PdfReader(io.BytesIO(http_compta.get(f"/api/devis/{d['id']}/pdf").content)).pages[0].extract_text()
    assert "Volta SRL" in texte and "TVA comprise" in texte and "2 020,00" in texte.replace(" ", " ")
    assert http_compta.post(f"/api/devis/{d['id']}/envoye").status_code == 200
    assert http_compta.post(f"/api/devis/{d['id']}/accepte").status_code == 200

    # Après l'événement : 22 couverts réels et 3 bouteilles de champagne en plus.
    champagne = http_admin.post("/api/produits", json={"nom": "Bouteille de champagne", "categorie": "supplement",
                                                       "unite": "bouteille", "prix": "65"}).json()
    bon = http_admin.post(f"/api/devis/{d['id']}/bon", json={
        "couverts_reels": 22, "extras": [{"nom": "bouteille de champagne", "quantite": 3}]}).json()
    assert bon["couverts_reels"] == 22
    assert bon["total_centimes"] == 22 * (4000 + 2000 + 1100) + 60000 + 3 * 6500
    assert bon["ecart_centimes"] == 2 * 7100 + 3 * 6500
    assert [l["libelle"] for l in bon["lignes"] if l["extra"]] == [champagne["nom"]]
    for action in ("valider", "transmettre"):
        assert http_admin.post(f"/api/bons/{bon['id']}/{action}").status_code == 200
    assert [b["id"] for b in http_compta.get("/api/compta").json()["a_facturer"]] == [bon["id"]]
    r = http_compta.post(f"/api/bons/{bon['id']}/facture", json={"numero_facture": "F2030-118"})
    assert r.json()["statut"] == "facture" and r.json()["numero_facture_compta"] == "F2030-118"

    journal = http_admin.get("/api/journal").json()
    actions = {j["action"] for j in journal}
    assert {"fiche.creer", "devis.transmettre", "devis.envoye", "bon.facture"} <= actions


def test_droits_par_role(http_admin, http_equipe, http_compta):
    client = _client(http_admin)
    assert http_compta.get("/api/fiches").status_code == 403
    assert http_compta.post("/api/fiches", json={"client_id": client["id"]}).status_code == 403
    produit = http_admin.get("/api/produits", params={"categorie": "formule_repas"}).json()[0]
    assert http_equipe.patch(f"/api/produits/{produit['id']}", json={"prix": "1"}).status_code == 403
    assert http_equipe.get("/api/utilisateurs").status_code == 403
    assert http_equipe.get("/api/journal").status_code == 403
    # L'équipe prépare, valide et transmet ; seule la compta (ou un admin) marque « envoyé ».
    fiche = http_equipe.post("/api/fiches", json={"client_id": client["id"], "date": "2030-01-10", "heure": "12:00",
                                                  "couverts": 8, "formule_repas": "1 service"}).json()
    d = http_equipe.post(f"/api/fiches/{fiche['id']}/devis").json()
    assert http_compta.get(f"/api/devis/{d['id']}").status_code == 403  # pas encore transmis
    http_equipe.post(f"/api/devis/{d['id']}/valider")
    http_equipe.post(f"/api/devis/{d['id']}/transmettre")
    assert http_equipe.post(f"/api/devis/{d['id']}/envoye").status_code == 403
    assert http_compta.get(f"/api/devis/{d['id']}").status_code == 200


def test_menu_prix(http_admin):
    manquants = http_admin.get("/api/produits", params={"manquants": True}).json()
    assert {p["nom"] for p in manquants} == {"Semi-privatisation", "Privatisation complète", "Planche apéro"}
    assert http_admin.get("/api/produits/manquants").json() == {"nombre": 3}
    semi = next(p for p in manquants if p["nom"] == "Semi-privatisation")
    r = http_admin.patch(f"/api/produits/{semi['id']}", json={"prix": "350,00"})
    assert r.json()["prix_centimes"] == 35000
    assert http_admin.get("/api/produits/manquants").json() == {"nombre": 2}
    assert http_admin.patch(f"/api/produits/{semi['id']}", json={"prix": "trois cents"}).status_code == 422


def test_menu_formules(http_admin):
    formules = http_admin.get("/api/formules").json()
    assert [f["nom"] for f in formules["repas"]] == ["1 service", "2 services", "3 services", "Sharing", "Brunch",
                                                     "À la carte"]
    cava = next(f for f in formules["boissons"] if f["nom"] == "avec alcool + cava")
    assert cava["prix_centimes"] == 2600
    # Une nouvelle formule repas crée sa ligne dans le menu Prix, à compléter.
    r = http_admin.post("/api/formules/repas", json={"nom": "Walking dinner", "comportement": "sans_plats"})
    assert r.status_code == 201 and r.json()["prix"] == "prix manquant"
    refs = http_admin.get("/api/references").json()
    assert "Walking dinner" in [f["nom"] for f in refs["formules_repas"]]
    # Désactivée : elle disparaît des choix de la fiche.
    http_admin.patch(f"/api/formules/repas/{r.json()['id']}", json={"actif": False})
    refs = http_admin.get("/api/references").json()
    assert "Walking dinner" not in [f["nom"] for f in refs["formules_repas"]]


def test_texte_special_dans_le_pdf(http_admin):
    client = _client(http_admin, nom="Dupont & Fils <SA>", email="d@f.be")
    fiche = http_admin.post("/api/fiches", json={
        "client_id": client["id"], "date": "2030-02-02", "heure": "20:00", "couverts": 4,
        "lignes": [{"type": "plat", "libelle": "Steak <saignant>", "quantite": 2, "commentaire": "sans sel & poivre"}],
    }).json()
    pdf = http_admin.get(f"/api/fiches/{fiche['id']}/pdf", params={"variante": "salle"})
    texte = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert "Dupont & Fils <SA>" in texte and "Steak <saignant>" in texte and "sans sel & poivre" in texte
    assert "&" not in pdf.headers["content-disposition"].split("filename=")[1]
