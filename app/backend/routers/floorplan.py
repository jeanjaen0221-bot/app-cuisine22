# from __future__ imports must be at the top
from __future__ import annotations
# ---- Numbering helpers ----

def _assign_table_numbers(plan: Dict[str, Any], max_numbers: int = 20, max_tnumbers: int = 20, max_rnumbers: int = 20, persist: bool = True) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Assign labels:
    - Fixed tables: 1..N
    - Rect tables: T1..TN
    - Round tables: R1..RN
    - Sofa: C1..C20
    - Standing: D1..D20
    Order: top-left counting DOWN first (i.e., column-major: x asc, then y desc).
    Returns (updated_plan, id_to_label).
    """
    tables: List[Dict[str, Any]] = list(plan.get("tables") or [])
    # Separate pools
    fixed = [t for t in tables if (t.get("kind") == "fixed" or t.get("locked") is True)]
    rects = [t for t in tables if (t.get("kind") == "rect" and not t.get("locked"))]
    rounds = [t for t in tables if (t.get("kind") == "round")]
    sofas = [t for t in tables if (t.get("kind") == "sofa")]
    standings = [t for t in tables if (t.get("kind") == "standing")]
    # Sort: bas→haut (y DESC), gauche→droite (x ASC)
    def key_table(t):
        x = float(t.get("x") or 0)
        y = float(t.get("y") or 0)
        return (-y, x)  # Tri: y décroissant (bas en premier), puis x croissant
    
    fixed.sort(key=key_table)
    rects.sort(key=key_table)
    rounds.sort(key=key_table)
    sofas.sort(key=key_table)
    standings.sort(key=key_table)
    
    id_to_label: Dict[str, str] = {}
    
    # Assign numbers 1..max_numbers to fixed tables
    for i, t in enumerate(fixed[: max_numbers]):
        lbl = str(i + 1)
        id_to_label[str(t.get("id"))] = lbl
        if persist:
            t["label"] = lbl
    
    # Assign T1..Tmax_tnumbers to rect tables
    for i, t in enumerate(rects[: max_tnumbers]):
        lbl = f"T{i + 1}"
        id_to_label[str(t.get("id"))] = lbl
        if persist:
            t["label"] = lbl
    
    # Assign R1..Rmax_rnumbers to round tables
    for i, t in enumerate(rounds[: max_rnumbers]):
        lbl = f"R{i + 1}"
        id_to_label[str(t.get("id"))] = lbl
        if persist:
            t["label"] = lbl
    
    # Assign C1..C20 to sofa (canapé)
    for i, t in enumerate(sofas[: 20]):
        lbl = f"C{i + 1}"
        id_to_label[str(t.get("id"))] = lbl
        if persist:
            t["label"] = lbl
    
    # Assign D1..D20 to standing (debout)
    for i, t in enumerate(standings[: 20]):
        lbl = f"D{i + 1}"
        id_to_label[str(t.get("id"))] = lbl
        if persist:
            t["label"] = lbl
    
    if persist:
        plan["tables"] = tables
    return plan, id_to_label

# ---- PDF helpers ----

def _draw_plan_page(c: pdfcanvas.Canvas, plan: Dict[str, Any], id_to_label: Dict[str, str], assignments: Optional[Dict[str, Any]] = None) -> None:
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
    tables: List[Dict[str, Any]] = list(plan.get("tables") or [])
    for t in tables:
        kind = (t.get("kind") or "rect")
        # Prefer computed numbering over any existing text label
        raw_lbl = id_to_label.get(str(t.get("id")) or "", "") or t.get("label")
        lbl = str(raw_lbl or "")
        # Sanitize labels: only accept expected formats per type
        try:
            if kind == "fixed":
                lbl = lbl if lbl.isdigit() else ""
            elif kind == "rect":
                lbl = lbl if isinstance(lbl, str) and lbl.startswith("T") and lbl[1:].isdigit() else ""
            elif kind == "round":
                lbl = lbl if isinstance(lbl, str) and lbl.startswith("R") and lbl[1:].isdigit() else ""
            elif kind == "sofa":
                lbl = lbl if isinstance(lbl, str) and lbl.startswith("C") and lbl[1:].isdigit() else ""
            elif kind == "standing":
                lbl = lbl if isinstance(lbl, str) and lbl.startswith("D") and lbl[1:].isdigit() else ""
            else:
                lbl = ""
        except Exception:
            lbl = ""
        
        # Couleurs selon le type
        if kind == "fixed":
            c.setFillColor(colors.Color(0.133, 0.467, 0.467))  # #2c7
        elif kind == "rect":
            c.setFillColor(colors.Color(0.2, 0.6, 1))  # #39f
        elif kind == "round":
            c.setFillColor(colors.Color(1, 0.58, 0.2))  # #f93
        elif kind == "sofa":
            c.setFillColor(colors.Color(0.61, 0.15, 0.69))  # #9c27b0 violet
        elif kind == "standing":
            c.setFillColor(colors.Color(1, 0.34, 0.13))  # #ff5722 orange
        else:
            c.setFillColor(colors.white)
        
        if kind in ("round", "standing") and t.get("r"):
            x = float(t.get("x") or 0)
            y = float(t.get("y") or 0)
            r = float(t.get("r") or 0)
            c.circle(tx(x), ty(y), scale * r, stroke=1, fill=1)
            if lbl:
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", 9)
                c.drawCentredString(tx(x), ty(y) - 3, str(lbl))
            # draw assignment if any
            if assignments and isinstance(assignments.get("tables"), dict):
                a = assignments["tables"].get(str(t.get("id")))
                if a:
                    c.setFont("Helvetica", 8)
                    c.setFillColor(colors.black)
                    c.drawString(tx(x + r + 4), ty(y) + 2, f"{a.get('name','')} ({a.get('pax',0)})")
        else:
            x = float(t.get("x") or 0)
            y = float(t.get("y") or 0)
            w = float(t.get("w") or 120)
            h = float(t.get("h") or 60)
            c.rect(tx(x), ty(y + h), scale * w, scale * h, stroke=1, fill=1)
            cx = tx(x + w / 2.0)
            cy = ty(y + h / 2.0)
            if lbl:
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", 9)
                c.drawCentredString(cx, cy - 3, str(lbl))
            # draw assignment if any
            if assignments and isinstance(assignments.get("tables"), dict):
                a = assignments["tables"].get(str(t.get("id")))
                if a:
                    c.setFont("Helvetica", 8)
                    c.setFillColor(colors.black)
                    c.drawString(tx(x + w + 4), ty(y + 10), f"{a.get('name','')} ({a.get('pax',0)})")

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
        # Prefer computed numbering over any existing text label
        lbl = (id_to_label.get(tid) or t.get("label") or "")
        if not lbl:
            continue
        # Derive capacity robustly like runtime logic
        try:
            cap = _capacity_for_table(t)
        except Exception as e:
            cap = int(t.get("capacity") or 0)
            logger.warning("_draw_table_list_page -> failed to get capacity for table %s: %s", t.get("id"), str(e))
            _dbg_add("WARNING", f"_draw_table_list_page -> capacity error table={t.get('id')}: {str(e)[:50]}")
        kind = str(t.get("kind") or "")
        rows.append((lbl, cap, kind))
    # Sort by label natural (numbers first, then T, R, C, D)
    def sort_key(r: Tuple[str, int, str]):
        lbl = r[0]
        if lbl.startswith("T"):
            try:
                return (1, int(lbl[1:]))
            except Exception:
                return (1, 9999)
        elif lbl.startswith("R"):
            try:
                return (2, int(lbl[1:]))
            except Exception:
                return (2, 9999)
        elif lbl.startswith("C"):
            try:
                return (3, int(lbl[1:]))
            except Exception:
                return (3, 9999)
        elif lbl.startswith("D"):
            try:
                return (4, int(lbl[1:]))
            except Exception:
                return (4, 9999)
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


def _draw_reservations_page(
    c: pdfcanvas.Canvas,
    reservations: List[Reservation],
    assignments: Dict[str, Any],
    id_to_label: Dict[str, str],
) -> None:
    page_w, page_h = A4
    margin = 15 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, page_h - margin, "Liste du service avec numéros de table")
    y = page_h - margin - 10 * mm
    header_h = 7 * mm
    line_h = 7 * mm
    c.setFillColor(colors.whitesmoke)
    c.rect(margin - 2, y - 1.5, page_w - 2 * margin + 4, header_h, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    # Build mapping res_id -> labels list
    lab_by_res: Dict[str, List[str]] = {}
    tbl_map: Dict[str, Any] = (assignments or {}).get("tables", {})
    for tid, a in tbl_map.items():
        res_id = str(a.get("res_id"))
        lbl = id_to_label.get(tid) or ""
        if not lbl:
            continue
        lab_by_res.setdefault(res_id, []).append(lbl)
    # Reservations already sorted by _load_reservations (arrival_time asc, created_at asc)
    rows = reservations
    c.drawString(margin, y, "Heure")
    c.drawString(margin + 25 * mm, y, "Client")
    c.drawString(margin + 110 * mm, y, "Pax")
    c.drawString(margin + 125 * mm, y, "Table(s)")
    y -= header_h
    c.setFont("Helvetica", 9)
    col_client_w = (110 * mm) - (25 * mm) - 6
    col_tables_w = (page_w - margin) - (125 * mm) - 6
    for i, r in enumerate(rows):
        # Zebra background for readability
        if i % 2 == 1:
            c.setFillColor(colors.Color(0.965, 0.965, 0.965))
            c.rect(margin - 2, y - (line_h - 3), page_w - 2 * margin + 4, line_h - 2, stroke=0, fill=1)
            c.setFillColor(colors.black)
        t = getattr(r, "arrival_time", None)
        tstr = str(t)[:5] if t else ""
        c.drawString(margin, y, tstr)
        client_txt = _fit_text(c, (r.client_name or "").upper(), col_client_w, "Helvetica", 9)
        c.drawString(margin + 25 * mm, y, client_txt)
        # Right align Pax just before the Table(s) column
        c.drawRightString(margin + 122 * mm, y, str(r.pax or 0))
        lst_raw = ", ".join(sorted(lab_by_res.get(str(r.id), []), key=lambda s: (s.startswith('R'), s)))
        lst = _fit_text(c, lst_raw, col_tables_w, "Helvetica", 9)
        c.drawString(margin + 125 * mm, y, lst)
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.5)
        c.line(margin - 2, y - 3, page_w - margin + 2, y - 3)
        y -= line_h
        if y < margin + 2 * line_h:
            c.showPage()
            # Redraw header on new page
            c.setFont("Helvetica-Bold", 10)
            y = page_h - margin - 10 * mm
            c.setFillColor(colors.whitesmoke)
            c.rect(margin - 2, y - 1.5, page_w - 2 * margin + 4, header_h, stroke=0, fill=1)
            c.setFillColor(colors.black)
            c.drawString(margin, y, "Heure")
            c.drawString(margin + 25 * mm, y, "Client")
            c.drawString(margin + 110 * mm, y, "Pax")
            c.drawString(margin + 125 * mm, y, "Table(s)")
            y -= header_h
            c.setFont("Helvetica", 9)

import io
import uuid
from datetime import date, time as dtime
import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from sqlmodel import Session, select
import logging
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
try:
    from pypdf import PdfReader, PdfWriter, PdfMerger
except Exception:
    PdfReader = None  # type: ignore
    PdfWriter = None  # type: ignore
    PdfMerger = None  # type: ignore

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
logger = logging.getLogger("app.floorplan")
logger.propagate = True
logger.setLevel(logging.DEBUG)

# --- In-memory debug buffer for UI tail ---
from collections import deque
from datetime import datetime

_dbg_buffer: "deque[dict]" = deque(maxlen=1000)
_dbg_seq: int = 0

class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            global _dbg_seq
            _dbg_seq += 1
            msg = self.format(record)
            _dbg_buffer.append({
                "id": _dbg_seq,
                "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "lvl": record.levelname,
                "msg": msg,
            })
        except Exception:
            pass

_buf_handler = _BufferHandler()
_buf_handler.setLevel(logging.DEBUG)
_buf_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
if not any(isinstance(h, _BufferHandler) for h in logger.handlers):
    logger.addHandler(_buf_handler)

def _dbg_add(level: str, msg: str) -> None:
    """Append a line to the in-memory debug buffer with a new id."""
    try:
        global _dbg_seq
        _dbg_seq += 1
        _dbg_buffer.append({
            "id": _dbg_seq,
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "lvl": level,
            "msg": msg,
        })
    except Exception:
        pass


@router.get("/debug-log")
def get_debug_log(after: Optional[int] = None, limit: int = 200):
    try:
        limit = max(1, min(1000, int(limit)))
    except Exception:
        limit = 200
    items = list(_dbg_buffer)
    if after is not None:
        try:
            a = int(after)
            items = [x for x in items if int(x.get("id") or 0) > a]
        except Exception:
            pass
    else:
        # If no cursor, return the tail only
        items = items[-limit:]
    # When using cursor, still cap to limit
    items = items[-limit:]
    return {"lines": items, "last": (items[-1]["id"] if items else after or 0)}


# ---- Helpers ----

def _get_or_create_base(session: Session) -> FloorPlanBase:
    row = session.exec(select(FloorPlanBase).order_by(FloorPlanBase.created_at.asc())).first()
    if row:
        return row
    row = FloorPlanBase(name="base", data={})
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Created FloorPlanBase id=%s", row.id)
    return row


def _classify_service_label(t: dtime) -> str:
    return "lunch" if t.hour < 17 else "dinner"


def _load_reservations(session: Session, service_date: date, service_label: Optional[str], instance: Optional[FloorPlanInstance] = None) -> List[Reservation]:
    """
    Load reservations for a service.
    If instance is provided, load from instance.reservations (floorplan tool, independent).
    Otherwise, load from main Reservation table (legacy).
    """
    if instance and instance.reservations:
        # Load from instance JSON (floorplan tool)
        items = instance.reservations.get("items", [])
        # Convert dict to Reservation objects
        reservations = []
        for item in items:
            # Create a Reservation-like object from dict
            res = Reservation(
                id=item.get("id") or str(uuid.uuid4()),
                client_name=item.get("client_name", ""),
                pax=item.get("pax", 2),
                service_date=service_date,
                arrival_time=item.get("arrival_time", "12:00"),
                drink_formula=item.get("drink_formula", ""),
                notes=item.get("notes", ""),
                status=item.get("status", "confirmed"),
                final_version=item.get("final_version", False),
                on_invoice=item.get("on_invoice", False),
                allergens=item.get("allergens", ""),
            )
            reservations.append(res)
        # Sort by arrival_time then client_name to align with PDF import order
        reservations.sort(key=lambda r: (r.arrival_time, r.client_name.lower() if r.client_name else ""))
        return reservations
    else:
        # Load from main table (legacy)
        stmt = select(Reservation).where(Reservation.service_date == service_date).order_by(Reservation.arrival_time.asc(), Reservation.created_at.asc())
        rows = session.exec(stmt).all()
        if service_label:
            rows = [r for r in rows if _classify_service_label(r.arrival_time) == service_label]
        return rows


def _capacity_for_table(tbl: Dict[str, Any]) -> int:
    cap = int(tbl.get("capacity") or 0)
    kind = (tbl.get("kind") or "").lower()
    if cap <= 0:
        # fallback defaults
        if kind == "rect":
            cap = 6
        elif kind == "round":
            cap = 10
        elif kind == "fixed" or (tbl.get("locked") is True):
            cap = 4
        elif kind == "sofa":
            cap = 5
        elif kind == "standing":
            cap = 8
        else:
            cap = 2
    return cap


def _fit_text(c: pdfcanvas.Canvas, text: str, max_w: float, font_name: str, font_size: float) -> str:
    s = str(text or "")
    if stringWidth(s, font_name, font_size) <= max_w:
        return s
    ell = "…"
    while s and stringWidth(s + ell, font_name, font_size) > max_w:
        s = s[:-1]
    return s + ell if s else ell


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


def _find_spot_for_table(plan: Dict[str, Any], shape: str, w: float = 120, h: float = 60, r: float = 50, require_rect_zone: bool = False) -> Optional[Dict[str, float]]:
    """Find spot for table. shape can be: rect, round, sofa, standing"""
    room = (plan.get("room") or {"width": 0, "height": 0})
    gw = int(room.get("grid") or 50)
    W = int(room.get("width") or 0)
    H = int(room.get("height") or 0)
    round_zones = plan.get("round_only_zones", [])  # Zones R (rondes uniquement)
    rect_zones = plan.get("rect_only_zones", [])    # Zones T (rectangulaires uniquement)
    
    def is_in_round_only_zone(x: float, y: float) -> bool:
        """Vérifie si une position est dans une zone round-only (R)."""
        for zone in round_zones:
            zx, zy, zw, zh = zone.get("x", 0), zone.get("y", 0), zone.get("w", 0), zone.get("h", 0)
            if x >= zx and x <= zx + zw and y >= zy and y <= zy + zh:
                return True
        return False
    
    def is_in_rect_only_zone(x: float, y: float) -> bool:
        """Vérifie si une position est dans une zone rect-only (T)."""
        for zone in rect_zones:
            zx, zy, zw, zh = zone.get("x", 0), zone.get("y", 0), zone.get("w", 0), zone.get("h", 0)
            if x >= zx and x <= zx + zw and y >= zy and y <= zy + zh:
                return True
        return False
    
    # If a rect spot must be inside a T zone, try zone centers first, then scan inside each T zone
    if require_rect_zone and shape == "rect":
        if not rect_zones:
            return None
        # try centered placement in each rect-only zone
        for zone in rect_zones:
            zx, zy, zw, zh = zone.get("x", 0), zone.get("y", 0), zone.get("w", 0), zone.get("h", 0)
            cx, cy = float(zx + zw / 2.0), float(zy + zh / 2.0)
            cand = {"x": float(cx - w / 2.0), "y": float(cy - h / 2.0), "w": float(w), "h": float(h)}
            # ensure the rect fits entirely within the zone
            if cand["x"] < zx or cand["y"] < zy or cand["x"] + w > zx + zw or cand["y"] + h > zy + zh:
                pass
            else:
                t = {"id": "_probe", **cand}
                if not _table_collides(plan, t, existing_tables=plan.get("tables") or []):
                    return cand
        # fallback: scan grid inside each rect-only zone
        gw = int(room.get("grid") or 50)
        for zone in rect_zones:
            zx, zy, zw, zh = zone.get("x", 0), zone.get("y", 0), zone.get("w", 0), zone.get("h", 0)
            max_y = max(0, int((zy + zh) - h))
            max_x = max(0, int((zx + zw) - w))
            for yy in range(int(zy), max_y, max(1, gw)):
                for xx in range(int(zx), max_x, max(1, gw)):
                    cand = {"x": float(xx), "y": float(yy), "w": float(w), "h": float(h)}
                    t = {"id": "_probe", **cand}
                    if not _table_collides(plan, t, existing_tables=plan.get("tables") or []):
                        return cand
        return None
    # scan grid row by row (default)
    is_circular = shape in ("round", "standing")
    for yy in range(0, max(0, H - (int(h) if not is_circular else int(r))), max(1, gw)):
        for xx in range(0, max(0, W - (int(w) if not is_circular else int(r))), max(1, gw)):
            cand: Dict[str, Any]
            if shape in ("rect", "sofa"):
                cand = {"x": float(xx), "y": float(yy), "w": float(w), "h": float(h)}
                check_x, check_y = float(xx + w/2), float(yy + h/2)  # Centre de la table
            else:  # round, standing
                cand = {"x": float(xx + r), "y": float(yy + r), "r": float(r)}
                check_x, check_y = float(xx + r), float(yy + r)  # Centre du cercle
            
            # Vérifier si la position est dans une zone spécialisée
            in_round_zone = is_in_round_only_zone(check_x, check_y)
            in_rect_zone = is_in_rect_only_zone(check_x, check_y)
            
            # Si c'est une zone round-only (R), seules les tables rondes sont autorisées (pas standing, sofa, etc.)
            if in_round_zone and shape not in ("round",):
                continue
            
            # Si c'est une zone rect-only (T), seules les tables rectangulaires sont autorisées (pas sofa)
            if in_rect_zone and shape not in ("rect",):
                continue
            
            t = {"id": "_probe", **cand}
            if not _table_collides(plan, t, existing_tables=plan.get("tables") or []):
                return cand
    return None


def _auto_assign(plan_data: Dict[str, Any], reservations: List[Reservation]) -> Dict[str, Any]:
    plan = plan_data  # Alias for consistency with helper functions
    tables: List[Dict[str, Any]] = list(plan_data.get("tables") or [])
    
    # Limites de tables dynamiques disponibles (stock)
    max_dynamic = plan_data.get("max_dynamic_tables", {})
    max_rect_dynamic = int(max_dynamic.get("rect", 10))  # Default: 10 tables rect disponibles
    max_round_dynamic = int(max_dynamic.get("round", 5))  # Default: 5 tables rondes disponibles
    # Stock global de chaises dans la zone des tables fixes (déplaçables)
    fixed_chair_stock = int(plan_data.get("fixed_chair_stock", 28))
    
    # Partition tables
    fixed = [t for t in tables if (t.get("kind") == "fixed" or t.get("locked") is True)]
    rects = [t for t in tables if (t.get("kind") == "rect" and not (t.get("locked") is True))]
    rounds = [t for t in tables if (t.get("kind") == "round" and not (t.get("locked") is True))]

    # Available pools (copy ids)
    avail_fixed = {t.get("id"): t for t in fixed}
    avail_rects = {t.get("id"): t for t in rects}
    avail_rounds = {t.get("id"): t for t in rounds}
    avail_sofas = {t.get("id"): t for t in tables if t.get("kind") == "sofa"}
    avail_standings = {t.get("id"): t for t in tables if t.get("kind") == "standing"}
    
    # Compter les tables rect/round déjà existantes pour calculer combien on peut encore en créer
    existing_rect_count = len(rects)
    existing_round_count = len(rounds)
    rect_dynamic_created = 0
    round_dynamic_created = 0

    # Sort reservations largest first to minimize waste; tie-breaker by arrival time
    groups = sorted(reservations, key=lambda r: (-int(r.pax), r.arrival_time or dtime(0, 0)))

    assignments_by_table: Dict[str, Dict[str, Any]] = {}
    unplaced_count = 0  # Compter les réservations non placées
    fixed_chairs_used = 0

    # Pre-pass: fill fixed zone with all 1–4 pax groups first, up to fixed_chair_stock
    placed_small_ids = set()
    small_groups = sorted([r for r in groups if int(r.pax) <= 4], key=lambda r: int(r.pax))
    while small_groups and avail_fixed and (fixed_chairs_used < fixed_chair_stock):
        chairs_rem = fixed_chair_stock - fixed_chairs_used
        # pick the smallest group that fits remaining chairs
        if int(small_groups[0].pax) > chairs_rem:
            break
        r = small_groups.pop(0)
        # choose the smallest fixed table that fits
        cand_fixed = [t for t in avail_fixed.values() if _capacity_for_table(t) >= r.pax and t.get("id") not in assignments_by_table]
        if not cand_fixed:
            break
        cand_fixed.sort(key=lambda t: _capacity_for_table(t))
        best_fixed = cand_fixed[0]
        avail_fixed.pop(best_fixed.get("id"), None)
        pax_on_table = min(_capacity_for_table(best_fixed), int(r.pax))
        assignments_by_table.setdefault(best_fixed.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
        fixed_chairs_used += pax_on_table
        placed_small_ids.add(str(r.id))
        try:
            logger.debug("prepass fixed -> res=%s pax=%s table=%s cap=%s used=%s/%s", r.id, r.pax, best_fixed.get("id"), _capacity_for_table(best_fixed), fixed_chairs_used, fixed_chair_stock)
            _dbg_add("DEBUG", f"prepass fixed -> res={r.id} pax={r.pax} table={best_fixed.get('id')} used={fixed_chairs_used}/{fixed_chair_stock}")
        except Exception:
            pass

    def take_table(pool: Dict[str, Dict[str, Any]], predicate=None) -> Optional[Dict[str, Any]]:
        items = list(pool.values())
        if predicate:
            items = [x for x in items if predicate(x)]
        # Filter out already assigned tables
        items = [t for t in items if t.get("id") not in assignments_by_table]
        if not items:
            return None
        # choose smallest capacity that fits
        items.sort(key=lambda t: _capacity_for_table(t))
        chosen = items[0]
        pool.pop(chosen.get("id"), None)
        return chosen

    def take_best_rect_combo(pax: int) -> Optional[List[Dict[str, Any]]]:
        """Pick best pair of existing rect tables.
        Preference: use base capacity (6 + 6 = 12). Only allow limited extension to reach up to 14 if necessary.
        Do NOT target 16 by default to avoid over-extending; larger groups should use aligned dynamic tables.
        """
        available_ids = [id for id in avail_rects.keys() if id not in assignments_by_table]
        if len(available_ids) < 2:
            return None
        ids = available_ids
        best_pair: Optional[List[Dict[str, Any]]] = None
        best_score = (10**9, 10**9)  # (total_cap, total_extension)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = avail_rects[ids[i]]
                b = avail_rects[ids[j]]
                base_a = max(6, int(a.get("capacity") or 6))
                base_b = max(6, int(b.get("capacity") or 6))
                base_sum = base_a + base_b
                if base_sum >= pax:
                    # Prefer minimal total capacity (avoid waste), zero extension
                    score = (base_sum, 0)
                    if score < best_score:
                        best_score = score
                        best_pair = [a, b]
                    continue
                # Allow limited extension ONLY up to 14 total
                if pax <= 14:
                    # Minimal extension needed but cap at 14
                    need = pax - base_sum
                    if need <= 4:
                        total_cap = min(14, base_sum + need)
                        # Prefer less extension, then less total_cap
                        score = (total_cap, need)
                        if total_cap >= pax and score < best_score:
                            best_score = score
                            best_pair = [a, b]
        return best_pair

    def pack_from_pool(pool: Dict[str, Dict[str, Any]], target: int, allow_rect_ext: bool = False) -> Optional[List[Dict[str, Any]]]:
        items = list(pool.values())
        if not items:
            return None
        # CRITICAL: Filter out already assigned tables (same as take_table)
        items = [t for t in items if t.get("id") not in assignments_by_table]
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
            cap = _capacity_for_table(t)
            # Allow +2 extension for rect tables
            if allow_rect_ext and t.get("kind") == "rect":
                cap = min(8, cap + 2)
            total += cap
        if total >= target:
            return chosen
        return None

    for r in groups:
        if str(r.id) in placed_small_ids:
            continue
        placed = False
        # EARLY: For large groups (>=13 pax), first try ONE large dynamic rect (no splitting)
        if int(r.pax) >= 13 and (rect_dynamic_created) < max_rect_dynamic:
            total = int(r.pax)
            needed = min(4, math.ceil(total / 6))
            width = needed * 120 + (needed - 1) * 10
            cap = 6 * needed
            if cap >= total:
                spot = _find_spot_for_table(plan_data, "rect", w=width, h=60, require_rect_zone=True)
                if spot:
                    new_id = str(uuid.uuid4())
                    new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed}
                    (plan_data.setdefault("tables", [])).append(new_tbl)
                    assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": total})
                    rect_dynamic_created += 1
                    placed = True
                    try:
                        logger.debug("assign dynamic-large-rect (early) -> res=%s pax=%s table=%s cap=%s span=%s", r.id, r.pax, new_id, cap, needed)
                        _dbg_add("DEBUG", f"assign dynamic-large-rect (early) -> res={r.id} pax={r.pax} table={new_id} span={needed}")
                    except Exception:
                        pass
        if placed:
            continue
        # 1) Fixed tables by best-fit
        best_fixed = take_table(
            avail_fixed,
            predicate=lambda t: _capacity_for_table(t) >= r.pax,
        )
        if best_fixed and int(r.pax) <= 4 and (fixed_chairs_used + int(r.pax) <= fixed_chair_stock):
            pax_on_table = min(_capacity_for_table(best_fixed), int(r.pax))
            assignments_by_table.setdefault(best_fixed.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
            fixed_chairs_used += pax_on_table
            placed = True
            try:
                logger.debug("assign fixed -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_fixed.get("id"), _capacity_for_table(best_fixed))
                _dbg_add("DEBUG", f"assign fixed -> res={r.id} pax={r.pax} table={best_fixed.get('id')}")
            except Exception as e:
                logger.warning("assign fixed -> log failed: %s", str(e))
                pass
        if placed:
            continue

        # 2a) Removed pair preference for 7-8 pax: keep group together on a single rect (with extension to 8 as last resort)

        # 2) Rect single table (6 or 8 with head) best-fit (extension is last resort) for up to 8 pax
        # For groups <=4, only consider rects if fixed stock is exhausted or no fixed tables remain
        rect_allowed = True
        if int(r.pax) <= 4:
            rect_allowed = (fixed_chairs_used + int(r.pax) > fixed_chair_stock) or (len(avail_fixed) == 0)

        if rect_allowed:
            def rect_can_fit(t):
                cap = _capacity_for_table(t)
                # Allow +2 head extension up to 8 for a single rectangle
                cap_ext = min(8, cap + 2)
                return cap_ext >= r.pax

            best_rect = take_table(avail_rects, predicate=rect_can_fit)
            if best_rect:
                # seat up to extended capacity for a single rectangle
                pax_on_table = min(int(r.pax), min(8, _capacity_for_table(best_rect) + 2))
                assignments_by_table.setdefault(best_rect.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                placed = True
                try:
                    logger.debug("assign rect -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_rect.get("id"), _capacity_for_table(best_rect))
                    _dbg_add("DEBUG", f"assign rect -> res={r.id} pax={r.pax} table={best_rect.get('id')}")
                except Exception as e:
                    logger.warning("assign rect -> log failed: %s", str(e))
                    pass
        if placed:
            continue

        # 2b) For groups (>=9 pax), create ONE large dynamic rect table (max span of 4 widths)
        # to avoid scattering across distant tables.
        if int(r.pax) >= 9 and (rect_dynamic_created) < max_rect_dynamic:
            total = int(r.pax)
            needed = min(4, math.ceil(total / 6))
            width = needed * 120 + (needed - 1) * 10
            cap = 6 * needed
            if cap >= total:
                spot = _find_spot_for_table(plan_data, "rect", w=width, h=60, require_rect_zone=True)
                if spot:
                    new_id = str(uuid.uuid4())
                    new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed}
                    (plan_data.setdefault("tables", [])).append(new_tbl)
                    assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": total})
                    rect_dynamic_created += 1
                    placed = True
                    try:
                        logger.debug("assign dynamic-large-rect -> res=%s pax=%s table=%s cap=%s span=%s", r.id, r.pax, new_id, cap, needed)
                        _dbg_add("DEBUG", f"assign dynamic-large-rect -> res={r.id} pax={r.pax} table={new_id} span={needed}")
                    except Exception:
                        pass
        if placed:
            continue

        # 3) Rect combo (two tables) disabled to avoid splitting groups across separate existing tables

        # 3aa) Standing single (8 pax)
        standing_allowed = True
        if int(r.pax) <= 4:
            standing_allowed = (fixed_chairs_used + int(r.pax) > fixed_chair_stock) or (len(avail_fixed) == 0)
        if standing_allowed:
            best_standing = take_table(avail_standings, predicate=lambda t: _capacity_for_table(t) >= r.pax)
            if best_standing:
                pax_on_table = min(_capacity_for_table(best_standing), int(r.pax))
                assignments_by_table.setdefault(best_standing.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                placed = True
        if placed:
            continue

        # 3b) Pack multiple fixed tables disabled (never split groups across distant fixed tables)

        # 3c) Pack multiple rect tables disabled (prefer aligned dynamic cluster)

        # 3d) Pack multiple round tables disabled (avoid splitting groups)

        # 4) Round table single (dernier recours) — for <=4 pax, only if fixed stock is exhausted or no fixed tables left
        round_allowed = True
        if int(r.pax) <= 4:
            round_allowed = (fixed_chairs_used + int(r.pax) > fixed_chair_stock) or (len(avail_fixed) == 0)
        if round_allowed:
            best_round = take_table(
                avail_rounds,
                predicate=lambda t: _capacity_for_table(t) >= r.pax,
            )
            if best_round:
                pax_on_table = min(_capacity_for_table(best_round), int(r.pax))
                assignments_by_table.setdefault(best_round.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table, "last_resort": True})
                placed = True
                try:
                    logger.debug("assign round -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_round.get("id"), _capacity_for_table(best_round))
                    _dbg_add("DEBUG", f"assign round (last resort) -> res={r.id} pax={r.pax} table={best_round.get('id')}")
                except Exception as e:
                    logger.warning("assign round -> log failed: %s", str(e))
                    pass

        # 4b) Sofa single (dernier recours aussi) — for <=4 pax, only if fixed stock is exhausted or no fixed tables left
        if not placed:
            sofa_allowed = True
            if int(r.pax) <= 4:
                sofa_allowed = (fixed_chairs_used + int(r.pax) > fixed_chair_stock) or (len(avail_fixed) == 0)
            if sofa_allowed:
                best_sofa = take_table(avail_sofas, predicate=lambda t: _capacity_for_table(t) >= r.pax)
                if best_sofa:
                    pax_on_table = min(_capacity_for_table(best_sofa), int(r.pax))
                    assignments_by_table.setdefault(best_sofa.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table, "last_resort": True})
                    placed = True
                    try:
                        logger.debug("assign sofa -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_sofa.get("id"), _capacity_for_table(best_sofa))
                        _dbg_add("DEBUG", f"assign sofa (last resort) -> res={r.id} pax={r.pax} table={best_sofa.get('id')}")
                    except Exception as e:
                        logger.warning("assign sofa -> log failed: %s", str(e))
                        pass

        # 5) Create and place a new non-fixed table if still not placed (single large rect first)
        if not placed:
            unplaced_count += 1
            print(f"CREATING DYNAMIC TABLES for res={r.id} ({r.client_name}, {r.pax} pax) - no existing table available")
            _dbg_add("INFO", f"CREATING DYNAMIC TABLES for {r.client_name} ({r.pax} pax) - stock: rect {max_rect_dynamic-rect_dynamic_created}/{max_rect_dynamic}, round {max_round_dynamic-round_dynamic_created}/{max_round_dynamic}")
            remaining = int(r.pax)
            created_any = False
            # Try one big rect first (span up to 4 widths)
            needed = min(4, math.ceil(remaining / 6))
            width = needed * 120 + (needed - 1) * 10
            cap = 6 * needed
            if cap >= remaining:
                spot = _find_spot_for_table(plan_data, "rect", w=width, h=60, require_rect_zone=True)
                if spot and (rect_dynamic_created) < max_rect_dynamic:
                    new_id = str(uuid.uuid4())
                    new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed}
                    (plan_data.setdefault("tables", [])).append(new_tbl)
                    assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": remaining})
                    remaining = 0
                    rect_dynamic_created += 1
                    created_any = True
                    print(f"✓ Created large rect table {rect_dynamic_created}/{max_rect_dynamic} (span {needed})")
                    _dbg_add("INFO", f"✓ Created large rect {rect_dynamic_created}/{max_rect_dynamic} span={needed}")
            # If still remaining, try a single round 10 (still not split)
            if remaining > 0 and (round_dynamic_created) < max_round_dynamic:
                spot = _find_spot_for_table(plan_data, "round", r=50)
                if spot:
                    new_id = str(uuid.uuid4())
                    cap = 10
                    new_tbl = {"id": new_id, "kind": "round", "capacity": cap, **spot, "dynamic": True}
                    if cap >= remaining:
                        (plan_data.setdefault("tables", [])).append(new_tbl)
                        assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": remaining})
                        remaining = 0
                        round_dynamic_created += 1
                        created_any = True
                        print(f"✓ Created round table {round_dynamic_created}/{max_round_dynamic}")
                        _dbg_add("INFO", f"✓ Created round {round_dynamic_created}/{max_round_dynamic}")
                    else:
                        logger.warning("Round 10 insufficient for %s (%d pax)", r.client_name, int(r.pax))
                        _dbg_add("WARNING", f"Round 10 insufficient for {r.client_name} ({int(r.pax)} pax)")
                else:
                    logger.warning("No space found for new round table")
                    _dbg_add("WARNING", "No space for new round table")
            if remaining <= 0 and created_any:
                placed = True
            elif remaining > 0:
                if (rect_dynamic_created) >= max_rect_dynamic:
                    logger.warning("⚠️ STOCK LIMIT REACHED: rect tables %d/%d (dynamic created)", rect_dynamic_created, max_rect_dynamic)
                    _dbg_add("WARNING", f"STOCK LIMIT: rect {rect_dynamic_created}/{max_rect_dynamic}")
                if (round_dynamic_created) >= max_round_dynamic:
                    logger.warning("⚠️ STOCK LIMIT REACHED: round tables %d/%d (dynamic created)", round_dynamic_created, max_round_dynamic)
                    _dbg_add("WARNING", f"STOCK LIMIT: round {round_dynamic_created}/{max_round_dynamic}")

        # If not placed, leave unassigned; frontend will show conflict
        if not placed:
            logger.warning("UNPLACED reservation: %s (%s, %d pax) - no space found even after trying to create tables", r.id, r.client_name, r.pax)
            _dbg_add("WARNING", f"UNPLACED: {r.client_name} ({r.pax} pax)")

    print(f"_auto_assign SUMMARY: {len(reservations)} reservations, {unplaced_count} tried dynamic, {len(assignments_by_table)} assignments | STOCK USED: rect {rect_dynamic_created}/{max_rect_dynamic}, round {round_dynamic_created}/{max_round_dynamic}")
    _dbg_add("INFO", f"_auto_assign SUMMARY: {len(reservations)} res, {unplaced_count} tried dynamic, {len(assignments_by_table)} assigned | STOCK: rect {rect_dynamic_created}/{max_rect_dynamic}, round {round_dynamic_created}/{max_round_dynamic}")
    return {"tables": assignments_by_table}


# ---- Base plan ----

@router.get("/base", response_model=FloorPlanBaseRead)
def get_base(session: Session = Depends(get_session)):
    _dbg_add("INFO", "GET /base")
    row = _get_or_create_base(session)
    logger.info("GET /base -> id=%s", row.id)
    _dbg_add("INFO", f"GET /base -> id={row.id}")
    return FloorPlanBaseRead(**row.model_dump())


@router.put("/base", response_model=FloorPlanBaseRead)
def update_base(payload: FloorPlanBaseUpdate, session: Session = Depends(get_session)):
    _dbg_add("INFO", "PUT /base")
    row = _get_or_create_base(session)
    data = payload.model_dump(exclude_unset=True)
    
    # Validate data if present
    if "data" in data and data["data"]:
        plan_data = data["data"]
        if not isinstance(plan_data, dict):
            raise HTTPException(400, "Invalid data format: must be dict")
        if "tables" in plan_data:
            if not isinstance(plan_data["tables"], list):
                raise HTTPException(400, "Invalid data.tables format: must be list")
            # Validate each table
            for i, table in enumerate(plan_data["tables"]):
                if not isinstance(table, dict):
                    raise HTTPException(400, f"Invalid table at index {i}: must be dict")
                if "id" not in table:
                    raise HTTPException(400, f"Invalid table at index {i}: missing 'id'")
                if "x" not in table or "y" not in table:
                    raise HTTPException(400, f"Invalid table {table.get('id')}: missing x/y coordinates")
        if "room" in plan_data:
            room = plan_data["room"]
            if not isinstance(room, dict):
                raise HTTPException(400, "Invalid room format: must be dict")
            if "width" not in room or "height" not in room:
                raise HTTPException(400, "Invalid room: missing width/height")
            if room["width"] < 100 or room["height"] < 100:
                raise HTTPException(400, "Invalid room: dimensions must be >= 100")
    
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("PUT /base -> updated id=%s (keys=%s)", row.id, list(data.keys()))
    _dbg_add("INFO", f"PUT /base -> updated id={row.id} keys={list(data.keys())}")
    return FloorPlanBaseRead(**row.model_dump())


# ---- Numbering and PDF (Base) ----

@router.post("/base/number-tables", response_model=FloorPlanBaseRead)
def number_base_tables(session: Session = Depends(get_session)):
    _dbg_add("INFO", "POST /base/number-tables")
    row = _get_or_create_base(session)
    plan = row.data or {}
    plan, _ = _assign_table_numbers(plan, max_numbers=20, max_tnumbers=20, persist=True)
    row.data = plan
    session.add(row)
    session.commit()
    session.refresh(row)
    tables = plan.get("tables") or []
    used = sum(1 for t in tables if t.get("label"))
    logger.info("POST /base/number-tables -> labeled=%d", used)
    _dbg_add("INFO", f"POST /base/number-tables -> labeled={used}")
    return FloorPlanBaseRead(**row.model_dump())


@router.get("/base/export-pdf")
def export_base_pdf(session: Session = Depends(get_session)):
    _dbg_add("INFO", "GET /base/export-pdf")
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
    logger.info("GET /base/export-pdf -> bytes=%d labels=%d", len(pdf_bytes), len(id_to_label))
    _dbg_add("INFO", f"GET /base/export-pdf -> bytes={len(pdf_bytes)} labels={len(id_to_label)}")
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.post("/instances/{instance_id}/export-annotated")
def export_instance_annotated(
    instance_id: uuid.UUID,
    file: UploadFile = File(...),
    page_start: int = Form(0),
    start_y_mm: float = Form(95.0),
    row_h_mm: float = Form(13.5),
    table_x_mm: float = Form(137.0),
    session: Session = Depends(get_session),
):
    _dbg_add("INFO", f"POST /instances/{instance_id}/export-annotated")
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    if PdfReader is None:
        raise HTTPException(501, "PDF annotation not available (pypdf not installed)")
    
    # Si l'instance n'a pas de plan, copier depuis le plan de base
    plan = row.data or {}
    if not plan.get("tables"):
        base = _get_or_create_base(session)
        if base and base.data:
            import copy
            plan = copy.deepcopy(base.data)
            logger.info("POST /instances/%s/export-annotated -> copied base plan with %d tables", instance_id, len(plan.get("tables") or []))
            _dbg_add("INFO", f"POST /instances/{instance_id}/export-annotated -> copied base plan with {len(plan.get('tables') or [])} tables")
    _plan, id_to_label = _assign_table_numbers(dict(plan), persist=False)
    # Build labels by reservation id
    lab_by_res: Dict[str, List[str]] = {}
    tbl_map: Dict[str, Any] = (row.assignments or {}).get("tables", {})
    for tid, a in tbl_map.items():
        rid = str(a.get("res_id"))
        lbl = id_to_label.get(tid)
        if lbl:
            lab_by_res.setdefault(rid, []).append(lbl)
    try:
        reservations = _load_reservations(session, row.service_date, row.service_label, instance=row)
    except Exception as e:
        logger.error("export_instance_annotated -> failed to load reservations: %s", str(e))
        _dbg_add("ERROR", f"export_instance_annotated -> load reservations failed: {str(e)[:100]}")
        reservations = []
    # Reservations already sorted by _load_reservations (arrival_time asc, created_at asc)

    # Read original PDF
    orig_bytes = file.file.read()
    reader = PdfReader(io.BytesIO(orig_bytes))
    writer = PdfWriter()

    # Prepare overlays per page
    res_idx = 0
    total_annotated = 0
    
    logger.info("POST /instances/%s/export-annotated -> annotating %d reservations", instance_id, len(reservations))
    _dbg_add("INFO", f"Annotating {len(reservations)} reservations with table numbers")
    
    for pidx in range(len(reader.pages)):
        page = reader.pages[pidx]
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        # Build overlay for this page
        ov_buf = io.BytesIO()
        cv = pdfcanvas.Canvas(ov_buf, pagesize=(pw, ph))
        y_top = ph - start_y_mm * mm
        y = y_top
        drawn_any = False
        page_annotations = 0
        
        # Only start drawing from page_start
        if pidx >= page_start:
            while res_idx < len(reservations):
                res = reservations[res_idx]
                lbls = ", ".join(sorted(lab_by_res.get(str(res.id), []), key=lambda s: (s.startswith('R'), s)))
                if lbls:
                    cv.setFont("Helvetica-Bold", 10)
                    cv.setFillColorRGB(0, 0, 0)  # Noir
                    cv.drawString(table_x_mm * mm, y, lbls)
                    drawn_any = True
                    page_annotations += 1
                    total_annotated += 1
                    if total_annotated <= 5:  # Log les 5 premières
                        logger.debug("  Annotated: %s -> %s at y=%.1f", res.client_name[:20], lbls, y)
                # advance to next reservation after drawing current row
                res_idx += 1
                y -= row_h_mm * mm
                # Stop near bottom
                if y < 15 * mm:
                    break
            # If we broke due to height, keep the same res_idx to continue on next page
        
        if page_annotations > 0:
            logger.debug("Page %d: annotated %d reservations", pidx, page_annotations)
        
        cv.save()
        ov_pdf = PdfReader(io.BytesIO(ov_buf.getvalue()))
        base_page = reader.pages[pidx]
        if drawn_any and len(ov_pdf.pages) > 0:
            base_page.merge_page(ov_pdf.pages[0])
        writer.add_page(base_page)

    # Append the generated plan+lists PDF
    plan_buf = io.BytesIO()
    c = pdfcanvas.Canvas(plan_buf, pagesize=A4)
    _draw_reservations_page(c, reservations, (row.assignments or {}), id_to_label)
    c.showPage()
    _draw_plan_page(c, _plan, id_to_label, assignments=(row.assignments or {}))
    c.showPage()
    _draw_table_list_page(c, id_to_label, _plan)
    c.save()
    plan_reader = PdfReader(io.BytesIO(plan_buf.getvalue()))
    for pg in plan_reader.pages:
        writer.add_page(pg)

    out = io.BytesIO()
    writer.write(out)
    pdf_bytes = out.getvalue()
    out.close()
    headers = {"Content-Disposition": "attachment; filename=floorplan_instance_annotated.pdf"}
    logger.info("POST /instances/%s/export-annotated -> bytes=%d", instance_id, len(pdf_bytes))
    _dbg_add("INFO", f"POST /instances/{instance_id}/export-annotated -> bytes={len(pdf_bytes)} reservations={len(reservations)}")
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

# ---- Instances ----

@router.post("/instances", response_model=FloorPlanInstanceRead)
def create_instance(payload: FloorPlanInstanceCreate, session: Session = Depends(get_session)):
    _dbg_add("INFO", f"POST /instances date={payload.service_date} label={payload.service_label}")
    base = _get_or_create_base(session)
    # Check unique
    existing = session.exec(
        select(FloorPlanInstance).where(
            FloorPlanInstance.service_date == payload.service_date,
            FloorPlanInstance.service_label == payload.service_label,
        )
    ).first()
    if existing:
        logger.info("POST /instances -> exists id=%s for %s/%s", existing.id, payload.service_date, payload.service_label)
        _dbg_add("INFO", f"POST /instances -> exists id={existing.id}")
        return FloorPlanInstanceRead(**existing.model_dump())

    row = FloorPlanInstance(
        service_date=payload.service_date,
        service_label=payload.service_label,
        template_id=base.id,
        data=base.data or {},
        assignments={"tables": {}},
        reservations={"items": []},  # Initialize empty reservations
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("POST /instances -> created id=%s for %s/%s (template_id=%s)", row.id, row.service_date, row.service_label, row.template_id)
    _dbg_add("INFO", f"POST /instances -> created id={row.id}")
    return FloorPlanInstanceRead(**row.model_dump())


@router.get("/instances", response_model=List[FloorPlanInstanceRead])
def list_instances(service_date: Optional[date] = None, service_label: Optional[str] = None, session: Session = Depends(get_session)):
    stmt = select(FloorPlanInstance).order_by(FloorPlanInstance.service_date.desc())
    rows = session.exec(stmt).all()
    if service_date:
        rows = [r for r in rows if r.service_date == service_date]
    if service_label:
        rows = [r for r in rows if (r.service_label or "").lower() == service_label.lower()]
    logger.info("GET /instances -> count=%d (filters: date=%s label=%s)", len(rows), service_date, service_label)
    return [FloorPlanInstanceRead(**r.model_dump()) for r in rows]


@router.get("/instances/{instance_id}", response_model=FloorPlanInstanceRead)
def get_instance(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    _dbg_add("INFO", f"GET /instances/{instance_id}")
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    logger.info("GET /instances/%s -> found", instance_id)
    _dbg_add("INFO", f"GET /instances/{instance_id} -> found")
    return FloorPlanInstanceRead(**row.model_dump())


@router.post("/instances/{instance_id}/number-tables", response_model=FloorPlanInstanceRead)
def number_instance_tables(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    _dbg_add("INFO", f"POST /instances/{instance_id}/number-tables")
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    
    # Si l'instance n'a pas de plan, copier depuis le plan de base
    plan = row.data or {}
    if not plan.get("tables"):
        base = _get_or_create_base(session)
        if base and base.data:
            import copy
            plan = copy.deepcopy(base.data)
            logger.info("POST /instances/%s/number-tables -> copied base plan with %d tables", instance_id, len(plan.get("tables") or []))
            _dbg_add("INFO", f"POST /instances/{instance_id}/number-tables -> copied base plan with {len(plan.get('tables') or [])} tables")
    
    plan, _ = _assign_table_numbers(plan, max_numbers=20, max_tnumbers=20, persist=True)
    row.data = plan
    session.add(row)
    session.commit()
    session.refresh(row)
    tables = plan.get("tables") or []
    used = sum(1 for t in tables if t.get("label"))
    logger.info("POST /instances/%s/number-tables -> labeled=%d", instance_id, used)
    _dbg_add("INFO", f"POST /instances/{instance_id}/number-tables -> labeled={used}")
    return FloorPlanInstanceRead(**row.model_dump())


@router.get("/instances/{instance_id}/export-pdf")
def export_instance_pdf(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    _dbg_add("INFO", f"GET /instances/{instance_id}/export-pdf")
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    
    # Si l'instance n'a pas de plan, copier depuis le plan de base
    plan = row.data or {}
    if not plan.get("tables"):
        base = _get_or_create_base(session)
        if base and base.data:
            import copy
            plan = copy.deepcopy(base.data)
            logger.info("GET /instances/%s/export-pdf -> copied base plan with %d tables", instance_id, len(plan.get("tables") or []))
            _dbg_add("INFO", f"GET /instances/{instance_id}/export-pdf -> copied base plan with {len(plan.get('tables') or [])} tables")
    _plan, id_to_label = _assign_table_numbers(dict(plan), persist=False)
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    # 1) Reservations + assigned tables
    try:
        reservations = _load_reservations(session, row.service_date, row.service_label, instance=row)
        logger.info("export_instance_pdf -> loaded %d reservations from instance", len(reservations))
    except Exception as e:
        logger.error("export_instance_pdf -> failed to load reservations: %s", str(e))
        _dbg_add("ERROR", f"export_instance_pdf -> load reservations failed: {str(e)[:100]}")
        reservations = []
    _draw_reservations_page(c, reservations, (row.assignments or {}), id_to_label)
    c.showPage()
    # 2) Floor plan with labels and assignments
    _draw_plan_page(c, _plan, id_to_label, assignments=(row.assignments or {}))
    c.showPage()
    # 3) Numbered tables list
    _draw_table_list_page(c, id_to_label, _plan)
    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    headers = {"Content-Disposition": "attachment; filename=floorplan_instance.pdf"}
    logger.info("GET /instances/%s/export-pdf -> bytes=%d labels=%d", instance_id, len(pdf_bytes), len(id_to_label))
    _dbg_add("INFO", f"GET /instances/{instance_id}/export-pdf -> bytes={len(pdf_bytes)} labels={len(id_to_label)} reservations={len(reservations)}")
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

@router.post("/instances/{instance_id}/reset", response_model=FloorPlanInstanceRead)
def reset_instance(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    """Reset an instance: clear all table assignments and remove dynamically created tables.
    Keeps the existing base tables and labels intact.
    """
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    plan = row.data or {}
    tables = list(plan.get("tables") or [])
    # Remove tables marked as dynamic=True
    kept = [t for t in tables if not (t.get("dynamic") is True)]
    plan["tables"] = kept
    row.data = plan
    # Clear assignments
    row.assignments = {"tables": {}}
    # Persist JSON mutations
    try:
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(row, "data")
        flag_modified(row, "assignments")
    except Exception:
        pass
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("POST /instances/%s/reset -> kept_tables=%d", instance_id, len(kept))
    _dbg_add("INFO", f"RESET instance -> kept_tables={len(kept)}")
    return FloorPlanInstanceRead(**row.model_dump())


@router.get("/instances/{instance_id}/compare")
def compare_instance(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    """Compare reservations parsed from PDF (stored on instance) with current table assignments.
    Returns JSON with per-reservation assigned labels and a list of orphan assignments.
    """
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    # Load reservations from instance
    try:
        reservations = _load_reservations(session, row.service_date, row.service_label, instance=row)
    except Exception as e:
        logger.error("compare_instance -> failed to load reservations: %s", str(e))
        reservations = []
    # Build label map from plan snapshot
    plan = row.data or {}
    _plan, id_to_label = _assign_table_numbers(dict(plan), persist=False)
    tables = {str(t.get("id")): t for t in (plan.get("tables") or [])}
    # Build mapping res_id -> labels and assigned pax
    labels_by_res: Dict[str, List[str]] = {}
    assigned_pax_by_res: Dict[str, int] = {}
    orphan_assignments: List[Dict[str, Any]] = []
    tbl_map: Dict[str, Any] = (row.assignments or {}).get("tables", {})
    known_res_ids = set(str(r.id) for r in reservations)
    for tid, a in tbl_map.items():
        rid = str(a.get("res_id"))
        lbl = id_to_label.get(str(tid)) or str((tables.get(str(tid)) or {}).get("label") or "")
        if not lbl:
            # keep empty to signal missing numbering
            lbl = ""
        if rid in known_res_ids:
            labels_by_res.setdefault(rid, []).append(lbl)
            try:
                assigned_pax_by_res[rid] = assigned_pax_by_res.get(rid, 0) + int(a.get("pax", 0))
            except Exception:
                pass
        else:
            orphan_assignments.append({
                "table_id": str(tid),
                "label": lbl,
                "res_id": rid,
                "name": a.get("name"),
                "pax": a.get("pax", 0),
            })
    # Build per-reservation summary
    items = []
    for r in reservations:
        rid = str(r.id)
        labs = sorted([x for x in labels_by_res.get(rid, []) if x], key=lambda s: (s.startswith('R'), s))
        assigned_pax = int(assigned_pax_by_res.get(rid, 0))
        items.append({
            "id": rid,
            "arrival_time": str(getattr(r, "arrival_time", ""))[:5],
            "pax": int(getattr(r, "pax", 0)),
            "client_name": getattr(r, "client_name", ""),
            "labels": labs,
            "assigned_tables_count": len(labs),
            "assigned_pax": assigned_pax,
            "coverage_ok": assigned_pax >= int(getattr(r, "pax", 0)),
        })
    return {
        "reservations": items,
        "orphan_assignments": orphan_assignments,
        "counts": {
            "reservations": len(reservations),
            "assigned_tables": len(tbl_map),
            "orphan_assignments": len(orphan_assignments),
        }
    }


@router.put("/instances/{instance_id}", response_model=FloorPlanInstanceRead)
def update_instance(instance_id: uuid.UUID, payload: FloorPlanInstanceUpdate, session: Session = Depends(get_session)):
    _dbg_add("INFO", f"PUT /instances/{instance_id}")
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    data = payload.model_dump(exclude_unset=True)
    
    # Validate assignments if present
    if "assignments" in data and data["assignments"]:
        assignments = data["assignments"]
        if not isinstance(assignments, dict) or "tables" not in assignments:
            raise HTTPException(400, "Invalid assignments format: must have 'tables' key")
        tables_map = assignments.get("tables", {})
        if not isinstance(tables_map, dict):
            raise HTTPException(400, "Invalid assignments.tables format: must be dict")
        for table_id, assignment in tables_map.items():
            if not isinstance(assignment, dict):
                raise HTTPException(400, f"Invalid assignment for table {table_id}: must be dict")
            required_keys = ["res_id", "name", "pax"]
            for key in required_keys:
                if key not in assignment:
                    raise HTTPException(400, f"Invalid assignment for table {table_id}: missing '{key}'")
    
    # Validate data if present
    if "data" in data and data["data"]:
        plan_data = data["data"]
        if not isinstance(plan_data, dict):
            raise HTTPException(400, "Invalid data format: must be dict")
        if "tables" in plan_data and not isinstance(plan_data["tables"], list):
            raise HTTPException(400, "Invalid data.tables format: must be list")
    
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("PUT /instances/%s -> updated keys=%s", instance_id, list(data.keys()))
    _dbg_add("INFO", f"PUT /instances/{instance_id} -> updated keys={list(data.keys())}")
    return FloorPlanInstanceRead(**row.model_dump())


@router.delete("/instances/{instance_id}")
def delete_instance(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    """Supprime une instance de floorplan."""
    _dbg_add("INFO", f"DELETE /instances/{instance_id}")
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    
    # Supprimer les réservations associées (si nécessaire)
    # Note: Si Reservation a une foreign key vers FloorPlanInstance avec cascade, SQLAlchemy gère automatiquement
    # Sinon, il faut supprimer manuellement:
    # session.exec(delete(Reservation).where(Reservation.instance_id == instance_id))
    
    session.delete(row)
    session.commit()
    logger.info("DELETE /instances/%s -> deleted", instance_id)
    _dbg_add("INFO", f"DELETE /instances/{instance_id} -> deleted successfully")
    return {"message": "Instance deleted", "id": str(instance_id)}


@router.post("/instances/{instance_id}/auto-assign", response_model=FloorPlanInstanceRead)
def auto_assign(instance_id: uuid.UUID, session: Session = Depends(get_session)):
    print("=" * 80)
    print("🔥 AUTO-ASSIGN VERSION 2.0 - WITH ANTI-REUSE FIX 🔥")
    print("=" * 80)
    _dbg_add("INFO", "🔥 AUTO-ASSIGN V2.0 - ANTI-REUSE FIX")
    _dbg_add("INFO", f"POST /instances/{instance_id}/auto-assign")
    row = session.get(FloorPlanInstance, instance_id)
    if not row:
        raise HTTPException(404, "Instance not found")
    
    # Utiliser les réservations stockées dans l'instance (parsées du PDF)
    # au lieu de charger depuis la table reservation principale
    res_data = (row.reservations or {}).get("items", [])
    if not res_data:
        logger.error("POST /instances/%s/auto-assign -> no reservations in instance, import PDF first", instance_id)
        _dbg_add("ERROR", f"POST /instances/{instance_id}/auto-assign -> no reservations, import PDF first")
        raise HTTPException(400, "Aucune réservation trouvée. Importez d'abord un PDF de réservations via l'interface.")
    
    # Convertir les données dict en objets Reservation pour compatibilité avec _auto_assign
    from types import SimpleNamespace
    reservations = []
    for idx, item in enumerate(res_data):
        # IMPORTANT: NE PAS régénérer les IDs si ils existent déjà (créés par import-pdf)
        # Utiliser l'ID existant pour maintenir la cohérence
        res_id = item.get("id")
        if not res_id:
            # Fallback: générer un ID seulement si absent
            import hashlib
            content = f"{idx}_{item.get('client_name', '')}_{item.get('pax', 0)}_{item.get('arrival_time', '')}"
            hash_val = hashlib.md5(content.encode()).hexdigest()
            res_id = str(uuid.UUID(hash_val))
            item["id"] = res_id
        
        res = SimpleNamespace(
            id=res_id,
            client_name=item.get("client_name", "Client"),
            pax=int(item.get("pax", 0)),
            arrival_time=dtime.fromisoformat(item.get("arrival_time", "12:00") + (":00" if len(item.get("arrival_time", "12:00")) == 5 else ""))
        )
        reservations.append(res)
    
    # Mettre à jour les IDs dans row.reservations pour cohérence
    row.reservations = {"items": res_data}
    
    # Si l'instance n'a pas de plan, copier depuis le plan de base
    plan = row.data or {}
    if not plan.get("tables"):
        base = _get_or_create_base(session)
        if base and base.data:
            import copy
            plan = copy.deepcopy(base.data)
            tables = plan.get("tables") or []
            fixed_count = sum(1 for t in tables if t.get("kind") == "fixed" or t.get("locked"))
            rect_count = sum(1 for t in tables if t.get("kind") == "rect")
            round_count = sum(1 for t in tables if t.get("kind") == "round")
            logger.info("POST /instances/%s/auto-assign -> copied base plan: %d tables (fixed=%d rect=%d round=%d)", instance_id, len(tables), fixed_count, rect_count, round_count)
            _dbg_add("INFO", f"POST /instances/{instance_id}/auto-assign -> copied base: {len(tables)} tables (fixed={fixed_count} rect={rect_count} round={round_count})")
    
    tables = plan.get("tables") or []
    tables_before_count = len(tables)  # Capturer AVANT auto-assign (plan modifié par référence)
    fixed_count = sum(1 for t in tables if t.get("kind") == "fixed" or t.get("locked"))
    rect_count = sum(1 for t in tables if t.get("kind") == "rect")
    round_count = sum(1 for t in tables if t.get("kind") == "round")
    print(f"POST /instances/{instance_id}/auto-assign -> BEFORE: reservations={len(reservations)} tables={tables_before_count} (fixed={fixed_count} rect={rect_count} round={round_count})")
    _dbg_add("INFO", f"POST /instances/{instance_id}/auto-assign -> BEFORE: reservations={len(reservations)} tables={tables_before_count} (fixed={fixed_count} rect={rect_count} round={round_count})")
    
    # Sauvegarder le plan avec les tables du base avant auto-assign
    row.data = plan
    row.assignments = _auto_assign(plan, reservations)
    
    # Le plan peut avoir été modifié par _auto_assign (tables créées dynamiquement)
    row.data = plan  # Important: sauvegarder le plan modifié
    tables_after = plan.get("tables", [])
    fixed_after = sum(1 for t in tables_after if t.get("kind") == "fixed" or t.get("locked"))
    rect_after = sum(1 for t in tables_after if t.get("kind") == "rect")
    round_after = sum(1 for t in tables_after if t.get("kind") == "round")
    tables_created = len(tables_after) - tables_before_count
    
    print(f"POST /instances/{instance_id}/auto-assign -> AFTER: tables={len(tables_after)} (fixed={fixed_after} rect={rect_after} round={round_after}) CREATED={tables_created}")
    _dbg_add("INFO", f"POST /instances/{instance_id}/auto-assign -> AFTER: tables={len(tables_after)} (fixed={fixed_after} rect={rect_after} round={round_after}) CREATED={tables_created}")
    
    if tables_created > 0:
        print(f"POST /instances/{instance_id}/auto-assign -> NEW TABLES CREATED:")
        for t in tables_after[tables_before_count:]:
            print(f"  - {t.get('id')}: {t.get('kind')} {t.get('capacity', 0)} pax @ ({t.get('x')}, {t.get('y')})")
            _dbg_add("INFO", f"  NEW TABLE: {t.get('id')} {t.get('kind')} {t.get('capacity')}pax @({t.get('x')},{t.get('y')})")
    
    # CRITICAL: Force SQLAlchemy to detect JSON dict changes
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(row, "data")
    flag_modified(row, "assignments")
    session.add(row)
    session.commit()
    session.refresh(row)
    assigned_count = len((row.assignments or {}).get("tables", {}))
    logger.info("POST /instances/%s/auto-assign -> assigned_tables=%d (floorplan independent, not in main reservation table)", instance_id, assigned_count)
    _dbg_add("INFO", f"POST /instances/{instance_id}/auto-assign -> assigned_tables={assigned_count} (independent)")
    
    # Log summary for debugging
    unassigned = len(reservations) - assigned_count
    if unassigned > 0:
        logger.warning("POST /instances/%s/auto-assign -> %d reservations NOT assigned (no space or last resort)", instance_id, unassigned)
        _dbg_add("WARNING", f"POST /instances/{instance_id}/auto-assign -> {unassigned} reservations NOT assigned")
    
    return FloorPlanInstanceRead(**row.model_dump())


# ---- Import PDF ----

@router.post("/import-pdf")
def import_reservations_pdf(
    file: UploadFile = File(...),
    service_date: date = Form(...),
    service_label: Optional[str] = Form(None),
    create: bool = Form(False),  # Deprecated: kept for API compatibility but ignored
    session: Session = Depends(get_session),
):
    try:
        import pdfplumber
    except Exception:
        raise HTTPException(500, "pdfplumber non installé côté serveur")

    blob = file.file.read()
    out: List[Dict[str, Any]] = []
    import re
    import hashlib
    
    # Regex patterns
    re_time = re.compile(r"^\d{1,2}:\d{2}$")
    re_pax = re.compile(r"^\d{1,2}$")
    default_time = dtime(12, 30) if (service_label or "").lower() == "lunch" else dtime(19, 0)
    
    logger.info("POST /import-pdf -> starting PDF table extraction")
    _dbg_add("INFO", "POST /import-pdf -> extracting tables with pdfplumber")
    
    # Parser avec pdfplumber (extrait les tableaux)
    try:
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                logger.debug("POST /import-pdf -> page %d: found %d tables", page_num, len(tables))
                
                for table in tables:
                    if not table:
                        continue
                    
                    # Parcourir les lignes du tableau
                    for row in table:
                        if not row or len(row) < 3:
                            continue
                        
                        # Nettoyer la ligne
                        clean_row = [str(cell).strip() if cell else "" for cell in row]
                        
                        # Détecter colonnes heure/pax/nom (peuvent être dans différentes positions)
                        heure_idx = None
                        pax_idx = None
                        nom_idx = None
                        
                        for idx, cell in enumerate(clean_row[:7]):
                            if cell and re_time.match(cell):
                                heure_idx = idx
                            elif cell and re_pax.match(cell) and heure_idx is not None:
                                pax_idx = idx
                            elif cell and len(cell) >= 2 and any(c.isupper() for c in cell) and heure_idx is not None and pax_idx is not None:
                                if nom_idx is None and not cell.startswith('Commentaire'):
                                    nom_idx = idx
                                    break
                        
                        # Valider et extraire
                        if heure_idx is not None and pax_idx is not None and nom_idx is not None:
                            heure = clean_row[heure_idx]
                            pax_str = clean_row[pax_idx]
                            nom = clean_row[nom_idx]
                            
                            try:
                                pax = int(pax_str)
                                if 1 <= pax <= 30 and nom and len(nom) >= 2:
                                    # Nettoyer le nom (prendre première ligne, retirer téléphone)
                                    nom_clean = nom.split('\n')[0] if '\n' in nom else nom
                                    nom_clean = nom_clean.split('Téléphone')[0].strip()
                                    
                                    # Filtrer mots-clés commentaires
                                    if nom_clean.lower() not in ['commentaire', 'confirmé', 'web', 'google', 'heure', 'pax', 'client']:
                                        # Parser l'heure
                                        try:
                                            hh, mm = heure.split(":")
                                            arrival_time = dtime(int(hh), int(mm))
                                        except:
                                            arrival_time = default_time
                                        
                                        # Générer ID déterministe
                                        h = hashlib.md5(f"{service_date}_{heure}_{pax}_{nom_clean}".encode()).hexdigest()
                                        res_id = str(uuid.UUID(h[:32]))
                                        
                                        out.append({
                                            "id": res_id,
                                            "arrival_time": arrival_time.isoformat(),
                                            "pax": pax,
                                            "client_name": nom_clean
                                        })
                            except ValueError:
                                pass
    
    except Exception as e:
        logger.error("POST /import-pdf -> PDF extraction failed: %s", str(e))
        _dbg_add("ERROR", f"POST /import-pdf -> extraction failed: {str(e)[:200]}")
        raise HTTPException(400, f"Erreur lors de l'extraction PDF: {str(e)[:100]}")
    
    parsed_count = len(out)
    _dbg_add("INFO", f"POST /import-pdf -> parsed={parsed_count} reservations")
    
    if parsed_count == 0:
        logger.error("POST /import-pdf -> NO RESERVATIONS PARSED!")
        _dbg_add("ERROR", "NO RESERVATIONS PARSED!")
        raise HTTPException(400, "Aucune réservation trouvée dans le PDF. Vérifiez le format.")
    
    # NOTE: L'outil floorplan est complètement indépendant.
    # Il ne crée JAMAIS de réservations dans la table principale.
    # Les données parsées sont stockées dans l'instance pour usage temporaire.
    
    # Trouver ou créer l'instance pour ce service
    from sqlmodel import select
    stmt = select(FloorPlanInstance).where(
        FloorPlanInstance.service_date == service_date
    )
    if service_label:
        stmt = stmt.where(FloorPlanInstance.service_label == service_label)
    instance = session.exec(stmt).first()
    
    if instance:
        # Stocker les réservations parsées dans l'instance
        instance.reservations = {"items": out}
        instance.updated_at = datetime.utcnow()
        session.add(instance)
        session.commit()
        logger.info("POST /import-pdf -> stored %d reservations in instance %s", len(out), instance.id)
        _dbg_add("INFO", f"POST /import-pdf -> stored in instance {instance.id}")
    else:
        logger.warning("POST /import-pdf -> no instance found for %s/%s, reservations not stored", service_date, service_label)
        _dbg_add("WARNING", f"POST /import-pdf -> no instance found, create one first")
    
    return {"parsed": out, "message": f"Parsed {len(out)} reservations from PDF (stored in instance)"}
