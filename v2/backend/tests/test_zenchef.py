"""Synchronisation Zenchef (API simulée)."""
from albert.models import Fiche
from albert.services import zenchef


def faux_zenchef(reservations):
    appels = []

    def appel(params):
        appels.append(params)
        return {"reservations": reservations}
    return appel, appels


RESAS = [
    {"id": 101, "startTime": "2030-06-01T19:30:00", "numberOfPeople": 14,
     "customer": {"firstname": "Anne", "lastname": "Martin", "email": "anne@exemple.be"}, "comment": "Anniversaire"},
    {"id": 102, "startTime": "2030-06-01T12:30:00", "numberOfPeople": 4, "customer": {"lastname": "Petit"}},
    {"id": 103, "startTime": "2030-06-02T20:00:00", "numberOfPeople": 25, "customer": {"company": "Volta"}},
    {"id": 104, "startTime": "2030-06-03T20:00:00", "numberOfPeople": 30, "status": "canceled", "customer": {}},
]


def test_import_des_groupes(session, acteur_admin):
    appel, appels = faux_zenchef(RESAS)
    r = zenchef.synchroniser(session, acteur_admin, "2030-06-01", "2030-06-30", appel=appel)
    assert [c["client"] for c in r["creees"]] == ["Anne Martin", "Volta"]
    assert r["ignorees"] == 2 and appels[0]["fromDate"] == "2030-06-01"
    fiche = session.query(Fiche).filter(Fiche.cle_idempotence == "zenchef:101").one()
    assert fiche.couverts == 14 and fiche.statut == "brouillon" and "Anniversaire" in fiche.notes_salle
    assert fiche.client.email == "anne@exemple.be"
    # Deuxième passage : rien n'est recréé, et le client existant est réutilisé.
    r = zenchef.synchroniser(session, acteur_admin, "2030-06-01", "2030-06-30", appel=appel)
    assert r["creees"] == [] and r["deja_importees"] == 2


def test_api_non_configure(http_admin, monkeypatch):
    monkeypatch.delenv("ZENCHEF_API_TOKEN", raising=False)
    assert http_admin.get("/api/zenchef").json() == {"configure": False}
    assert http_admin.post("/api/zenchef/synchroniser").status_code == 422
