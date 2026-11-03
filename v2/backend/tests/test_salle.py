"""Plan de salle : placement repris de l'ancienne version, fiches du jour, import PDF, PDF."""
import io
from datetime import time as dtime
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from albert.domain.erreurs import ErreurMetier
from albert.salle.placement import placer
from albert.services import fiches, salle

from .conftest import nouveau_client


def plan_test():
    """Le plan du script de test de l'ancienne version : 8 fixes, 2 rectangles, 1 ronde."""
    tables = [{"id": f"f{i}", "kind": "fixed", "x": 50 + 100 * (i // 4), "y": 50 + 100 * (i % 4), "w": 80, "h": 80,
               "capacity": 4} for i in range(8)]
    tables += [{"id": "t1", "kind": "rect", "x": 250, "y": 50, "w": 120, "h": 60, "capacity": 6},
               {"id": "t2", "kind": "rect", "x": 250, "y": 150, "w": 120, "h": 60, "capacity": 6},
               {"id": "rnd1", "kind": "round", "x": 450, "y": 150, "r": 50, "capacity": 10}]
    return {"room": {"width": 1600, "height": 1000, "grid": 50}, "tables": tables, "walls": [], "columns": [],
            "fixtures": [], "no_go": [], "round_only_zones": [],
            "rect_only_zones": [{"id": "zt", "x": 600, "y": 50, "w": 900, "h": 900}],
            "max_dynamic_tables": {"rect": 10, "round": 5}}


FIXES = {f"f{i}" for i in range(8)}


def _places(affect):
    places = {}
    for a in affect.values():
        places[a["res_id"]] = places.get(a["res_id"], 0) + a["pax"]
    return places


def test_placement_trente_reservations_respecte_le_stock():
    """Scénario du script de l'ancienne version : plus de groupes que de tables en stock."""
    plan = plan_test()
    tailles = [2, 2, 2, 3, 3, 4, 4, 4, 4, 4, 6, 6, 6, 6, 8, 8, 10, 10, 12, 12, 14, 14, 15, 15, 1, 1, 2, 3, 5, 7]
    resas = [SimpleNamespace(id=f"r{i}", client_name=f"Client {i}", pax=p, arrival_time=dtime(12, 0))
             for i, p in enumerate(tailles)]
    resultat = placer(plan, resas)
    dynamiques = [t for t in plan["tables"] if t.get("dynamic")]
    assert sum(1 for t in dynamiques if t["kind"] == "rect") <= 10 and sum(1 for t in dynamiques if t["kind"] == "round") <= 5
    places = _places(resultat["tables"])
    non_places = [r for r in resas if places.get(r.id, 0) < r.pax]
    assert non_places, "le stock de tables ne suffit pas : des réservations doivent rester à placer"
    assert any("non assignée" in a for a in resultat["alerts"])  # et l'équipe en est avertie
    assert all(a["pax"] <= 4 for t, a in resultat["tables"].items() if t in FIXES)


def test_placement_service_normal():
    plan = plan_test()
    tailles = [2, 2, 3, 4, 4, 6, 8, 12, 18]
    resas = [SimpleNamespace(id=f"r{i}", client_name=f"Client {i}", pax=p, arrival_time=dtime(19, 30))
             for i, p in enumerate(tailles)]
    resultat = placer(plan, resas)
    places = _places(resultat["tables"])
    assert all(places.get(r.id, 0) >= r.pax for r in resas)
    petits = {r.id for r in resas if r.pax <= 4}
    assert all(resultat["tables"][t]["res_id"] in petits for t in resultat["tables"] if t in FIXES)


def _fiche(session, acteur, nom, heure, couverts, **extra):
    client = nouveau_client(session, acteur, nom)
    f, _ = fiches.creer(session, acteur, {"client_id": str(client.id), "date": "2030-05-10", "heure": heure,
                                          "couverts": couverts, "formule_repas": "2 services", **extra})
    return f


def _pdf_reservations(lignes):
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4)
    tableau = Table([["Heure", "Pax", "Client", "Commentaire"]] + lignes)
    tableau.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))  # comme le PDF du service
    doc.build([tableau])
    return tampon.getvalue()


def test_service_avec_fiches_et_import(session, acteur_admin):
    plan = salle.plan_de_base(session)
    plan.donnees = plan_test()
    session.commit()
    groupe = _fiche(session, acteur_admin, "Volta SRL", "19:30", 18)
    _fiche(session, acteur_admin, "Déjeuner Dupont", "12:30", 6)  # midi : pas dans le service du soir
    _fiche(session, acteur_admin, "Rooftop Martin", "20:00", 10, espace="Rooftop")  # autre espace

    svc = salle.obtenir_service(session, "2030-05-10", "soir")
    d = salle.service_dict(session, svc)
    assert [r["nom"] for r in d["reservations"]] == ["Volta SRL"]

    pdf = _pdf_reservations([["19:00", "2", "MARTIN Paul", ""], ["19:30", "18", "VOLTA SRL", "groupe"],
                             ["20:00", "4", "DURAND Anne", ""], ["12:30", "2", "MIDI Jean", ""]])
    svc = salle.importer_pdf(session, acteur_admin, svc, pdf)
    d = salle.service_dict(session, svc)
    noms = {r["nom"]: r for r in d["reservations"]}
    assert set(noms) == {"Volta SRL", "MARTIN Paul", "VOLTA SRL", "DURAND Anne"}  # la ligne de midi est ignorée
    assert noms["VOLTA SRL"]["doublon_de"] == str(groupe.id)  # déjà une fiche : pas compté deux fois
    assert d["totaux"]["couverts"] == 18 + 2 + 4

    svc = salle.placement_automatique(session, acteur_admin, svc)
    d = salle.service_dict(session, svc)
    assert all(r["place"] for r in d["reservations"])
    tables = salle.tables_de_la_fiche(session, fiches.obtenir(session, groupe.id))
    assert tables and fiches.fiche_dict(session, fiches.obtenir(session, groupe.id))["tables_salle"] == tables

    # Relancer le placement ne multiplie pas les tables ajoutées.
    nb = len(svc.donnees["tables"])
    svc = salle.placement_automatique(session, acteur_admin, svc)
    assert len(svc.donnees["tables"]) == nb


def test_affectation_manuelle_et_fiche_annulee(session, acteur_admin):
    plan = salle.plan_de_base(session)
    plan.donnees = plan_test()
    session.commit()
    f = _fiche(session, acteur_admin, "Petit groupe", "19:00", 4)
    svc = salle.obtenir_service(session, "2030-05-10", "soir")
    svc = salle.affecter(session, acteur_admin, svc, "f3", str(f.id))
    assert svc.affectations["tables"]["f3"]["pax"] == 4
    with pytest.raises(ErreurMetier):
        salle.affecter(session, acteur_admin, svc, "inconnue", str(f.id))
    fiches.changer_statut(session, acteur_admin, f.id, "annulee", motif="désistement")
    d = salle.service_dict(session, svc)
    assert d["orphelines"] and any("n'existe plus" in a for a in d["alertes"])
    svc = salle.affecter(session, acteur_admin, svc, "f3", None)
    assert "f3" not in svc.affectations["tables"]


def test_api_plan_et_pdf(http_admin):
    r = http_admin.put("/api/salle/plan", json={"donnees": plan_test()})
    assert r.status_code == 200
    r = http_admin.post("/api/salle/plan/numeroter")
    assert r.json()["etiquettes"]["f3"] == "1" and r.json()["etiquettes"]["t1"].startswith("T")
    assert http_admin.put("/api/salle/plan", json={"donnees": {"tables": "non"}}).status_code == 422
    pdf = http_admin.get("/api/salle/plan/pdf")
    assert pdf.status_code == 200 and len(PdfReader(io.BytesIO(pdf.content)).pages) == 2

    svc = http_admin.post("/api/salle/services", json={"date": "10/05/2030", "service": "dinner"}).json()
    assert svc["service"] == "soir"
    r = http_admin.post(f"/api/salle/services/{svc['id']}/placement-auto")
    assert r.status_code == 422  # aucune réservation
    contenu = _pdf_reservations([["19:00", "2", "MARTIN Paul", ""], ["20:00", "4", "DURAND Anne", ""]])
    r = http_admin.post(f"/api/salle/services/{svc['id']}/import-pdf",
                        files={"fichier": ("resa.pdf", contenu, "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["totaux"]["importees"] == 2
    r = http_admin.post(f"/api/salle/services/{svc['id']}/placement-auto")
    assert r.status_code == 200 and r.json()["totaux"]["placees"] == 2
    pdf = http_admin.get(f"/api/salle/services/{svc['id']}/pdf")
    texte = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert "MARTIN PAUL" in texte
    annote = http_admin.post(f"/api/salle/services/{svc['id']}/pdf-annote",
                             files={"fichier": ("resa.pdf", contenu, "application/pdf")})
    assert annote.status_code == 200 and len(PdfReader(io.BytesIO(annote.content)).pages) == 3
    pas_pdf = http_admin.post(f"/api/salle/services/{svc['id']}/import-pdf",
                              files={"fichier": ("x.pdf", b"bonjour", "application/pdf")})
    assert pas_pdf.status_code == 422


def test_compta_sans_acces_au_plan(http_compta):
    assert http_compta.get("/api/salle/plan").status_code == 403
