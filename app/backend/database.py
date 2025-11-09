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
    ensure_final_version_column()
    ensure_allergens_column()


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

def ensure_final_version_column() -> None:
    """Idempotent column addition for reservation.final_version across backends."""
    try:
        backend = engine.url.get_backend_name()
        with engine.begin() as conn:
            if backend == 'sqlite':
                # Check pragma for column existence
                res = conn.exec_driver_sql("PRAGMA table_info(reservation);")
                cols = [row[1] for row in res.fetchall()]
                if 'final_version' not in cols:
                    conn.exec_driver_sql("ALTER TABLE reservation ADD COLUMN final_version BOOLEAN DEFAULT 0;")
            elif backend == 'postgresql':
                conn.execute(text(
                    """
                    DO $$
                    BEGIN
                      IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name='reservation' AND column_name='final_version'
                      ) THEN
                        ALTER TABLE reservation ADD COLUMN final_version BOOLEAN DEFAULT FALSE;
                      END IF;
                    END$$;
                    """
                ))
            else:
                # Best-effort: try generic alter
                try:
                    conn.execute(text("ALTER TABLE reservation ADD COLUMN final_version BOOLEAN DEFAULT FALSE"))
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table may not exist yet in some flows
        pass


def backfill_allergen_icons() -> None:
    """On startup, load any existing PNG icons from assets/allergens into DB rows.
    Idempotent: only sets icon_bytes if missing. Creates row if absent.
    """
    try:
        base_dir = os.path.dirname(__file__)
        icons_dir = os.path.join(base_dir, "assets", "allergens")
        if not os.path.isdir(icons_dir):
            return
        from datetime import datetime
        from .models import Allergen as AllergenModel
        with Session(engine) as session:
            for fname in os.listdir(icons_dir):
                if not fname.lower().endswith('.png'):
                    continue
                key = os.path.splitext(fname)[0]
                path = os.path.join(icons_dir, fname)
                try:
                    with open(path, 'rb') as f:
                        blob = f.read()
                except Exception:
                    continue
                row = session.get(AllergenModel, key)
                if row is None:
                    row = AllergenModel(key=key, label=key, icon_bytes=blob, updated_at=datetime.utcnow())
                else:
                    if not row.icon_bytes:
                        row.icon_bytes = blob
                        row.updated_at = datetime.utcnow()
                session.add(row)
            session.commit()
    except Exception:
        # best-effort; non-fatal
        pass

def ensure_allergens_column() -> None:
    try:
        backend = engine.url.get_backend_name()
        with engine.begin() as conn:
            if backend == 'sqlite':
                res = conn.exec_driver_sql("PRAGMA table_info(reservation);")
                cols = [row[1] for row in res.fetchall()]
                if 'allergens' not in cols:
                    conn.exec_driver_sql("ALTER TABLE reservation ADD COLUMN allergens VARCHAR(1024) DEFAULT '';")
            elif backend == 'postgresql':
                conn.execute(text(
                    """
                    DO $$
                    BEGIN
                      IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='reservation' AND column_name='allergens'
                      ) THEN
                        ALTER TABLE reservation ADD COLUMN allergens VARCHAR(1024) DEFAULT '';
                      END IF;
                    END$$;
                    """
                ))
            else:
                try:
                    conn.execute(text("ALTER TABLE reservation ADD COLUMN allergens VARCHAR(1024) DEFAULT ''"))
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table may not exist yet in some flows
        pass

@contextmanager
def session_context() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
