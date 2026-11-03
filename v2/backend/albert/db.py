"""Connexion à la base. Le schéma est géré par Alembic (alembic/versions)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import reglages


class Base(DeclarativeBase):
    pass


def creer_moteur(url: str) -> Engine:
    options: dict = {}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    moteur = create_engine(url, pool_pre_ping=True, **options)
    if url.startswith("sqlite"):
        # SQLite n'applique les clés étrangères que si on le lui demande.
        @event.listens_for(moteur, "connect")
        def _fk(dbapi_connection, _record):  # pragma: no cover - plomberie
            curseur = dbapi_connection.cursor()
            curseur.execute("PRAGMA foreign_keys=ON")
            curseur.close()
    return moteur


moteur = creer_moteur(reglages.database_url)
FabriqueSession = sessionmaker(bind=moteur, expire_on_commit=False)


def configurer(url: str) -> None:
    """Change de base (utilisé par les tests)."""
    global moteur
    moteur = creer_moteur(url)
    FabriqueSession.configure(bind=moteur)


def obtenir_session() -> Iterator[Session]:
    session = FabriqueSession()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_contexte() -> Iterator[Session]:
    session = FabriqueSession()
    try:
        yield session
    finally:
        session.close()
