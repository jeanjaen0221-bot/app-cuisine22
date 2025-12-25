from __future__ import annotations
import uuid
from typing import List, Optional
import re
from pathlib import Path
import csv

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
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


@router.post("/import/upload")
async def import_from_upload(
    file: UploadFile = File(...),
    default_category: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    fname = file.filename or ""
    ext = fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    if ext in {"txt"} or (file.content_type or "").startswith("text/"):
        payload = DrinksImportTextIn(text=text, default_category=default_category, unit=unit)
        return import_from_text(payload, session)
    if ext in {"csv"}:
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        if not rows:
            r2 = csv.reader(text.splitlines())
            simple = list(r2)
            added = 0
            existing = { (r.name or "").strip().lower() for r in session.exec(select(Drink)).all() }
            seen = set()
            for row in simple:
                if not row:
                    continue
                name = (row[0] or "").strip()
                if not name:
                    continue
                key = name.lower()
                if key in seen or key in existing:
                    continue
                session.add(Drink(name=name, category=default_category, unit=unit, active=True))
                seen.add(key)
                added += 1
            session.commit()
            return {"added": added}
        added = 0
        existing = { (r.name or "").strip().lower() for r in session.exec(select(Drink)).all() }
        seen = set()
        for row in rows:
            name = (row.get("name") or row.get("Name") or "").strip()
            if not name:
                continue
            cat = (row.get("category") or row.get("Category") or default_category or None)
            un = (row.get("unit") or row.get("Unit") or unit or None)
            act_raw = str(row.get("active") or row.get("Active") or "true").strip().lower()
            act = False if act_raw in {"0","false","no","non"} else True
            key = name.lower()
            if key in seen or key in existing:
                continue
            session.add(Drink(name=name, category=cat, unit=un, active=act))
            seen.add(key)
            added += 1
        session.commit()
        return {"added": added}
    raise HTTPException(400, "Unsupported file type")


class DrinksImportTextIn(BaseModel):
    text: str
    default_category: Optional[str] = None
    unit: Optional[str] = None


@router.post("/import/text")
def import_from_text(payload: DrinksImportTextIn, session: Session = Depends(get_session)):
    raw = payload.text or ""
    if not raw.strip():
        raise HTTPException(400, "Empty text")

    def norm_spaces(s: str) -> str:
        s = s.replace("\u00a0", " ")
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    def remove_prices_units(s: str) -> str:
        t = s
        # Remove spaced units like '2 5 c l' or '3 3 c l'
        t = re.sub(r"(?:\d\s*)+(c\s*l|m\s*l|l)\b", "", t, flags=re.I)
        # Remove compact units like '25 cl', '33cl'
        t = re.sub(r"\b\d+\s*(cl|ml|l)\b", "", t, flags=re.I)
        # Remove trailing prices (with , or .) and currency words
        t = re.sub(r"\s*[€$]?(?:\d+[\.,]\d+|\d+)(?:\s*(eur|€))?\s*$", "", t, flags=re.I)
        # Remove inline price columns like '2.5 / 5 / 7.5'
        t = re.sub(r"\b\d+(?:[\.,]\d+)?\b(?:\s*/\s*\d+(?:[\.,]\d+)?\b)+", "", t)
        return norm_spaces(t)

    def join_letter_spans(s: str) -> str:
        toks = s.split(" ")
        out: list[str] = []
        buf: list[str] = []
        for t in toks:
            if len(t) == 1 and t.isalpha():
                buf.append(t)
            else:
                if buf:
                    out.append("".join(buf))
                    buf = []
                if t:
                    out.append(t)
        if buf:
            out.append("".join(buf))
        return " ".join([x for x in out if x])

    def is_heading(s: str) -> bool:
        k = s.lower()
        return any(x in k for x in [
            "drink", "bier", "bière", "beer", "aperitif", "aperitief", "digestif",
            "non-alcoholic", "fris", "soda", "soft", "warm", "chaud", "hot",
            "low-alcoholic", "wild"
        ]) and len(k) <= 64

    def detect_category(s: str) -> Optional[str]:
        k = s.lower()
        if any(x in k for x in ["bier", "bière", "beer"]):
            return "bière"
        if any(x in k for x in ["aperitif", "aperitief", "apéritif"]):
            return "apéritif"
        if "digestif" in k:
            return "digestif"
        if any(x in k for x in ["non-alcoholic", "sans alcool"]):
            return "sans alcool"
        if any(x in k for x in ["fris", "soda", "soft"]):
            return "soft"
        if any(x in k for x in ["warm", "hot", "chaud"]):
            return "chaud"
        if any(x in k for x in ["low-alcoholic", "wild"]):
            return "low-alcoholic"
        return None

    lines = [norm_spaces(l) for l in raw.splitlines()]
    existing = { (r.name or "").strip().lower() for r in session.exec(select(Drink)).all() }

    current_cat: Optional[str] = None
    added = 0
    seen = set()
    for ln in lines:
        if not ln:
            continue
        # Ignore purely decorative or navigation lines
        if re.fullmatch(r"[-=*\s]+", ln):
            continue
        # If looks like a section heading, update category and continue
        src = join_letter_spans(ln)
        if is_heading(src):
            cat = detect_category(src)
            if cat:
                current_cat = cat
            continue
        clean = remove_prices_units(src)
        # Drop lines that became empty or obviously non-items
        if not clean or len(clean) < 2:
            continue
        low = clean.lower()
        if any(t in low for t in ["page", "automatic zoom", "actual size", "page fit", "width"]):
            continue
        key = low
        if key in seen or key in existing:
            continue
        row = Drink(name=clean, category=(current_cat or payload.default_category), unit=payload.unit, active=True)
        session.add(row)
        seen.add(key)
        added += 1
    session.commit()
    return {"added": added}
