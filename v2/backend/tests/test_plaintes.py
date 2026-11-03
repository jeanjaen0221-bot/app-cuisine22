"""Plaintes et notes."""
import io

import pytest
from pypdf import PdfReader

from albert.domain.erreurs import ErreurMetier
from albert.services import fiches, plaintes

from .conftest import nouveau_client


def test_plainte_rattachee_a_la_fiche(session, acteur_admin):
    client = nouveau_client(session, acteur_admin, "Volta SRL")
    fiche, _ = fiches.creer(session, acteur_admin, {"client_id": str(client.id), "date": "2030-02-02", "heure": "20:00",
                                                    "couverts": 12, "formule_repas": "3 services"})
    p = plaintes.creer(session, acteur_admin, {"date": "02/02/2030", "heure": "21h15", "recit_brut": "Plat servi froid.",
                                               "fiche_id": str(fiche.id), "gravite": "Moyenne"})
    assert p.client_id == client.id and p.gravite == "moyen" and p.statut == "ouverte"
    assert plaintes.plainte_dict(p)["client_nom"] == "Volta SRL"
    with pytest.raises(ErreurMetier):
        plaintes.creer(session, acteur_admin, {"date": "2030-02-02"})  # rien de décrit


def test_chatgpt_redige_en_brouillon(session, acteur_admin, acteur_chatgpt):
    p = plaintes.creer(session, acteur_chatgpt, {"recit_brut": "Le client attendait depuis 40 minutes.",
                                                 "heure": "Non précisé", "statut": "traitee"})
    assert p.statut == "brouillon" and p.heure is None
    plaintes.modifier(session, acteur_chatgpt, p.id, {"description": "Attente de 40 minutes."})
    plaintes.modifier(session, acteur_admin, p.id, {"statut": "ouverte"})
    with pytest.raises(ErreurMetier) as e:
        plaintes.modifier(session, acteur_chatgpt, p.id, {"description": "autre"})
    assert e.value.code == "interdit"
    with pytest.raises(ErreurMetier):
        plaintes.supprimer(session, acteur_chatgpt, p.id)


def test_api_plaintes_et_notes(http_admin, http_equipe):
    p = http_equipe.post("/api/plaintes", json={"date": "2030-03-03", "recit_brut": "Bruit <fort> & musique",
                                                "client_nom": "Dupont"}).json()
    pdf = http_equipe.get(f"/api/plaintes/{p['id']}/pdf")
    assert "Bruit <fort> & musique" in PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert [x["id"] for x in http_equipe.get("/api/plaintes", params={"q": "dupont"}).json()] == [p["id"]]
    assert http_equipe.delete(f"/api/plaintes/{p['id']}").status_code == 403  # suppression : admin seulement
    assert http_admin.delete(f"/api/plaintes/{p['id']}").status_code == 200

    n = http_equipe.post("/api/notes", json={"contenu": "Livraison de vin demain 9h"}).json()
    assert n["auteur"] == "equipe@albert.test"
    http_equipe.patch(f"/api/notes/{n['id']}", json={"epinglee": True})
    assert http_equipe.get("/api/notes").json()[0]["epinglee"] is True
    assert http_equipe.post("/api/notes", json={"contenu": "  "}).status_code == 422
