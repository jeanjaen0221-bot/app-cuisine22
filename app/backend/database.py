import os
from contextlib import contextmanager
from typing import Generator

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

# Normalize postgres scheme for SQLAlchemy/psycopg2
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def run_startup_migrations() -> None:
    """Idempotent migrations for PostgreSQL in production.
    - Remove duplicates on (service_date, arrival_time, client_name, pax)
    - Add CHECK pax >= 1 (if missing)
    - Add UNIQUE constraint on slot (if missing)
    - Add composite index on (service_date, arrival_time)
    """
    backend = engine.url.get_backend_name()
    if backend != 'postgresql':
        return
    with engine.begin() as conn:
        # Remove duplicates, keep earliest by created_at
        conn.execute(text(
            """
            WITH dup AS (
              SELECT id,
                     ROW_NUMBER() OVER (
                       PARTITION BY service_date, arrival_time, client_name, pax
                       ORDER BY created_at
                     ) AS rn
              FROM reservation
            )
            DELETE FROM reservation r
            USING dup d
            WHERE r.id = d.id AND d.rn > 1;
            """
        ))

        # Add CHECK constraint if missing
        conn.execute(text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_reservation_pax_min'
              ) THEN
                ALTER TABLE reservation
                  ADD CONSTRAINT ck_reservation_pax_min CHECK (pax >= 1);
              END IF;
            END$$;
            """
        ))

        # Add UNIQUE constraint if missing
        conn.execute(text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_reservation_slot'
              ) THEN
                ALTER TABLE reservation
                  ADD CONSTRAINT uq_reservation_slot
                  UNIQUE (service_date, arrival_time, client_name, pax);
              END IF;
            END$$;
            """
        ))

        # Add index (idempotent)
        conn.execute(text(
            """
            CREATE INDEX IF NOT EXISTS ix_reservation_date_time
              ON reservation (service_date, arrival_time);
            """
        ))


@contextmanager
def session_context() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
