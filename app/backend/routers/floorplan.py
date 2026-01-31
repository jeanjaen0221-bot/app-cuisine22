from __future__ import annotations
import io
import uuid
from datetime import date, time as dtime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    FloorPlanBase,
    FloorPlanBaseRead,
    FloorPlanBaseUpdate,
    FloorPlanInstance,
    FloorPlanInstanceCreate,
    FloorPlanInstanceRead,
    FloorPlanInstanceUpdate,
    Reservation,
)

router = APIRouter(prefix="/api/floorplan", tags=["floorplan"])


# ---- Helpers ----

def _get_or_create_base(session: Session) -> FloorPlanBase:
    row = session.exec(select(FloorPlanBase).order_by(FloorPlanBase.created_at.asc())).first()
    if row:
        return row
    row = FloorPlanBase(name="base", data={})
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _classify_service_label(t: dtime) -> str:
    return "lunch" if t.hour < 17 else "dinner"


def _load_reservations(session: Session, service_date: date, service_label: Optional[str]) -> List[Reservation]:
    rows = session.exec(select(Reservation).where(Reservation.service_date == service_date)).all()
    if service_label:
        rows = [r for r in rows if _classify_service_label(r.arrival_time) == service_label]
    return rows


def _capacity_for_table(tbl: Dict[str, Any]) -> int:
    cap = int(tbl.get("capacity") or 0)
    kind = (tbl.get("kind") or "").lower()
    if cap <= 0:
        if kind == "rect":
            cap = 6
        elif kind == "round":
            cap = 10
        else:
            cap = 2
    return cap


def _auto_assign(plan_data: Dict[str, Any], reservations: List[Reservation]) -> Dict[str, Any]:
    tables: List[Dict[str, Any]] = list(plan_data.get("tables") or [])
    # Partition tables
    fixed = [t for t in tables if (t.get("kind") == "fixed" or t.get("locked") is True)]
    rects = [t for t in tables if (t.get("kind") == "rect")]
    rounds = [t for t in tables if (t.get("kind") == "round")]

    # Available pools (copy ids)
    avail_fixed = {t.get("id"): t for t in fixed}
    avail_rects = {t.get("id"): t for t in rects}
    avail_rounds = {t.get("id"): t for t in rounds}

    # Sort reservations largest first to minimize waste
    groups = sorted(reservations, key=lambda r: r.pax, reverse=True)

    assignments_by_table: Dict[str, Dict[str, Any]] = {}

    def take_table(pool: Dict[str, Dict[str, Any]], predicate=None) -> Optional[Dict[str, Any]]:
        items = list(pool.values())
        if predicate:
            items = [x for x in items if predicate(x)]
        if not items:
            return None
        # choose smallest capacity that fits
        items.sort(key=lambda t: _capacity_for_table(t))
        chosen = items[0]
        pool.pop(chosen.get("id"), None)
        return chosen

    def take_best_rect_combo(pax: int) -> Optional[List[Dict[str, Any]]]:
        # Try 2-rect combo first for pax > 6
        ids = list(avail_rects.keys())
        best: Optional[List[Dict[str, Any]]] = None
        best_cap = 10**9
        # capacities: rect can be 6 or 8 with extension; allow extension opportunistically
        rect_caps = {}
        for i in ids:
            t = avail_rects[i]
            rect_caps[i] = max(6, int(t.get("capacity") or 6))
        # Try pairs
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = avail_rects[ids[i]]
                b = avail_rects[ids[j]]
                cap_a = max(6, int(a.get("capacity") or 6))
                cap_b = max(6, int(b.get("capacity") or 6))
                base_cap = cap_a + cap_b
                # Allow +2 head extension on each table up to 8
                cap_a_ext = min(8, cap_a)
                cap_b_ext = min(8, cap_b)
                cap_pair = max(base_cap, cap_a_ext + cap_b_ext)
                if cap_pair >= pax and cap_pair < best_cap:
                    best = [a, b]
                    best_cap = cap_pair
        return best

    for r in groups:
        placed = False
        # 1) Fixed tables by best-fit
        best_fixed = take_table(
            avail_fixed,
            predicate=lambda t: _capacity_for_table(t) >= r.pax,
        )
        if best_fixed:
            assignments_by_table.setdefault(best_fixed.get("id"), {"res_id": str(r.id), "name": r.client_name, "pax": r.pax})
            placed = True
        if placed:
            continue

        # 2) Rect single table (6 or 8 with head) best-fit
        def rect_can_fit(t):
            cap = _capacity_for_table(t)
            cap_ext = min(8, max(6, cap))
            return cap_ext >= r.pax

        best_rect = take_table(avail_rects, predicate=rect_can_fit)
        if best_rect:
            assignments_by_table.setdefault(best_rect.get("id"), {"res_id": str(r.id), "name": r.client_name, "pax": r.pax})
            placed = True
        if placed:
            continue

        # 3) Rect combo (two tables)
        combo = take_best_rect_combo(r.pax)
        if combo:
            for t in combo:
                assignments_by_table.setdefault(t.get("id"), {"res_id": str(r.id), "name": r.client_name, "pax": r.pax})
                avail_rects.pop(t.get("id"), None)
            placed = True
        if placed:
            continue

        # 4) Round table (last resort)
        best_round = take_table(
            avail_rounds,
            predicate=lambda t: _capacity_for_table(t) >= r.pax,
        )
        if best_round:
            assignments_by_table.setdefault(best_round.get("id"), {"res_id": str(r.id), "name": r.client_name, "pax": r.pax, "last_resort": True})
            placed = True

        # If not placed, leave unassigned; frontend will show conflict

    return {"tables": assignments_by_table}


# ---- Base plan ----

@router.get("/base", response_model=FloorPlanBaseRead)
def get_base(session: Session = Depends(get_session)):
    row = _get_or_create_base(session)
    return FloorPlanBaseRead(**row.model_dump())


@router.put("/base", response_model=FloorPlanBaseRead)
def update_base(payload: FloorPlanBaseUpdate, session: Session = Depends(get_session)):
    row = _get_or_create_base(session)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return FloorPlanBaseRead(**row.model_dump())


# ---- Instances ----

@router.post("/instances", response_model=FloorPlanInstanceRead)
def create_instance(payload: FloorPlanInstanceCreate, session: Session = Depends(get_session)):
    base = _get_or_create_base(session)
    # Check unique
    existing = session.exec(
        select(FloorPlanInstance).where(
            FloorPlanInstance.service_date == payload.service_date,
            FloorPlanInstance.service_label == payload.service_label,
        )
    ).first()
    if existing:
        return FloorPlanInstanceRead(**existing.model_dump())

    row = FloorPlanInstance(
        service_date=payload.service_date,
        service_label=payload.service_label,
        data=base.data or {},
        assignments={"tables": {}},
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return FloorPlanInstanceRead(**row.model_dump())


@router.get("/instances", response_model=List[FloorPlanInstanceRead])
def list_instances(service_date: Optional[date] = None, service_label: Optional[str] = None, session: Session = Depends(get_session)):
    stmt = select(FloorPlanInstance).order_by(FloorPlanInstance.service_date.desc())
    rows = session.exec(stmt).all()
    if service_date:
        rows = [r for r in rows if r.service_date == service_date]
    if service_label:
        rows = [r for r in rows if (r.service_label or "").lower() == service_label.lower()]
    return [FloorPlanInstanceRead(**r.model_dump()) for r in rows]


@router.get("/instances/{instance_id}", response_model=FloorPlanInstanceRead)
def get_instance(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    return FloorPlanInstanceRead(**row.model_dump())


@router.put("/instances/{instance_id}", response_model=FloorPlanInstanceRead)
def update_instance(instance_id: uuid.UUID, payload: FloorPlanInstanceUpdate, session: Session = Depends(get_session)):
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return FloorPlanInstanceRead(**row.model_dump())


@router.post("/instances/{instance_id}/auto-assign", response_model=FloorPlanInstanceRead)
def auto_assign(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    reservations = _load_reservations(session, row.service_date, row.service_label)
    row.assignments = _auto_assign(row.data or {}, reservations)
    session.add(row)
    session.commit()
    session.refresh(row)
    return FloorPlanInstanceRead(**row.model_dump())


# ---- Import PDF ----

@router.post("/import-pdf")
def import_reservations_pdf(
    file: UploadFile = File(...),
    service_date: date = Form(...),
    service_label: Optional[str] = Form(None),
    create: bool = Form(False),
    session: Session = Depends(get_session),
):
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        raise HTTPException(500, "pdfminer.six non installé côté serveur")

    blob = file.file.read()
    try:
        text = extract_text(io.BytesIO(blob))
    except Exception:
        text = ""

    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    out: List[Dict[str, Any]] = []

    import re
    re_time = re.compile(r"(\d{1,2}[:h]\d{2})")
    re_pax = re.compile(r"(\d{1,2})\s*(pax|pers|couverts?)", re.IGNORECASE)

    default_time = dtime(12, 30) if (service_label or "").lower() == "lunch" else dtime(19, 0)

    for ln in lines:
        nm = ln
        tm = re_time.search(ln)
        px = re_pax.search(ln)
        pax = None
        at = None
        if tm:
            raw = tm.group(1).replace("h", ":")
            try:
                hh, mm = raw.split(":")
                at = dtime(int(hh), int(mm))
            except Exception:
                at = None
            nm = nm.replace(tm.group(1), "").strip(" -,")
        if px:
            pax = int(px.group(1))
            nm = nm.replace(px.group(0), "").strip(" -,")
        if not pax:
            # try trailing number
            m2 = re.search(r"(\d{1,2})$", ln)
            if m2:
                pax = int(m2.group(1))
                nm = nm[: ln.rfind(m2.group(1))].strip(" -,")
        if not pax:
            continue
        if not at:
            at = default_time
        item = {
            "client_name": nm or "Client",
            "pax": pax,
            "service_date": service_date.isoformat(),
            "arrival_time": f"{at.hour:02d}:{at.minute:02d}",
            "drink_formula": "",
            "notes": "",
            "status": "confirmed",
            "final_version": False,
            "on_invoice": False,
            "allergens": "",
            "items": [],
        }
        out.append(item)

    created_ids: List[str] = []
    if create and out:
        for it in out:
            try:
                res = Reservation(
                    client_name=it["client_name"],
                    pax=int(it["pax"]),
                    service_date=service_date,
                    arrival_time=dtime.fromisoformat(it["arrival_time"] + (":00" if len(it["arrival_time"]) == 5 else "")),
                    drink_formula=it["drink_formula"],
                    notes=it["notes"],
                )
                session.add(res)
                session.commit()
                created_ids.append(str(res.id))
            except Exception:
                session.rollback()
                continue

    return {"parsed": out, "created_ids": created_ids}
