"""Connecteur ChatGPT (MCP) de bout en bout : enregistrement OAuth, connexion, outils, droits."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from albert.config import reglages
from albert.models import Audit, ConnexionChatGPT
from sqlalchemy import select

from .conftest import MOT_DE_PASSE

BASE = "http://localhost"
REDIRECTION = "https://chatgpt.com/connector_platform_oauth_redirect"


@pytest.fixture(scope="module")
def _client_mcp():
    # Le gestionnaire de sessions MCP ne démarre qu'une fois par processus : un seul client pour le module.
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from albert.db import Base, FabriqueSession
    from albert.main import app

    assert reglages.url_publique == BASE  # fixé dans conftest : l'émetteur OAuth doit être HTTPS ou localhost
    moteur = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(moteur)
    FabriqueSession.configure(bind=moteur)
    with TestClient(app, base_url=BASE) as client:
        yield client


@pytest.fixture()
def app_mcp(session, _client_mcp):
    return _client_mcp


def _pkce():
    verificateur = secrets.token_urlsafe(48)
    defi = base64.urlsafe_b64encode(hashlib.sha256(verificateur.encode()).digest()).rstrip(b"=").decode()
    return verificateur, defi


def connecter(http: TestClient, email: str, scopes: list[str], coches: list[str] | None = None) -> tuple[str, str]:
    client = http.post("/mcp/register", json={
        "redirect_uris": [REDIRECTION], "client_name": "ChatGPT", "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "scope": " ".join(scopes)}).json()
    verificateur, defi = _pkce()
    r = http.get("/mcp/authorize", params={
        "response_type": "code", "client_id": client["client_id"], "redirect_uri": REDIRECTION,
        "code_challenge": defi, "code_challenge_method": "S256", "state": "etat123", "scope": " ".join(scopes),
        "resource": f"{BASE}/mcp"}, follow_redirects=False)
    assert r.status_code == 302, r.text
    page = r.headers["location"]
    demande = parse_qs(urlsplit(page).query)["demande"][0]
    assert "Autoriser ChatGPT" in http.get(page).text
    r = http.post("/mcp/connexion", data={"demande": demande, "email": email, "mot_de_passe": MOT_DE_PASSE,
                                          "scope": coches if coches is not None else scopes},
                  follow_redirects=False)
    assert r.status_code == 302, r.text
    retour = parse_qs(urlsplit(r.headers["location"]).query)
    assert retour["state"] == ["etat123"]
    jetons = http.post("/mcp/token", data={
        "grant_type": "authorization_code", "code": retour["code"][0], "redirect_uri": REDIRECTION,
        "client_id": client["client_id"], "code_verifier": verificateur, "resource": f"{BASE}/mcp"}).json()
    assert "access_token" in jetons, jetons
    return jetons["access_token"], client["client_id"]


class Mcp:
    def __init__(self, http: TestClient, jeton: str):
        self.http, self.n = http, 0
        self.entetes = {"Authorization": f"Bearer {jeton}", "Accept": "application/json, text/event-stream"}
        r = self._envoyer("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                         "clientInfo": {"name": "test", "version": "1"}})
        assert r.status_code == 200, r.text
        if r.headers.get("mcp-session-id"):
            self.entetes["mcp-session-id"] = r.headers["mcp-session-id"]
        self.consignes = r.json()["result"].get("instructions", "")
        self.http.post("/mcp/", headers=self.entetes, json={"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _envoyer(self, methode: str, params: dict):
        self.n += 1
        return self.http.post("/mcp/", headers=self.entetes,
                              json={"jsonrpc": "2.0", "id": self.n, "method": methode, "params": params})

    def outils(self) -> list[str]:
        return [o["name"] for o in self._envoyer("tools/list", {}).json()["result"]["tools"]]

    def appeler(self, outil: str, **arguments) -> dict:
        r = self._envoyer("tools/call", {"name": outil, "arguments": arguments})
        assert r.status_code == 200, r.text
        resultat = r.json()["result"]
        if resultat.get("structuredContent") is not None:
            contenu = resultat["structuredContent"]
            return contenu.get("result", contenu)
        return json.loads(resultat["content"][0]["text"])


def test_sans_jeton_refuse(app_mcp):
    r = app_mcp.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401


def test_parcours_chatgpt(app_mcp, admin, session):
    jeton, _ = connecter(app_mcp, admin.email, ["lecture", "fiches:ecrire", "devis:preparer"])
    mcp = Mcp(app_mcp, jeton)
    assert "TVA comprise" in mcp.consignes
    outils = mcp.outils()
    assert {"fiche_creer", "devis_preparer", "fiche_annuler", "pdf_lien"} <= set(outils)
    assert not any(n.startswith(("devis_valider", "devis_transmettre", "produit", "fiche_supprimer")) for n in outils)

    refs = mcp.appeler("references_lister")
    assert "Privatisation City" in [p["nom"] for p in refs["privatisations"]]

    client = mcp.appeler("client_creer", nom="Volta", type="entreprise", email="events@volta.be")["client"]
    doublon = mcp.appeler("client_creer", nom="VOLTA SRL", type="entreprise", telephone="02")
    assert doublon["ok"] is False and doublon["erreur"]["code"] == "doublon_probable"

    manque = mcp.appeler("fiche_creer", client_id=client["id"], date="2030-09-17", heure="", couverts=20,
                         cle_idempotence="essai-1")
    assert manque["erreur"]["code"] == "champ_obligatoire"

    fiche = mcp.appeler("fiche_creer", client_id=client["id"], date="17/09/2030", heure="19h30", couverts=20,
                        formule_repas="3 services", formule_boissons="avec alcool + cava",
                        privatisation="Privatisation City", allergenes=["lactose"], cle_idempotence="essai-2")["fiche"]
    assert fiche["statut"] == "brouillon" and fiche["allergenes"] == ["lait"]
    meme = mcp.appeler("fiche_creer", client_id=client["id"], date="2030-09-17", heure="19:30", couverts=20,
                       cle_idempotence="essai-2")["fiche"]
    assert meme["id"] == fiche["id"]

    devis = mcp.appeler("devis_preparer", fiche_id=fiche["id"])["devis"]
    assert devis["total_centimes"] == 192000 and devis["statut"] == "brouillon"
    assert devis["lien_pdf"].startswith(f"{BASE}/api/pdf/")
    pdf = app_mcp.get(devis["lien_pdf"].removeprefix(BASE))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # Ajouter un plat : les plats prévalent, la formule est retrouvée au devis.
    modif = mcp.appeler("fiche_ligne_ajouter", fiche_id=fiche["id"], version=fiche["version"], type="plat",
                        libelle="Steak", quantite=20)["fiche"]
    assert modif["formule_repas"] is None
    perime = mcp.appeler("fiche_ligne_ajouter", fiche_id=fiche["id"], version=fiche["version"], type="plat",
                         libelle="Poisson", quantite=2)
    assert perime["erreur"]["code"] == "conflit_version"

    annule = mcp.appeler("fiche_annuler", fiche_id=fiche["id"], motif="essai")
    assert annule["erreur"]["code"] == "confirmation_requise"
    jeton_conf = annule["erreur"]["details"]["jeton_confirmation"]
    assert mcp.appeler("fiche_annuler", fiche_id=fiche["id"], motif="essai",
                       jeton_confirmation=jeton_conf)["fiche"]["statut"] == "annulee"

    canaux = {a.canal for a in session.scalars(select(Audit).where(Audit.objet_type == "fiche"))}
    assert canaux == {"chatgpt"}


def test_droits_choisis_a_la_connexion(app_mcp, admin):
    jeton, _ = connecter(app_mcp, admin.email, ["lecture", "fiches:ecrire", "devis:preparer"], coches=["lecture"])
    mcp = Mcp(app_mcp, jeton)
    refus = mcp.appeler("client_creer", nom="X", email="x@x.be")
    assert refus["ok"] is False and refus["erreur"]["code"] == "interdit"
    assert mcp.appeler("references_lister")["ok"] is True


def test_revocation_immediate(app_mcp, admin, session):
    jeton, _ = connecter(app_mcp, admin.email, ["lecture"])
    mcp = Mcp(app_mcp, jeton)
    connexion = session.scalars(select(ConnexionChatGPT)).one()
    connexion.revoquee = True
    session.commit()
    r = app_mcp.post("/mcp/", headers=mcp.entetes, json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"})
    assert r.status_code == 401


def test_compte_sans_droit_chatgpt(app_mcp, session):
    from .conftest import _utilisateur

    _utilisateur(session, "serveur@albert.test", "equipe")
    with pytest.raises(AssertionError):
        connecter(app_mcp, "serveur@albert.test", ["lecture"])
