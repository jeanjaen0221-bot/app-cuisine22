from __future__ import annotations

import os
import uuid

os.environ.setdefault("SECRET_KEY", "secret-de-test-" + "x" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ["PUBLIC_BASE_URL"] = "http://localhost"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from albert import db, models  # noqa: F401
from albert.db import Base, FabriqueSession
from albert.main import creer_app
from albert.services import comptes
from albert.services.contexte import Acteur
from albert.services.initialisation import initialiser_catalogue

MOT_DE_PASSE = "mot-de-passe-solide"


@pytest.fixture()
def session():
    from sqlalchemy import create_engine, event

    moteur = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(moteur, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    db.moteur = moteur
    FabriqueSession.configure(bind=moteur)
    Base.metadata.create_all(moteur)
    s = FabriqueSession()
    initialiser_catalogue(s)
    comptes._echecs.clear()
    yield s
    s.close()
    Base.metadata.drop_all(moteur)


def _utilisateur(session, email: str, role: str, droits=None):
    from albert.models import Utilisateur

    u = Utilisateur(email=email, role=role, droits=droits or [], mot_de_passe=comptes.hacher(MOT_DE_PASSE))
    session.add(u)
    session.commit()
    return u


@pytest.fixture()
def admin(session):
    return _utilisateur(session, "admin@albert.test", "admin")


@pytest.fixture()
def acteur_admin(admin):
    return comptes.acteur_de(admin)


@pytest.fixture()
def acteur_chatgpt(admin):
    return comptes.acteur_de(admin, canal="chatgpt")


def _connecte(session, email: str) -> TestClient:
    client = TestClient(creer_app(avec_mcp=False))
    client.headers["X-Albert"] = "1"
    r = client.post("/api/auth/connexion", json={"email": email, "mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def http_admin(session, admin):
    return _connecte(session, admin.email)


@pytest.fixture()
def http_equipe(session):
    _utilisateur(session, "equipe@albert.test", "equipe")
    return _connecte(session, "equipe@albert.test")


@pytest.fixture()
def http_compta(session):
    _utilisateur(session, "compta@albert.test", "compta")
    return _connecte(session, "compta@albert.test")


def nouveau_client(session, acteur: Acteur, nom: str = "Dupont", **extra):
    from albert.services import clients

    donnees = {"type": "particulier", "nom": nom, "email": f"{uuid.uuid4().hex[:8]}@exemple.be", **extra}
    return clients.creer(session, acteur, donnees)
