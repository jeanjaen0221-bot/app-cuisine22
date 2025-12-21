from __future__ import annotations
import uuid
from typing import List, Optional
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, delete

from ..database import get_session
from ..models import Drink, DrinkCreate, DrinkRead, DrinkUpdate

router = APIRouter(prefix="/api/drinks", tags=["drinks"])


@router.get("", response_model=List[DrinkRead])
def list_drinks(session: Session = Depends(get_session)):
    return session.exec(select(Drink).order_by(Drink.name.asc())).all()


@router.post("", response_model=DrinkRead)
def create_drink(payload: DrinkCreate, session: Session = Depends(get_session)):
    row = Drink(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/{drink_id}", response_model=DrinkRead)
def get_drink(drink_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(Drink, drink_id)
    if not row:
        raise HTTPException(404, "Drink not found")
    return row


@router.put("/{drink_id}", response_model=DrinkRead)
def update_drink(drink_id: uuid.UUID, payload: DrinkUpdate, session: Session = Depends(get_session)):
    row = session.get(Drink, drink_id)
    if not row:
        raise HTTPException(404, "Drink not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{drink_id}")
def delete_drink(drink_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(Drink, drink_id)
    if not row:
        raise HTTPException(404, "Drink not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.delete("")
def delete_all_drinks(confirm: bool = False, session: Session = Depends(get_session)):
    if not confirm:
        raise HTTPException(400, "Confirmation required")
    session.exec(delete(Drink))
    session.commit()
    return {"ok": True}


class DrinksImportPdfIn(BaseModel):
    path: str
    category: Optional[str] = None
    unit: Optional[str] = None


@router.post("/import/pdf")
def import_from_pdf(payload: DrinksImportPdfIn, session: Session = Depends(get_session)):
    try:
        from pypdf import PdfReader
    except Exception:
        raise HTTPException(500, "Missing dependency: pypdf")

    base_assets = (Path(__file__).resolve().parents[1] / "assets").resolve()
    full_path = Path(payload.path).resolve()
    try:
        if base_assets not in full_path.parents and full_path != base_assets and base_assets not in full_path.parents:
            raise HTTPException(400, "Invalid path")
        if not full_path.exists():
            raise HTTPException(404, "File not found")
    except HTTPException:
        raise

    try:
        reader = PdfReader(str(full_path))
    except Exception as e:
        raise HTTPException(400, f"Cannot read PDF: {e}")

    lines: List[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if not txt:
            continue
        for ln in txt.splitlines():
            ln = ln.replace("\u00a0", " ")
            ln = re.sub(r"\s+", " ", ln).strip()
            if not ln:
                continue
            lines.append(ln)

    if not lines:
        raise HTTPException(400, "No extractable text in PDF")

    def clean_name(s: str) -> str:
        s = re.sub(r"\s*[€$]?[0-9]+([\.,][0-9]{1,2})?\s*(EUR|€)?\s*$", "", s, flags=re.I)
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r"\b\d+\s*(cl|ml|l)\b", "", s, flags=re.I)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    existing = { (r.name or "").strip().lower() for r in session.exec(select(Drink)).all() }
    added = 0
    seen = set()
    for raw in lines:
        name = clean_name(raw)
        if not name or len(name) < 2 or len(name) > 120:
            continue
        if any(t in name.lower() for t in ["boissons", "prix", "menu", "carte", "tax", "tva"]):
            continue
        key = name.lower()
        if key in seen or key in existing:
            continue
        row = Drink(name=name, category=payload.category, unit=payload.unit, active=True)
        session.add(row)
        seen.add(key)
        added += 1
    session.commit()
    return {"added": added}
