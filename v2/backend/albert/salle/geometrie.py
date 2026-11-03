"""Géométrie du plan de salle : numérotation des tables, capacités, collisions, recherche de place.

Repris de l'ancienne version (app/backend/routers/floorplan.py), qui a fait ses preuves en
service ; seuls les journaux de débogage en mémoire ont été remplacés par des logs normaux.
"""
from __future__ import annotations

import logging
from datetime import time as dtime
from typing import Any, Dict, List, Optional, Tuple

from ..domain.erreurs import ErreurMetier

journal = logging.getLogger("albert.salle")


def _trace(_niveau: str, message: str) -> None:
    journal.debug(message)

def _numbering_kind(t: Dict[str, Any]) -> str:
    """Family a table is numbered and drawn as.

    Numbering follows the *kind*, never the lock state: locking a rectangle
    keeps it out of the auto-assign pool but it is still a rectangle, so it
    must keep a T label. Deriving this in one place stops the numbering and the
    PDF renderer from disagreeing — a mismatch used to blank the label.
    """
    kind = str(t.get("kind") or "").lower()
    if kind in ("fixed", "rect", "round", "sofa", "standing"):
        return kind
    # Legacy plans: a table with no kind was drawn as a rectangle, and a locked
    # one was numbered alongside the fixed tables.
    return "fixed" if t.get("locked") is True else "rect"


def _label_sort_key(label: str) -> Tuple[int, int, str]:
    """Natural order for table labels: 1 < 2 < 10, and T2 < T10."""
    s = str(label or "")
    families = {"": 0, "T": 1, "R": 2, "C": 3, "D": 4}
    prefix = s[:1].upper() if s[:1].isalpha() else ""
    digits = s[1:] if prefix else s
    try:
        return (families.get(prefix, 5), int(digits), s)
    except ValueError:
        return (families.get(prefix, 5), 10**6, s)


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
    # Separate pools — each table belongs to exactly one family, so a table can
    # never consume a number in one sequence and be labelled from another.
    fixed = [t for t in tables if _numbering_kind(t) == "fixed"]
    rects = [t for t in tables if _numbering_kind(t) == "rect"]
    rounds = [t for t in tables if _numbering_kind(t) == "round"]
    sofas = [t for t in tables if _numbering_kind(t) == "sofa"]
    standings = [t for t in tables if _numbering_kind(t) == "standing"]
    # Sort: gauche→droite (x ASC), puis bas→haut (y DESC)
    def key_table(t):
        x = float(t.get("x") or 0)
        y = float(t.get("y") or 0)
        return (x, -y)  # Tri: x croissant (gauche en premier), puis y décroissant (bas en premier)
    
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


def renumeroter(plan: Dict[str, Any], table_ids: List[str], prefixe: str = "", debut: int = 1) -> Dict[str, Any]:
    """Numérotation manuelle des tables choisies, dans l'ordre donné."""
    ids = [str(x) for x in (table_ids or [])]
    if not ids:
        raise ErreurMetier("champ_obligatoire", "Choisir au moins une table.")
    if debut is None or int(debut) < 0:
        raise ErreurMetier("valeur_non_permise", "Numéro de départ invalide.")
    prefix = str(prefixe or "")
    start = int(debut)
    tables: List[Dict[str, Any]] = list(plan.get("tables") or [])
    by_id: Dict[str, Dict[str, Any]] = {str(t.get("id")): t for t in tables}
    for i, tid in enumerate(ids):
        t = by_id.get(tid)
        if not t:
            continue
        n = start + i
        t["label"] = f"{prefix}{n}" if prefix else str(n)
    plan["tables"] = tables
    return plan


def _parse_arrival_time(value: Any, default: dtime = dtime(12, 0)) -> dtime:
    """Best-effort HH:MM / HH:MM:SS parsing; never raises.

    Reservations come from PDF parsing, so a missing or malformed time must
    downgrade to a default rather than fail the whole service assignment.
    """
    if isinstance(value, dtime):
        return value
    text = str(value or "").strip()
    if not text:
        return default
    if len(text) == 5:
        text = f"{text}:00"
    try:
        return dtime.fromisoformat(text[:8])
    except ValueError:
        return default



def _classify_service_label(t: dtime) -> str:
    return "lunch" if t.hour < 17 else "dinner"



def _capacity_for_table(tbl: Dict[str, Any]) -> int:
    cap = int(tbl.get("capacity") or 0)
    if cap > 0:
        return cap
    # Fallback defaults, keyed on the same family as the numbering and the
    # canvas. Lock state must not change the assumed capacity: a locked
    # rectangle still seats 6, and showing 6 in the editor while the engine
    # counted 4 silently under-filled the room.
    return {"rect": 6, "round": 10, "fixed": 4, "sofa": 5, "standing": 8}.get(_numbering_kind(tbl), 2)


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


def _find_spot_for_table(plan: Dict[str, Any], shape: str, w: float = 120, h: float = 60, r: float = 50, require_rect_zone: bool = False, prefer_right: bool = False, prefer_center: bool = False, prefer_center_y: bool = False, prefer_vertical: bool = False) -> Optional[Dict[str, float]]:
    """Find spot for table. shape can be: rect, round, sofa, standing.
    prefer_vertical=True: portrait orientation (w narrow, h tall), placed on the right wall, no T-zone required.
    """
    room = (plan.get("room") or {"width": 0, "height": 0})
    gw = int(room.get("grid") or 50)
    W = int(room.get("width") or 0)
    H = int(room.get("height") or 0)
    round_zones = plan.get("round_only_zones", [])  # Zones R (rondes uniquement)
    rect_zones = plan.get("rect_only_zones", [])    # Zones T (rectangulaires uniquement)

    # ── Vertical placement (portrait orientation, right wall) ──────────────────
    if prefer_vertical and shape == "rect":
        # w stays narrow (≈120), h is tall. Scan from right edge, top to bottom.
        margin = max(gw, 10)
        step = max(1, gw // 2)
        # x candidates: from right edge leftward
        x_candidates = list(range(max(0, int(W - w - margin)), max(0, int(W // 2)), -step))
        if not x_candidates:
            x_candidates = [max(0, int(W - w - margin))]
        # y candidates: prefer vertically centered, then top-to-bottom
        best_y = max(0, int((H - h) / 2))
        y_up = list(range(best_y, -1, -step))
        y_down = list(range(best_y + step, max(0, int(H - h)), step))
        y_candidates: list = []
        for i in range(max(len(y_up), len(y_down))):
            if i < len(y_up):
                y_candidates.append(y_up[i])
            if i < len(y_down):
                y_candidates.append(y_down[i])
        for xx in x_candidates:
            for yy in y_candidates:
                cand = {"x": float(xx), "y": float(yy), "w": float(w), "h": float(h)}
                t = {"id": "_probe", **cand}
                if not _table_collides(plan, t, existing_tables=plan.get("tables") or []):
                    return cand
        return None
    
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
    
    # If a rect spot must be inside a T zone, try biased placement, then scan inside each T zone
    if require_rect_zone and shape == "rect":
        if not rect_zones:
            return None
        # Optionally sort zones from rightmost to leftmost to bias to the right
        zones_iter = list(rect_zones)
        if prefer_right:
            zones_iter.sort(key=lambda z: float(z.get("x", 0)) + float(z.get("w", 0)), reverse=True)
        # try preferred placement in each rect-only zone
        for zone in zones_iter:
            zx, zy, zw, zh = zone.get("x", 0), zone.get("y", 0), zone.get("w", 0), zone.get("h", 0)
            if prefer_right:
                # right-aligned, vertically centered
                cx, cy = float(zx + zw - w), float(zy + zh / 2.0)
                cand = {"x": float(cx), "y": float(cy - h / 2.0), "w": float(w), "h": float(h)}
            elif prefer_center:
                # centered in zone
                cx, cy = float(zx + (zw - w) / 2.0), float(zy + zh / 2.0)
                cand = {"x": float(cx), "y": float(cy - h / 2.0), "w": float(w), "h": float(h)}
            else:
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
        for zone in zones_iter:
            zx, zy, zw, zh = zone.get("x", 0), zone.get("y", 0), zone.get("w", 0), zone.get("h", 0)
            max_y = max(0, int((zy + zh) - h))
            max_x = max(0, int((zx + zw) - w))
            step = max(1, (gw // 2) if (prefer_right or prefer_center or prefer_center_y) else gw)
            if prefer_center_y:
                start_y = int(zy + max(0, (zh - h)) / 2.0)
                up = list(range(start_y, int(zy) - 1, -step))
                down = list(range(start_y + step, int(max_y), step))
                y_iter: List[int] = []
                L = max(len(up), len(down))
                for i in range(L):
                    if i < len(up):
                        y_iter.append(up[i])
                    if i < len(down):
                        y_iter.append(down[i])
            else:
                y_iter = list(range(int(zy), max_y, step))
            if prefer_right:
                x_iter = list(range(int(max_x), int(zx) - 1, -step))
            elif prefer_center:
                # build x positions from center outwards
                start = int(zx + max(0, (zw - w)) / 2.0)
                left = list(range(start, int(zx) - 1, -step))
                right = list(range(start + step, int(max_x), step))
                # interleave left and right
                x_iter = []
                L = max(len(left), len(right))
                for i in range(L):
                    if i < len(left):
                        x_iter.append(left[i])
                    if i < len(right):
                        x_iter.append(right[i])
            else:
                x_iter = list(range(int(zx), int(max_x), step))
            for yy in y_iter:
                for xx in x_iter:
                    cand = {"x": float(xx), "y": float(yy), "w": float(w), "h": float(h)}
                    t = {"id": "_probe", **cand}
                    if not _table_collides(plan, t, existing_tables=plan.get("tables") or []):
                        return cand
        return None
    # scan grid row by row (default)
    is_circular = shape in ("round", "standing")
    y_range = range(0, max(0, H - (int(h) if not is_circular else int(r))), max(1, gw))
    if prefer_right and shape == "rect":
        x_range = range(max(0, int(W - (int(w)))), -1, -max(1, gw))
    else:
        x_range = range(0, max(0, W - (int(w) if not is_circular else int(r))), max(1, gw))
    for yy in y_range:
        for xx in x_range:
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
