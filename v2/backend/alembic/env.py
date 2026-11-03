"""Migrations : `alembic upgrade head` (lancé au démarrage du conteneur)."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from albert import models  # noqa: F401 - enregistre les tables
from albert.db import Base, creer_moteur
from albert.config import reglages

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

URL = config.attributes.get("url") or reglages.database_url


def run_migrations_offline() -> None:
    context.configure(url=URL, target_metadata=Base.metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    moteur = creer_moteur(URL)
    with moteur.connect() as connexion:
        context.configure(connection=connexion, target_metadata=Base.metadata, render_as_batch=True,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
