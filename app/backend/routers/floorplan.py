from __future__ import annotations
import uuid
import re
import io
from datetime import date
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models import FloorPlanTemplate, FloorPlanInstance

router = APIRouter(prefix="/api/floorplan", tags=["floorplan"]) 


# ---- Pydantic models for IO ----
from sqlmodel import SQLModel

class FloorPlanTemplateCreate(SQLModel):
    name: str
    width: int = 1000
    height: int = 800
    layout: Dict[str, Any] = {}

class FloorPlanTemplateUpdate(SQLModel):
    name: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    layout: Optional[Dict[str, Any]] = None

class ParsedReservation(SQLModel):
    name: str
    pax: int
    service_date: Optional[str] = None
    arrival_time: Optional[str] = None
    reference: Optional[str] = None
    constraints: Optional[str] = None

class GenerateRequest(SQLModel):
    template_id: uuid.UUID
    service_date: str
    service_label: str = "service"
    reservations: List[ParsedReservation]

class InstanceUpdate(SQLModel):
    assignments: Optional[Dict[str, Any]] = None
    layout_overrides: Optional[Dict[str, Any]] = None


# ---- Template CRUD ----
@router.get("/templates", response_model=List[FloorPlanTemplate])
def list_templates(session: Session = Depends(get_session)):
    return session.exec(select(FloorPlanTemplate).order_by(FloorPlanTemplate.created_at.desc())).all()


@router.post("/templates", response_model=FloorPlanTemplate)
def create_template(payload: FloorPlanTemplateCreate, session: Session = Depends(get_session)):
    row = FloorPlanTemplate(name=payload.name, width=payload.width, height=payload.height, layout=payload.layout or {})
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/templates/{template_id}", response_model=FloorPlanTemplate)
def get_template(template_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(FloorPlanTemplate, template_id)
    if not row:
        raise HTTPException(404, "Template not found")
    return row


@router.put("/templates/{template_id}", response_model=FloorPlanTemplate)
def update_template(template_id: uuid.UUID, payload: FloorPlanTemplateUpdate, session: Session = Depends(get_session)):
    row = session.get(FloorPlanTemplate, template_id)
    if not row:
        raise HTTPException(404, "Template not found")
    upd = payload.model_dump(exclude_unset=True)
    for k, v in upd.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/templates/{template_id}")
def delete_template(template_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(FloorPlanTemplate, template_id)
    if not row:
        raise HTTPException(404, "Template not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


# ---- PDF parsing ----
@router.post("/parse-pdf", response_model=List[ParsedReservation])
async def parse_pdf(
    f: UploadFile = File(...),
    default_date: Optional[str] = Query(None, description="YYYY-MM-DD if PDF lacks date")
):
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        raise HTTPException(500, "pdfminer.six manquant côté serveur")

    try:
        content = await f.read()
        text = extract_text(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Impossible de lire le PDF: {e}")

    lines = [l.strip() for l in (text or '').splitlines()]
    blocks: List[str] = []
    buf: List[str] = []
    for l in lines:
        if not l:
            if buf:
                blocks.append(" ".join(buf))
                buf = []
            continue
        buf.append(l)
    if buf:
        blocks.append(" ".join(buf))

    out: List[ParsedReservation] = []
    re_date = re.compile(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})")
    re_time = re.compile(r"(\d{1,2}[:h]\d{2})")
    re_pax = re.compile(r"(\d{1,3})\s*(?:pers?|personnes?|pax|couverts?|p)\b", re.IGNORECASE)

    for blk in blocks:
        d_m = re_date.search(blk)
        t_m = re_time.search(blk)
        p_m = re_pax.search(blk)
        d_str = None
        if d_m:
            s = d_m.group(1)
            if "/" in s:
                dd, mm, yyyy = s.split("/")
                d_str = f"{yyyy}-{mm}-{dd}"
            else:
                d_str = s[:10]
        if not d_str and default_date:
            d_str = default_date[:10]
        t_str = None
        if t_m:
            t_raw = t_m.group(1).replace('h', ':')
            parts = t_raw.split(":")
            if len(parts) >= 2:
                t_str = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        pax = None
        if p_m:
            pax = int(p_m.group(1))
        # name/reference heuristic: remove recognized tokens and trim
        name = None
        if pax is not None or t_str or d_str:
            tmp = blk
            for m in filter(None, [d_m, t_m, p_m]):
                tmp = tmp.replace(m.group(0), " ")
            tmp = re.sub(r"\s+", " ", tmp).strip()
            name = tmp or "Client"
        if pax is not None:
            out.append(ParsedReservation(name=name or "Client", pax=pax, service_date=d_str, arrival_time=t_str))
    return out


# ---- Generation / Instances ----
@router.post("/generate", response_model=FloorPlanInstance)
def generate_instance(payload: GenerateRequest, session: Session = Depends(get_session)):
    tpl = session.get(FloorPlanTemplate, payload.template_id)
    if not tpl:
        raise HTTPException(404, "Template not found")
    layout = tpl.layout or {}

    fixed = layout.get("fixedTables", [])
    mov6_count = int(layout.get("movableTables6Count", 22))
    round10_count = int(layout.get("round10ReserveCount", 11))

    fixed_free = {str(it.get("id")): int(it.get("seats", 0)) for it in fixed}
    used_fixed: set[str] = set()

    mov6_available = [
        {"id": f"T6-{i+1}", "seats": 6, "head": False} for i in range(max(mov6_count, 0))
    ]
    round10_available = [
        {"id": f"R10-{i+1}", "seats": 10} for i in range(max(round10_count, 0))
    ]

    def assign_best_fixed(size: int) -> Optional[str]:
        candidates = [ (tid, cap) for tid, cap in fixed_free.items() if tid not in used_fixed and cap >= size ]
        if not candidates:
            return None
        tid, _ = sorted(candidates, key=lambda x: (x[1]-size, x[1]))[0]
        used_fixed.add(tid)
        return tid

    def choose_6_tables(size: int) -> Optional[List[Dict[str, Any]]]:
        nonlocal mov6_available
        n = len(mov6_available)
        if n == 0:
            return None
        best: tuple[int, int, List[int]] | None = None  # (waste, k, picks indices)
        # try k from 1..min(n, ceil(size/6)+3)
        import math
        kmax = min(n, max(1, math.ceil(size/6)+3))
        for k in range(1, kmax+1):
            # for x 8-seaters out of k
            for x in range(0, k+1):
                capacity = 8*x + 6*(k-x)
                if capacity < size:
                    continue
                waste = capacity - size
                cand = (waste, k, x)
                if best is None or (waste < best[0]) or (waste == best[0] and k < best[1]):
                    best = (waste, k, x)
        if best is None:
            return None
        _, k, x = best
        if k > len(mov6_available):
            return None
        chosen = []
        # pick first k tables
        picks = mov6_available[:k]
        mov6_available = mov6_available[k:]
        # mark first x as with head (8-seaters)
        for i, t in enumerate(picks):
            t = dict(t)
            if i < x:
                t["seats"] = 8
                t["head"] = True
            chosen.append(t)
        return chosen

    def choose_round10(size: int) -> Optional[List[Dict[str, Any]]]:
        nonlocal round10_available
        need = (size + 9) // 10
        if need <= 0:
            need = 1
        if need > len(round10_available):
            # best-effort partial
            if not round10_available:
                return None
            need = len(round10_available)
        picks = round10_available[:need]
        round10_available = round10_available[need:]
        return [dict(p) for p in picks]

    assignments: Dict[str, Any] = {}
    # Sort reservations by descending pax to place big groups first
    res_sorted = sorted(payload.reservations, key=lambda r: -(r.pax or 0))
    for r in res_sorted:
        key = f"{(r.arrival_time or '').replace(':','')}_{(r.name or 'Client').strip()}"
        size = int(r.pax or 0)
        if size <= 0:
            assignments[key] = {"name": r.name, "pax": r.pax, "tables": []}
            continue
        tid = assign_best_fixed(size)
        if tid:
            assignments[key] = {"name": r.name, "pax": size, "tables": [{"type": "fixed", "id": tid}]}
            continue
        choice = choose_6_tables(size)
        if choice:
            assignments[key] = {"name": r.name, "pax": size, "tables": [{"type": "t6", **t} for t in choice]}
            continue
        choice = choose_round10(size)
        if choice:
            assignments[key] = {"name": r.name, "pax": size, "tables": [{"type": "r10", **t} for t in choice]}
            continue
        assignments[key] = {"name": r.name, "pax": size, "tables": []}

    inst = FloorPlanInstance(
        template_id=tpl.id,
        service_date=date.fromisoformat(payload.service_date[:10]),
        service_label=payload.service_label or "service",
        assignments=assignments,
        layout_overrides={},
    )
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


@router.get("/instances", response_model=List[FloorPlanInstance])
def list_instances(service_date: Optional[date] = None, service_label: Optional[str] = None, session: Session = Depends(get_session)):
    stmt = select(FloorPlanInstance).order_by(FloorPlanInstance.created_at.desc())
    rows = session.exec(stmt).all()
    if service_date:
        rows = [r for r in rows if r.service_date == service_date]
    if service_label:
        rows = [r for r in rows if (r.service_label or '').lower() == (service_label or '').lower()]
    return rows


@router.get("/instances/{instance_id}", response_model=FloorPlanInstance)
def get_instance(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    return row


@router.put("/instances/{instance_id}", response_model=FloorPlanInstance)
def update_instance(instance_id: uuid.UUID, payload: InstanceUpdate, session: Session = Depends(get_session)):
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    upd = payload.model_dump(exclude_unset=True)
    for k, v in upd.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
