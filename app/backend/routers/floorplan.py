# from __future__ imports must be at the top
from __future__ import annotations
# ---- Numbering helpers ----

def _assign_table_numbers(plan: Dict[str, Any], max_numbers: int = 20, max_tnumbers: int = 20, persist: bool = True) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Assign labels 1..N to fixed/rect tables and T1..TN to round tables, top-to-bottom then left-to-right.
    Returns (updated_plan, id_to_label).
    """
    tables: List[Dict[str, Any]] = list(plan.get("tables") or [])
    # Separate pools
    nums = [t for t in tables if (t.get("kind") in ("fixed", "rect"))]
    tees = [t for t in tables if (t.get("kind") == "round")]
    # Sort top-to-bottom (increasing y), tie by x
    def key_rect(t):
        y = float(t.get("y") or 0)
        x = float(t.get("x") or 0)
        return (y, x)
    def key_round(t):
        y = float(t.get("y") or 0)
        x = float(t.get("x") or 0)
        return (y, x)
    nums.sort(key=key_rect)
    tees.sort(key=key_round)
    id_to_label: Dict[str, str] = {}
    # Assign numbers 1..max_numbers
    for i, t in enumerate(nums[: max_numbers]):
        lbl = str(i + 1)
        id_to_label[str(t.get("id"))] = lbl
        if persist:
            t["label"] = lbl
    # Assign T1..Tmax_tnumbers
    for i, t in enumerate(tees[: max_tnumbers]):
        lbl = f"T{i + 1}"
        id_to_label[str(t.get("id"))] = lbl
        if persist:
            t["label"] = lbl
    if persist:
        plan["tables"] = tables
    return plan, id_to_label

# ---- PDF helpers ----

def _draw_plan_page(c: pdfcanvas.Canvas, plan: Dict[str, Any], id_to_label: Dict[str, str]) -> None:
    page_w, page_h = A4
    margin = 15 * mm
    room = (plan.get("room") or {"width": 1000, "height": 600})
    W = float(room.get("width") or 1000)
    H = float(room.get("height") or 600)
    scale = min((page_w - 2 * margin) / max(1.0, W), (page_h - 2 * margin) / max(1.0, H))
    ox = (page_w - scale * W) / 2.0
    oy = (page_h - scale * H) / 2.0

    def tx(x: float) -> float:
        return ox + scale * x
    def ty(y: float) -> float:
        # input y is top-left downwards; convert to reportlab bottom-up
        return oy + scale * (H - y)

    # room boundary
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.rect(ox, oy, scale * W, scale * H, stroke=1, fill=0)

    # draw no-go zones
    for ng in (plan.get("no_go") or []):
        x = float(ng.get("x") or 0)
        y = float(ng.get("y") or 0)
        w = float(ng.get("w") or 0)
        h = float(ng.get("h") or 0)
        c.setFillColor(colors.Color(1, 0, 0, alpha=0.2))
        c.setStrokeColor(colors.red)
        c.rect(tx(x), ty(y + h), scale * w, scale * h, stroke=1, fill=1)

    # fixtures/walls (light grey)
    c.setFillColor(colors.lightgrey)
    c.setStrokeColor(colors.grey)
    for wrec in (plan.get("walls") or []):
        x = float(wrec.get("x") or 0)
        y = float(wrec.get("y") or 0)
        w = float(wrec.get("w") or 0)
        h = float(wrec.get("h") or 0)
        c.rect(tx(x), ty(y + h), scale * w, scale * h, stroke=1, fill=1)
    for fx in (plan.get("fixtures") or []):
        if "r" in fx and fx.get("r"):
            x = float(fx.get("x") or 0)
            y = float(fx.get("y") or 0)
            r = float(fx.get("r") or 0)
            c.circle(tx(x), ty(y), scale * r, stroke=1, fill=1)
        else:
            x = float(fx.get("x") or 0)
            y = float(fx.get("y") or 0)
            w = float(fx.get("w") or 0)
            h = float(fx.get("h") or 0)
            c.rect(tx(x), ty(y + h), scale * w, scale * h, stroke=1, fill=1)

    # columns
    c.setFillColor(colors.darkgrey)
    for col in (plan.get("columns") or []):
        x = float(col.get("x") or 0)
        y = float(col.get("y") or 0)
        r = float(col.get("r") or 0)
        c.circle(tx(x), ty(y), scale * r, stroke=0, fill=1)

    # tables
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    tables: List[Dict[str, Any]] = list(plan.get("tables") or [])
    for t in tables:
        kind = (t.get("kind") or "rect")
        lbl = t.get("label") or id_to_label.get(str(t.get("id")) or "", "")
        if kind == "round" and t.get("r"):
            x = float(t.get("x") or 0)
            y = float(t.get("y") or 0)
            r = float(t.get("r") or 0)
            c.circle(tx(x), ty(y), scale * r, stroke=1, fill=0)
            if lbl:
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(tx(x), ty(y) - 3, str(lbl))
        else:
            x = float(t.get("x") or 0)
            y = float(t.get("y") or 0)
            w = float(t.get("w") or 120)
            h = float(t.get("h") or 60)
            c.rect(tx(x), ty(y + h), scale * w, scale * h, stroke=1, fill=0)
            if lbl:
                cx = tx(x + w / 2.0)
                cy = ty(y + h / 2.0)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(cx, cy - 3, str(lbl))

    # title
    c.setFont("Helvetica", 10)
    c.drawString(margin, page_h - margin + 2 * mm, "Plan de table (numérotation)")


def _draw_table_list_page(c: pdfcanvas.Canvas, id_to_label: Dict[str, str], plan: Dict[str, Any]) -> None:
    page_w, page_h = A4
    margin = 15 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, page_h - margin, "Numéros de tables")
    c.setFont("Helvetica", 10)
    y = page_h - margin - 10 * mm
    line_h = 6 * mm
    tables: List[Dict[str, Any]] = list(plan.get("tables") or [])
    # Build display list: label, capacity, kind
    rows: List[Tuple[str, int, str]] = []
    for t in tables:
        tid = str(t.get("id"))
        lbl = (t.get("label") or id_to_label.get(tid) or "")
        if not lbl:
            continue
        cap = int(t.get("capacity") or 0)
        kind = str(t.get("kind") or "")
        rows.append((lbl, cap, kind))
    # Sort by label natural (T before numbers later)
    def sort_key(r: Tuple[str, int, str]):
        lbl = r[0]
        if lbl.startswith("T"):
            try:
                return (1, int(lbl[1:]))
            except Exception:
                return (1, 9999)
        try:
            return (0, int(lbl))
        except Exception:
            return (0, 9999)
    rows.sort(key=sort_key)
    # 2 columns list
    col_x = [margin, page_w / 2.0]
    col = 0
    for lbl, cap, kind in rows:
        text = f"{lbl} - {kind} ({cap} pl.)"
        c.drawString(col_x[col], y, text)
        y -= line_h
        if y < margin + line_h:
            col += 1
            if col >= len(col_x):
                c.showPage()
                y = page_h - margin - 10 * mm
                col = 0
                c.setFont("Helvetica", 10)
            else:
                y = page_h - margin - 10 * mm

import io
import uuid
from datetime import date, time as dtime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from sqlmodel import Session, select
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors

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
        # Try to infer from label if numeric (e.g., label "4")
        try:
            lbl = str(tbl.get("label") or "").strip()
            if lbl.isdigit():
                cap = int(lbl)
        except Exception:
            pass
    if cap <= 0:
        if kind == "rect":
            cap = 6
        elif kind == "round":
            cap = 10
        elif kind == "fixed" or (tbl.get("locked") is True):
            cap = 4
        else:
            cap = 2
    return cap


def _rect_intersects(a: Dict[str, float], b: Dict[str, float]) -> bool:
    return not (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])


def _circle_rect_intersects(c: Dict[str, float], r: Dict[str, float]) -> bool:
    cx = max(r["x"], min(c["x"], r["x"] + r["w"]))
    cy = max(r["y"], min(c["y"], r["y"] + r["h"]))
    dx = c["x"] - cx
    dy = c["y"] - cy
    return dx * dx + dy * dy <= (c.get("r") or 0) ** 2


def _circle_circle_intersects(a: Dict[str, float], b: Dict[str, float]) -> bool:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    rr = (a.get("r") or 0) + (b.get("r") or 0)
    return dx * dx + dy * dy <= rr * rr


def _table_collides(plan: Dict[str, Any], t: Dict[str, Any], existing_tables: Optional[List[Dict[str, Any]]] = None) -> bool:
    room = (plan.get("room") or {"width": 0, "height": 0})
    x = float(t.get("x") or 0)
    y = float(t.get("y") or 0)
    if "r" in t and t.get("r"):
        r = float(t.get("r") or 0)
        # bounds
        if x - r < 0 or y - r < 0 or x + r > float(room.get("width") or 0) or y + r > float(room.get("height") or 0):
            return True
        c = {"x": x, "y": y, "r": r}
        for rr in (plan.get("no_go") or []):
            if _circle_rect_intersects(c, {"x": float(rr.get("x")), "y": float(rr.get("y")), "w": float(rr.get("w")), "h": float(rr.get("h"))}):
                return True
        for w in (plan.get("walls") or []):
            if _circle_rect_intersects(c, {"x": float(w.get("x")), "y": float(w.get("y")), "w": float(w.get("w")), "h": float(w.get("h"))}):
                return True
        for fx in (plan.get("fixtures") or []):
            if "r" in fx and fx.get("r"):
                if _circle_circle_intersects(c, {"x": float(fx.get("x")), "y": float(fx.get("y")), "r": float(fx.get("r"))}):
                    return True
            else:
                if _circle_rect_intersects(c, {"x": float(fx.get("x")), "y": float(fx.get("y")), "w": float(fx.get("w")), "h": float(fx.get("h"))}):
                    return True
        for col in (plan.get("columns") or []):
            if _circle_circle_intersects(c, {"x": float(col.get("x")), "y": float(col.get("y")), "r": float(col.get("r") or 0)}):
                return True
        for ot in (existing_tables or (plan.get("tables") or [])):
            if ot is t:
                continue
            if "r" in (ot or {}) and ot.get("r"):
                if _circle_circle_intersects(c, {"x": float(ot.get("x")), "y": float(ot.get("y")), "r": float(ot.get("r"))}):
                    return True
            else:
                if _circle_rect_intersects(c, {"x": float(ot.get("x")), "y": float(ot.get("y")), "w": float(ot.get("w") or 120), "h": float(ot.get("h") or 60)}):
                    return True
        return False
    else:
        w = float(t.get("w") or 120)
        h = float(t.get("h") or 60)
        # bounds
        if x < 0 or y < 0 or x + w > float(room.get("width") or 0) or y + h > float(room.get("height") or 0):
            return True
        rr = {"x": x, "y": y, "w": w, "h": h}
        for ng in (plan.get("no_go") or []):
            if _rect_intersects(rr, {"x": float(ng.get("x")), "y": float(ng.get("y")), "w": float(ng.get("w")), "h": float(ng.get("h"))}):
                return True
        for w2 in (plan.get("walls") or []):
            if _rect_intersects(rr, {"x": float(w2.get("x")), "y": float(w2.get("y")), "w": float(w2.get("w")), "h": float(w2.get("h"))}):
                return True
        for fx in (plan.get("fixtures") or []):
            if "r" in fx and fx.get("r"):
                if _circle_rect_intersects({"x": float(fx.get("x")), "y": float(fx.get("y")), "r": float(fx.get("r"))}, rr):
                    return True
            else:
                if _rect_intersects(rr, {"x": float(fx.get("x")), "y": float(fx.get("y")), "w": float(fx.get("w") or 0), "h": float(fx.get("h") or 0)}):
                    return True
        for col in (plan.get("columns") or []):
            if _circle_rect_intersects({"x": float(col.get("x")), "y": float(col.get("y")), "r": float(col.get("r") or 0)}, rr):
                return True
        for ot in (existing_tables or (plan.get("tables") or [])):
            if ot is t:
                continue
            if "r" in (ot or {}) and ot.get("r"):
                if _circle_rect_intersects({"x": float(ot.get("x")), "y": float(ot.get("y")), "r": float(ot.get("r"))}, rr):
                    return True
            else:
                if _rect_intersects(rr, {"x": float(ot.get("x")), "y": float(ot.get("y")), "w": float(ot.get("w") or 120), "h": float(ot.get("h") or 60)}):
                    return True
        return False


def _find_spot_for_table(plan: Dict[str, Any], shape: str, w: float = 120, h: float = 60, r: float = 50) -> Optional[Dict[str, float]]:
    room = (plan.get("room") or {"width": 0, "height": 0})
    gw = int(room.get("grid") or 50)
    W = int(room.get("width") or 0)
    H = int(room.get("height") or 0)
    # scan grid row by row
    for yy in range(0, max(0, H - (int(h) if shape == "rect" else int(r))), max(1, gw)):
        for xx in range(0, max(0, W - (int(w) if shape == "rect" else int(r))), max(1, gw)):
            cand: Dict[str, Any]
            if shape == "rect":
                cand = {"x": float(xx), "y": float(yy), "w": float(w), "h": float(h)}
            else:
                cand = {"x": float(xx + r), "y": float(yy + r), "r": float(r)}
            t = {"id": "_probe", **cand}
            if not _table_collides(plan, t, existing_tables=plan.get("tables") or []):
                return cand
    return None


def _auto_assign(plan_data: Dict[str, Any], reservations: List[Reservation]) -> Dict[str, Any]:
    tables: List[Dict[str, Any]] = list(plan_data.get("tables") or [])
    # Partition tables
    fixed = [t for t in tables if (t.get("kind") == "fixed" or t.get("locked") is True)]
    rects = [t for t in tables if (t.get("kind") == "rect" and not (t.get("locked") is True))]
    rounds = [t for t in tables if (t.get("kind") == "round" and not (t.get("locked") is True))]

    # Available pools (copy ids)
    avail_fixed = {t.get("id"): t for t in fixed}
    avail_rects = {t.get("id"): t for t in rects}
    avail_rounds = {t.get("id"): t for t in rounds}

    # Sort reservations largest first to minimize waste; tie-breaker by arrival time
    groups = sorted(reservations, key=lambda r: (-int(r.pax), r.arrival_time or dtime(0, 0)))

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
                # Allow +2 head extension on each table up to 8
                cap_a_ext = min(8, cap_a + 2)
                cap_b_ext = min(8, cap_b + 2)
                cap_pair = max(base_cap, cap_a_ext + cap_b_ext)
                if cap_pair >= pax and cap_pair < best_cap:
                    best = [a, b]
                    best_cap = cap_pair
        return best

    def pack_from_pool(pool: Dict[str, Dict[str, Any]], target: int) -> Optional[List[Dict[str, Any]]]:
        items = list(pool.values())
        if not items:
            return None
        # Greedy: pick largest capacities first to minimize number of tables
        items.sort(key=lambda t: _capacity_for_table(t), reverse=True)
        chosen: List[Dict[str, Any]] = []
        total = 0
        for t in items:
            if total >= target:
                break
            chosen.append(t)
            total += _capacity_for_table(t)
        if total >= target:
            return chosen
        return None

    for r in groups:
        placed = False
        # 1) Fixed tables by best-fit
        best_fixed = take_table(
            avail_fixed,
            predicate=lambda t: _capacity_for_table(t) >= r.pax,
        )
        if best_fixed:
            pax_on_table = min(_capacity_for_table(best_fixed), int(r.pax))
            assignments_by_table.setdefault(best_fixed.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
            placed = True
        if placed:
            continue

        # 2) Rect single table (6 or 8 with head) best-fit
        def rect_can_fit(t):
            cap = _capacity_for_table(t)
            # Allow +2 head extension up to 8 for a single rectangle
            cap_ext = min(8, cap + 2)
            return cap_ext >= r.pax

        best_rect = take_table(avail_rects, predicate=rect_can_fit)
        if best_rect:
            pax_on_table = min(_capacity_for_table(best_rect), int(r.pax))
            assignments_by_table.setdefault(best_rect.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
            placed = True
        if placed:
            continue

        # 3) Rect combo (two tables)
        combo = take_best_rect_combo(r.pax)
        if combo:
            remaining = int(r.pax)
            for t in combo:
                pax_on_table = max(0, min(_capacity_for_table(t), remaining))
                assignments_by_table.setdefault(t.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                remaining -= pax_on_table
                avail_rects.pop(t.get("id"), None)
            placed = True
        if placed:
            continue

        # 3b) Pack multiple fixed tables if needed
        chosen = pack_from_pool(avail_fixed, int(r.pax))
        if chosen:
            remaining = int(r.pax)
            for t in chosen:
                pax_on_table = max(0, min(_capacity_for_table(t), remaining))
                assignments_by_table.setdefault(t.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                remaining -= pax_on_table
                avail_fixed.pop(t.get("id"), None)
            placed = True
        if placed:
            continue

        # 3c) Pack multiple rect tables if needed
        chosen = pack_from_pool(avail_rects, int(r.pax))
        if chosen:
            remaining = int(r.pax)
            for t in chosen:
                pax_on_table = max(0, min(_capacity_for_table(t), remaining))
                assignments_by_table.setdefault(t.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                remaining -= pax_on_table
                avail_rects.pop(t.get("id"), None)
            placed = True
        if placed:
            continue

        # 3d) Pack multiple round tables if needed
        chosen = pack_from_pool(avail_rounds, int(r.pax))
        if chosen:
            remaining = int(r.pax)
            for t in chosen:
                pax_on_table = max(0, min(_capacity_for_table(t), remaining))
                assignments_by_table.setdefault(t.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                remaining -= pax_on_table
                avail_rounds.pop(t.get("id"), None)
            placed = True
        if placed:
            continue

        # 4) Round table (last resort)
        best_round = take_table(
            avail_rounds,
            predicate=lambda t: _capacity_for_table(t) >= r.pax,
        )
        if best_round:
            pax_on_table = min(_capacity_for_table(best_round), int(r.pax))
            assignments_by_table.setdefault(best_round.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table, "last_resort": True})
            placed = True

        # 5) Create and place a new non-fixed table if still not placed
        if not placed:
            # Create non-fixed tables to cover remaining pax using 6-seat rectangles first
            remaining = int(r.pax)
            created_any = False
            while remaining > 0:
                spot = _find_spot_for_table(plan_data, "rect", w=120, h=60)
                if not spot:
                    break
                new_id = str(uuid.uuid4())
                cap = 6
                new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot}
                (plan_data.setdefault("tables", [])).append(new_tbl)
                pax_on_table = max(0, min(cap, remaining))
                assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                remaining -= pax_on_table
                created_any = True
            if remaining > 0:
                # try to add a 10-seat round if space allows
                spot = _find_spot_for_table(plan_data, "round", r=50)
                if spot:
                    new_id = str(uuid.uuid4())
                    cap = 10
                    new_tbl = {"id": new_id, "kind": "round", "capacity": cap, **spot}
                    (plan_data.setdefault("tables", [])).append(new_tbl)
                    pax_on_table = max(0, min(cap, remaining))
                    assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                    remaining -= pax_on_table
                    created_any = True
            if remaining <= 0 and created_any:
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


# ---- Numbering and PDF (Base) ----

@router.post("/base/number-tables", response_model=FloorPlanBaseRead)
def number_base_tables(session: Session = Depends(get_session)):
    row = _get_or_create_base(session)
    plan = row.data or {}
    plan, _ = _assign_table_numbers(plan, max_numbers=20, max_tnumbers=20, persist=True)
    row.data = plan
    session.add(row)
    session.commit()
    session.refresh(row)
    return FloorPlanBaseRead(**row.model_dump())


@router.get("/base/export-pdf")
def export_base_pdf(session: Session = Depends(get_session)):
    row = _get_or_create_base(session)
    plan = row.data or {}
    # Do not mutate DB; compute labels transiently if missing
    _plan, id_to_label = _assign_table_numbers(dict(plan), persist=False)
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    _draw_plan_page(c, _plan, id_to_label)
    c.showPage()
    _draw_table_list_page(c, id_to_label, _plan)
    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    headers = {"Content-Disposition": "attachment; filename=base_floorplan.pdf"}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


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
        template_id=base.id,
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


@router.post("/instances/{instance_id}/number-tables", response_model=FloorPlanInstanceRead)
def number_instance_tables(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    plan = row.data or {}
    plan, _ = _assign_table_numbers(plan, max_numbers=20, max_tnumbers=20, persist=True)
    row.data = plan
    session.add(row)
    session.commit()
    session.refresh(row)
    return FloorPlanInstanceRead(**row.model_dump())


@router.get("/instances/{instance_id}/export-pdf")
def export_instance_pdf(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    plan = row.data or {}
    _plan, id_to_label = _assign_table_numbers(dict(plan), persist=False)
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    _draw_plan_page(c, _plan, id_to_label)
    c.showPage()
    _draw_table_list_page(c, id_to_label, _plan)
    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    headers = {"Content-Disposition": "attachment; filename=floorplan_instance.pdf"}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


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
    plan = row.data or {}
    row.data = plan
    row.assignments = _auto_assign(plan, reservations)
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
