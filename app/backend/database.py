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
    ensure_notes_name_column()
    ensure_reservation_item_comment_column()
    ensure_reservation_last_pdf_column()


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
        # Non-fatal
        pass


def ensure_reservation_last_pdf_column() -> None:
    """Ensure 'last_pdf_exported_at' column exists on reservation table (idempotent)."""
    try:
        backend = engine.url.get_backend_name()
        with engine.begin() as conn:
            if backend == 'sqlite':
                try:
                    res = conn.exec_driver_sql("PRAGMA table_info(reservation);")
                except Exception:
                    return
                cols = [row[1] for row in res.fetchall()]
                if 'last_pdf_exported_at' not in cols:
                    conn.exec_driver_sql("ALTER TABLE reservation ADD COLUMN last_pdf_exported_at TIMESTAMP NULL;")
            elif backend == 'postgresql':
                conn.execute(text(
                    """
                    DO $$
                    BEGIN
                      IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='reservation' AND column_name='last_pdf_exported_at'
                      ) THEN
                        ALTER TABLE reservation ADD COLUMN last_pdf_exported_at TIMESTAMP NULL;
                      END IF;
                    END$$;
                    """
                ))
            else:
                try:
                    conn.execute(text("ALTER TABLE reservation ADD COLUMN last_pdf_exported_at TIMESTAMP"))
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table may not exist yet in some flows
        pass


def ensure_notes_name_column() -> None:
    """Ensure Note table has a non-null name column; backfill from content if empty.
    Idempotent across sqlite/postgresql.
    """
    try:
        backend = engine.url.get_backend_name()
        with engine.begin() as conn:
            if backend == 'sqlite':
                # Check column existence
                try:
                    res = conn.exec_driver_sql("PRAGMA table_info(note);")
                except Exception:
                    return
                cols = [row[1] for row in res.fetchall()]
                if 'name' not in cols:
                    conn.exec_driver_sql("ALTER TABLE note ADD COLUMN name VARCHAR(255) DEFAULT '';")
                # Backfill reasonable default from content
                try:
                    conn.exec_driver_sql(
                        "UPDATE note SET name = substr(content,1,60) WHERE (name IS NULL OR name = '') AND content IS NOT NULL AND content <> '';"
                    )
                    conn.exec_driver_sql(
                        "UPDATE note SET name = 'Note' WHERE (name IS NULL OR name = '');"
                    )
                except Exception:
                    pass
            elif backend == 'postgresql':
                conn.execute(text(
                    """
                    DO $$
                    BEGIN
                      IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='note' AND column_name='name'
                      ) THEN
                        ALTER TABLE note ADD COLUMN name VARCHAR(255) DEFAULT '';
                      END IF;
                    END$$;
                    """
                ))
                # Backfill defaults
                try:
                    conn.execute(text(
                        "UPDATE note SET name = LEFT(content, 60) WHERE (name IS NULL OR name = '') AND content IS NOT NULL AND content <> '';"
                    ))
                    conn.execute(text(
                        "UPDATE note SET name = 'Note' WHERE (name IS NULL OR name = '');"
                    ))
                except Exception:
                    pass
            else:
                # Best-effort generic alter
                try:
                    conn.execute(text("ALTER TABLE note ADD COLUMN name VARCHAR(255)"))
                except Exception:
                    pass
    except Exception:
        # Non-fatal
        pass


def ensure_reservation_item_comment_column() -> None:
    """Ensure 'comment' column exists on reservationitem table (idempotent)."""
    try:
        backend = engine.url.get_backend_name()
        with engine.begin() as conn:
            if backend == 'sqlite':
                try:
                    res = conn.exec_driver_sql("PRAGMA table_info(reservationitem);")
                except Exception:
                    return
                cols = [row[1] for row in res.fetchall()]
                if 'comment' not in cols:
                    # SQLite can't add with type inference sometimes; use TEXT
                    conn.exec_driver_sql("ALTER TABLE reservationitem ADD COLUMN comment TEXT;")
            elif backend == 'postgresql':
                conn.execute(text(
                    """
                    DO $$
                    BEGIN
                      IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='reservationitem' AND column_name='comment'
                      ) THEN
                        ALTER TABLE reservationitem ADD COLUMN comment TEXT;
                      END IF;
                    END$$;
                    """
                ))
            else:
                try:
                    conn.execute(text("ALTER TABLE reservationitem ADD COLUMN comment TEXT"))
                except Exception:
                    pass
    except Exception:
        # Non-fatal
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
        from PIL import Image
        import io
        from .models import Allergen as AllergenModel
        with Session(engine) as session:
            for fname in os.listdir(icons_dir):
                if not fname.lower().endswith('.png'):
                    continue
                key = os.path.splitext(fname)[0]
                path = os.path.join(icons_dir, fname)
                try:
                    with open(path, 'rb') as f:
                        raw = f.read()
                    # Normalize: trim transparent borders, square canvas, resize to 320px
                    try:
                        im = Image.open(io.BytesIO(raw)).convert('RGBA')
                        bbox = im.getbbox()
                        if bbox:
                            im = im.crop(bbox)
                        max_side = max(im.size)
                        pad = int(max_side * 0.08)
                        canvas_side = max_side + pad * 2
                        canvas = Image.new('RGBA', (canvas_side, canvas_side), (0,0,0,0))
                        x = (canvas_side - im.size[0]) // 2
                        y = (canvas_side - im.size[1]) // 2
                        canvas.paste(im, (x,y), im)
                        canvas = canvas.resize((320, 320), Image.LANCZOS)
                        out = io.BytesIO()
                        canvas.save(out, format='PNG', optimize=True)
                        blob = out.getvalue()
                        # Write back normalized file
                        try:
                            with open(path, 'wb') as wf:
                                wf.write(blob)
                        except Exception:
                            pass
                    except Exception:
                        blob = raw
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
