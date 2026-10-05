"""The GPT API must produce fiches identical to a manual entry in ReservationForm.tsx.

Run from the repository root:  python -m pytest app/backend/tests
"""
import hashlib
import os
import tempfile

_DB = os.path.join(tempfile.mkdtemp(), "gpt_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["GPT_API_KEY_HASH"] = hashlib.sha256(b"test-key").hexdigest()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app.backend.database import engine  # noqa: E402
from app.backend.gpt_api import gpt_app  # noqa: E402
from app.backend.models import MenuItem  # noqa: E402

AUTH = {"Authorization": "Bearer test-key"}


@event.listens_for(engine, "connect")
def _sqlite_foreign_keys(dbapi_conn, _record):
    # Production runs on PostgreSQL, which always enforces foreign keys.
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


@pytest.fixture(autouse=True)
def fresh_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MenuItem(name="Carpaccio de boeuf", type="entrée"))
        s.add(MenuItem(name="Filet de bar", type="plat"))
        s.add(MenuItem(name="Tiramisu", type="dessert"))
        s.commit()
    yield


@pytest.fixture
def client():
    return TestClient(gpt_app)


def fiche(**overrides):
    base = {"client_name": "Dupont", "pax": 12, "service_date": "2030-09-17", "arrival_time": "19:30", "menu_formula": "3 services"}
    base.update(overrides)
    return base


def create(client, **overrides):
    r = client.post("/fiches", json=fiche(**overrides), headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize("missing", ["client_name", "service_date", "arrival_time", "pax"])
def test_required_fields_are_not_guessed(client, missing):
    body = fiche()
    del body[missing]
    assert client.post("/fiches", json=body, headers=AUTH).status_code == 422


def test_french_date_and_time_formats(client):
    f = create(client, service_date="17/09/2030", arrival_time="19h30")
    assert f["service_date"] == "2030-09-17"
    assert f["arrival_time"] == "19:30:00"


def test_formulas_are_normalized_to_form_values(client):
    f = create(client, menu_formula="3 Services", drink_formula="Avec Alcool + Champagne")
    assert f["menu_formula"] == "3 services"
    assert f["drink_formula"] == "avec alcool + champ"


def test_default_drink_formula_matches_form(client):
    assert create(client)["drink_formula"] == "sans alcool"


def test_unknown_formula_is_rejected_with_choices(client):
    r = client.post("/fiches", json=fiche(drink_formula="forfait vin maison"), headers=AUTH)
    assert r.status_code == 422
    assert "sans alcool" in r.text


def test_item_types_and_catalogue_spelling(client):
    f = create(client, menu_formula="", items=[
        {"type": "Main course", "name": "filet DE bar", "quantity": 12},
        {"type": "Starter", "name": "carpaccio de bœuf", "quantity": 12},
    ])
    got = {(i["type"], i["name"]) for i in f["items"]}
    assert got == {("plat", "Filet de bar"), ("entrée", "Carpaccio de boeuf")}


def test_dishes_win_over_formula(client):
    f = create(client, menu_formula="3 services", items=[{"type": "plat", "name": "Filet de bar", "quantity": 12}])
    assert f["menu_formula"] == ""


def test_empty_fiche_is_rejected(client):
    r = client.post("/fiches", json=fiche(menu_formula=""), headers=AUTH)
    assert r.status_code == 422


def test_brunch_rejects_dishes(client):
    r = client.post("/fiches", json=fiche(menu_formula="Brunch", items=[{"type": "entrée", "name": "Carpaccio de boeuf", "quantity": 2}]), headers=AUTH)
    assert r.status_code == 422
    f = create(client, menu_formula="Brunch", items=[{"type": "extra", "name": "Champagne", "quantity": 1}])
    assert f["menu_formula"] == "Brunch"
    assert f["items"][0]["type"] == "supplément"


def test_allergens_become_keys(client):
    f = create(client, allergens=["lactose", "Gluten", "sans fruits à coque"])
    assert f["allergens"] == "lait,gluten,fruits_a_coque"
    r = client.post("/fiches", json=fiche(allergens=["piment"]), headers=AUTH)
    assert r.status_code == 422
    assert "Clés permises" in r.text


def test_status_and_final_version_cannot_be_set(client):
    f = create(client, status="confirmed", final_version=True, company="ACME")
    assert f["status"] == "draft"
    assert f["final_version"] is False
    assert f["company"] is None
    fid = f["id"]
    r = client.patch(f"/fiches/{fid}", json={"status": "printed"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "draft"


def test_markdown_notes_are_cleaned(client):
    f = create(client, notes="## Infos\n* **Anniversaire**\n* Société ACME")
    assert f["notes"] == "Infos\n- **Anniversaire**\n- Société ACME"


def test_patch_date_is_applied_or_rejected_never_ignored(client):
    fid = create(client)["id"]
    r = client.patch(f"/fiches/{fid}", json={"service_date": "18/09/2030", "arrival_time": "20h"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["service_date"] == "2030-09-18"
    assert r.json()["arrival_time"] == "20:00:00"
    assert client.patch(f"/fiches/{fid}", json={"service_date": "jeudi prochain"}, headers=AUTH).status_code == 422


def test_patch_notes_only_keeps_items(client):
    fid = create(client, menu_formula="", items=[{"type": "plat", "name": "Filet de bar", "quantity": 12}])["id"]
    r = client.patch(f"/fiches/{fid}", json={"notes": "Table près de la fenêtre"}, headers=AUTH)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_add_and_remove_single_item(client):
    fid = create(client, menu_formula="", items=[{"type": "plat", "name": "Filet de bar", "quantity": 10}])["id"]
    r = client.post(f"/fiches/{fid}/items", json={"type": "dessert", "name": "tiramisu", "quantity": 12}, headers=AUTH)
    assert r.status_code == 200
    names = {i["name"]: i["quantity"] for i in r.json()["items"]}
    assert names == {"Filet de bar": 10, "Tiramisu": 12}
    r = client.post(f"/fiches/{fid}/items", json={"type": "plat", "name": "Filet de bar", "quantity": 12}, headers=AUTH)
    assert {i["name"]: i["quantity"] for i in r.json()["items"]} == {"Filet de bar": 12, "Tiramisu": 12}
    r = client.delete(f"/fiches/{fid}/items", params={"type": "dessert", "name": "Tiramisu"}, headers=AUTH)
    assert r.status_code == 200
    assert [i["name"] for i in r.json()["items"]] == ["Filet de bar"]


def test_per_type_total_still_limited_to_pax(client):
    fid = create(client)["id"]
    r = client.post(f"/fiches/{fid}/items", json={"type": "plat", "name": "Filet de bar", "quantity": 13}, headers=AUTH)
    assert r.status_code == 422


def test_duplicate_slot_gives_409(client):
    create(client)
    assert client.post("/fiches", json=fiche(), headers=AUTH).status_code == 409


def test_billing_defaults_match_form(client):
    fid = create(client)["id"]
    r = client.put(f"/fiches/{fid}/billing", json={"company_name": "ACME", "address_line1": "Rue 1", "zip_code": "1000", "city": "Bruxelles"}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["payment_terms"] == "Paiement à 30 jours"
    assert r.json()["country"] == "Belgique"


def test_openapi_exposes_choice_lists(client):
    schema = client.get("/openapi.json", headers=AUTH).json()
    create_schema = schema["components"]["schemas"]["GptFicheCreate"]["properties"]
    assert "sans alcool" in create_schema["drink_formula"]["enum"]
    assert "status" not in create_schema


def test_delete_fiche_with_billing(client):
    fid = create(client)["id"]
    client.put(f"/fiches/{fid}/billing", json={"company_name": "ACME", "address_line1": "Rue 1", "zip_code": "1000", "city": "Bruxelles"}, headers=AUTH)
    assert client.delete(f"/fiches/{fid}", headers=AUTH).status_code == 200
    assert client.get(f"/fiches/{fid}", headers=AUTH).status_code == 404


def test_menu_search_ignores_accents_and_word_order(client):
    r = client.get("/menu-items/search", params={"q": "BŒUF carpaccio"}, headers=AUTH)
    assert [i["name"] for i in r.json()] == ["Carpaccio de boeuf"]
    r = client.get("/menu-items/search", params={"type": "Desserts"}, headers=AUTH)
    assert [i["name"] for i in r.json()] == ["Tiramisu"]
