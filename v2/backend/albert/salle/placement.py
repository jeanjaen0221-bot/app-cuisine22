"""Placement automatique des réservations d'un service sur le plan de salle.

Repris de l'ancienne version (règles éprouvées : petites tables fixes d'abord avec le stock de chaises,
grands groupes en table longue à droite ou verticale, tables rondes en dernier recours).
Entrée : plan (dict, modifié sur place quand des tables sont ajoutées) et réservations
(objets avec id, client_name, pax, arrival_time).
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import time as dtime
from typing import Any, Dict, List, Optional

from .geometrie import _capacity_for_table, _find_spot_for_table

journal = logging.getLogger("albert.salle")


def _trace(_niveau: str, message: str) -> None:
    journal.debug(message)


def placer(plan_data: Dict[str, Any], reservations: List[Any]) -> Dict[str, Any]:
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
    
    rect_dynamic_created = 0
    round_dynamic_created = 0

    # ── Seuils configurables (plan_data.large_table_config) ──────────────────────
    _cfg = plan_data.get("large_table_config") or {}
    pax_threshold_right    = int(_cfg.get("pax_threshold_right", 10))
    pax_threshold_vertical = int(_cfg.get("pax_threshold_vertical", 20))
    vertical_span_max      = int(_cfg.get("vertical_span_max", 7))
    _trace("INFO", f"large_table_config: seuil_droite={pax_threshold_right} seuil_vertical={pax_threshold_vertical} span_max_v={vertical_span_max}")

    # Sort reservations largest first to minimize waste; tie-breaker by arrival time
    groups = sorted(reservations, key=lambda r: (-int(r.pax), r.arrival_time or dtime(0, 0)))

    # ---- Service load heuristic (aérer vs optimiser) ----
    # Heuristic goal:
    # - calm service -> allow more comfort (more spare seats), and allow 2 rect tables "collées" for 12/14 pax
    # - busy service -> tighter fit to save tables/stock
    try:
        total_pax = sum(int(r.pax or 0) for r in reservations)
    except Exception:
        total_pax = 0
    try:
        fixed_cap = int(plan_data.get("fixed_chair_stock", 28))
    except Exception:
        fixed_cap = 28
    try:
        rect_cap = sum(max(6, int(t.get("capacity") or 6)) for t in rects)
    except Exception:
        rect_cap = 0
    try:
        round_cap = sum(int(_capacity_for_table(t)) for t in rounds)
    except Exception:
        round_cap = 0
    approx_total_cap = max(1, fixed_cap + rect_cap + round_cap)
    load_ratio = float(total_pax) / float(approx_total_cap)
    # thresholds tuned for this room: <55% calm, >75% busy
    seat_mode = "aerer" if load_ratio < 0.55 else ("optimiser" if load_ratio > 0.75 else "normal")
    _trace("INFO", f"AUTO-ASSIGN mode={seat_mode} load_ratio={load_ratio:.2f} pax={total_pax} cap≈{approx_total_cap}")

    assignments_by_table: Dict[str, Dict[str, Any]] = {}
    alerts: List[str] = []
    small_on_nonfixed = 0
    unplaced_count = 0  # Compter les réservations non placées
    fixed_chairs_used = 0

    def _assign_tables_to_reservation(res: Any, tbls: List[Dict[str, Any]], total: int) -> None:
        """Assign a single reservation across multiple tables (collées).
        For optimiser: pack as much as possible on first table(s).
        For aérer: distribute more evenly when possible.
        """
        remaining = int(total)

        # Compute per-table effective capacity (rect can extend to 8)
        caps: List[int] = []
        for t in tbls:
            cap = int(_capacity_for_table(t))
            if t.get("kind") == "rect":
                cap = min(8, cap + 2)
            caps.append(max(0, cap))

        if seat_mode == "aerer" and len(tbls) >= 2:
            # target near-even distribution while respecting caps
            target_each = max(1, int(math.ceil(remaining / float(len(tbls)))))
            for idx, t in enumerate(tbls):
                cap = caps[idx]
                take = min(cap, max(0, min(target_each, remaining)))
                assignments_by_table.setdefault(t.get("id"), {"res_id": str(res.id), "name": (res.client_name or "").upper(), "pax": take})
                remaining -= take
            # if still remaining, pack the rest
            for idx, t in enumerate(tbls):
                if remaining <= 0:
                    break
                already = int(assignments_by_table.get(t.get("id"), {}).get("pax") or 0)
                cap = caps[idx]
                add = min(cap - already, remaining)
                if add > 0:
                    assignments_by_table[t.get("id")]["pax"] = already + add
                    remaining -= add
        else:
            # optimiser/normal: pack first tables
            for idx, t in enumerate(tbls):
                if remaining <= 0:
                    break
                cap = caps[idx]
                take = min(cap, remaining)
                assignments_by_table.setdefault(t.get("id"), {"res_id": str(res.id), "name": (res.client_name or "").upper(), "pax": take})
                remaining -= take

        # Remove from pools (safety)
        for t in tbls:
            avail_fixed.pop(t.get("id"), None)
            avail_rects.pop(t.get("id"), None)
            avail_rounds.pop(t.get("id"), None)
            avail_sofas.pop(t.get("id"), None)
            avail_standings.pop(t.get("id"), None)

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
            journal.debug("prepass fixed -> res=%s pax=%s table=%s cap=%s used=%s/%s", r.id, r.pax, best_fixed.get("id"), _capacity_for_table(best_fixed), fixed_chairs_used, fixed_chair_stock)
            _trace("DEBUG", f"prepass fixed -> res={r.id} pax={r.pax} table={best_fixed.get('id')} used={fixed_chairs_used}/{fixed_chair_stock}")
        except Exception:
            pass

    # Pre-checks
    try:
        rect_only = plan_data.get("rect_only_zones") or []
        if not rect_only:
            _trace("WARNING", "Aucune zone T définie (rect_only_zones vide) — le placement droite/centre sera limité")
            alerts.append("Aucune zone T définie — placement droite/centre limité")
    except Exception:
        pass

    def take_table(pool: Dict[str, Dict[str, Any]], predicate=None, sort_key=None) -> Optional[Dict[str, Any]]:
        items = list(pool.values())
        if predicate:
            items = [x for x in items if predicate(x)]
        # Filter out already assigned tables
        items = [t for t in items if t.get("id") not in assignments_by_table]
        if not items:
            return None
        # choose smallest capacity that fits
        if sort_key is not None:
            items.sort(key=sort_key)
        else:
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

        # ── EARLY PASS : grands groupes → placement prioritaire droite/vertical ──
        # > pax_threshold_vertical → table portrait (vertical) à droite du plan
        if int(r.pax) > pax_threshold_vertical and rect_dynamic_created < max_rect_dynamic:
            total = int(r.pax)
            h_seg, gap = 60, 10
            needed = min(vertical_span_max, math.ceil(total / 6))
            h_total = needed * h_seg + (needed - 1) * gap
            w_total = 120
            cap = 6 * needed
            if cap >= total:
                spot = _find_spot_for_table(plan_data, "rect", w=w_total, h=h_total, prefer_vertical=True, prefer_right=True)
                if spot:
                    new_id = str(uuid.uuid4())
                    new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed, "orientation": "vertical"}
                    (plan_data.setdefault("tables", [])).append(new_tbl)
                    assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": total})
                    rect_dynamic_created += 1
                    placed = True
                    _trace("DEBUG", f"assign dynamic-vertical (early) -> res={r.id} pax={r.pax} table={new_id} cap={cap} span={needed} h={h_total}")
                else:
                    _trace("WARNING", f"No space for vertical table for {r.client_name} ({int(r.pax)}p), falling through to horizontal")

        # > pax_threshold_right (mais ≤ pax_threshold_vertical) → grande table horizontale à droite (T zone)
        if not placed and int(r.pax) > pax_threshold_right and rect_dynamic_created < max_rect_dynamic:
            total = int(r.pax)
            needed = min(4, math.ceil(total / 6))
            width = needed * 120 + (needed - 1) * 10
            cap = 6 * needed
            try:
                if math.ceil(total / 6) > 4:
                    msg = f"Groupe {total}p dépasse la capacité rect dynamique max (24p, span 4)."
                    _trace("WARNING", msg)
                    alerts.append(msg)
            except Exception:
                pass
            try:
                z_ok = any((float(z.get('w',0)) >= width and float(z.get('h',0)) >= 60) for z in (plan_data.get('rect_only_zones') or []))
                if not z_ok:
                    msg = f"Zone T trop étroite pour span {needed} (largeur requise {width}px)."
                    _trace("INFO", msg)
                    alerts.append(msg)
            except Exception:
                pass
            if cap >= total:
                spot = _find_spot_for_table(plan_data, "rect", w=width, h=60, require_rect_zone=True, prefer_right=True, prefer_center_y=True)
                if spot:
                    new_id = str(uuid.uuid4())
                    new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed}
                    (plan_data.setdefault("tables", [])).append(new_tbl)
                    assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": total})
                    rect_dynamic_created += 1
                    placed = True
                    _trace("DEBUG", f"assign dynamic-large-rect (early) -> res={r.id} pax={r.pax} table={new_id} cap={cap} span={needed}")
                else:
                    _trace("WARNING", f"No space for early large rect in T for {r.client_name} ({int(r.pax)}p)")
                    alerts.append(f"Pas d'espace pour grande rect (early) pour {r.client_name} ({int(r.pax)}p)")
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
                journal.debug("assign fixed -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_fixed.get("id"), _capacity_for_table(best_fixed))
                _trace("DEBUG", f"assign fixed -> res={r.id} pax={r.pax} table={best_fixed.get('id')}")
            except Exception as e:
                journal.warning("assign fixed -> log failed: %s", str(e))
                pass
        if placed:
            continue

        # 2a) Removed pair preference for 7-8 pax: keep group together on a single rect (with extension to 8 as last resort)

        # 2) Rect single table (6 or 8 with head) best-fit (extension is last resort) for up to 8 pax
        # For groups <=4, only consider rects if fixed stock is exhausted or no fixed tables remain
        rect_allowed = True
        if int(r.pax) <= 4:
            rect_allowed = (fixed_chairs_used + int(r.pax) > fixed_chair_stock) or (len(avail_fixed) == 0)

        # Calm service: allow 2 rect tables "collées" for 9-14 pax (12/14) before creating a dynamic cluster
        if rect_allowed and seat_mode == "aerer" and 9 <= int(r.pax) <= 14:
            pair = take_best_rect_combo(int(r.pax))
            if pair:
                _assign_tables_to_reservation(r, pair, int(r.pax))
                placed = True
                try:
                    _trace("INFO", f"assign rect-collées -> res={r.id} pax={int(r.pax)} tables={[t.get('id') for t in pair]}")
                except Exception:
                    pass

        if placed:
            continue

        if rect_allowed:
            def rect_can_fit(t):
                cap = _capacity_for_table(t)
                # For small groups (<=8), avoid oversized rects (e.g., 12)
                if int(r.pax) <= 8 and cap > 8:
                    return False
                # Allow +2 head extension up to 8 for a single rectangle
                cap_ext = min(8, cap + 2)
                return cap_ext >= r.pax

            def rect_center_pref_key(t):
                cap = _capacity_for_table(t)
                cap_ext = min(8, cap + 2) if t.get("kind") == "rect" else cap
                spare = int(cap_ext) - int(r.pax)
                # optimiser: prefer minimal spare
                # aérer: prefer more spare only for 7-8 pax; for <=6 pax keep best-fit to avoid wasting 8-seaters
                if seat_mode == "aerer" and int(r.pax) >= 7:
                    spare_key = -spare
                else:
                    spare_key = spare
                try:
                    if int(r.pax) <= 8:
                        zones = plan_data.get("rect_only_zones") or []
                        tx = float(t.get("x") or 0.0)
                        ty = float(t.get("y") or 0.0)
                        tw = float(t.get("w") or 120.0)
                        th = float(t.get("h") or 60.0)
                        cx = tx + tw / 2.0
                        cy = ty + th / 2.0
                        # distance of table center from the LEFT edge of its T zone (prefer smaller = plus à gauche dans T)
                        dist = cx
                        for z in zones:
                            zx = float(z.get("x", 0.0)); zy = float(z.get("y", 0.0)); zw = float(z.get("w", 0.0)); zh = float(z.get("h", 0.0))
                            if cx >= zx and cx <= zx + zw and cy >= zy and cy <= zy + zh:
                                dist = cx - zx
                                break
                        return (spare_key, cap, dist)
                except Exception:
                    pass
                return (spare_key, cap, float(t.get("x") or 0.0))

            best_rect = take_table(avail_rects, predicate=rect_can_fit, sort_key=rect_center_pref_key)
            if best_rect:
                # seat up to extended capacity for a single rectangle
                pax_on_table = min(int(r.pax), min(8, _capacity_for_table(best_rect) + 2))
                assignments_by_table.setdefault(best_rect.get("id"), {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": pax_on_table})
                if int(r.pax) <= 4:
                    small_on_nonfixed += 1
                placed = True
                try:
                    journal.debug("assign rect -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_rect.get("id"), _capacity_for_table(best_rect))
                    _trace("DEBUG", f"assign rect -> res={r.id} pax={r.pax} table={best_rect.get('id')}")
                except Exception as e:
                    journal.warning("assign rect -> log failed: %s", str(e))
                    pass
            else:
                # Not strictly an error: will try dynamic. But warn if a suitable rect exists but blocked by collisions/locks.
                _trace("INFO", f"No existing rect chosen for {r.client_name} ({int(r.pax)}p), will try dynamic if needed")
        if placed:
            continue

        # 2b) Fallback : grands groupes > seuil_droite → grande rect dynamique (horizontal T zone, ou vertical si > seuil_vertical)
        if int(r.pax) > pax_threshold_right and rect_dynamic_created < max_rect_dynamic:
            total = int(r.pax)
            # Vertical (portrait) si > seuil_vertical
            if total > pax_threshold_vertical:
                h_seg, gap = 60, 10
                needed = min(vertical_span_max, math.ceil(total / 6))
                h_total = needed * h_seg + (needed - 1) * gap
                cap = 6 * needed
                if cap >= total:
                    spot = _find_spot_for_table(plan_data, "rect", w=120, h=h_total, prefer_vertical=True, prefer_right=True)
                    if spot:
                        new_id = str(uuid.uuid4())
                        new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed, "orientation": "vertical"}
                        (plan_data.setdefault("tables", [])).append(new_tbl)
                        assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": total})
                        rect_dynamic_created += 1
                        placed = True
                        _trace("DEBUG", f"assign dynamic-vertical (fallback) -> res={r.id} pax={r.pax} table={new_id} cap={cap} span={needed}")
                    else:
                        _trace("WARNING", f"No vertical spot for {r.client_name} ({total}p), trying horizontal")
            # Horizontal (paysage) si ≤ seuil_vertical OU si vertical a échoué
            if not placed:
                needed = min(4, math.ceil(total / 6))
                width = needed * 120 + (needed - 1) * 10
                cap = 6 * needed
                try:
                    if math.ceil(total / 6) > 4:
                        msg = f"Groupe {total}p dépasse la capacité rect dynamique max (24p, span 4)."
                        _trace("WARNING", msg)
                        alerts.append(msg)
                except Exception:
                    pass
                try:
                    z_ok = any((float(z.get('w',0)) >= width and float(z.get('h',0)) >= 60) for z in (plan_data.get('rect_only_zones') or []))
                    if not z_ok:
                        msg = f"Zone T trop étroite pour span {needed} (largeur requise {width}px)."
                        _trace("INFO", msg)
                        alerts.append(msg)
                except Exception:
                    pass
                if cap >= total:
                    spot = _find_spot_for_table(plan_data, "rect", w=width, h=60, require_rect_zone=True, prefer_right=True, prefer_center_y=True)
                    if spot:
                        new_id = str(uuid.uuid4())
                        new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed}
                        (plan_data.setdefault("tables", [])).append(new_tbl)
                        assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": total})
                        rect_dynamic_created += 1
                        placed = True
                        _trace("DEBUG", f"assign dynamic-large-rect -> res={r.id} pax={r.pax} table={new_id} span={needed}")
                    else:
                        _trace("WARNING", f"No space for large rect in T for {r.client_name} ({int(r.pax)}p)")
                        alerts.append(f"Pas d'espace pour grande rect pour {r.client_name} ({int(r.pax)}p)")
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
                if int(r.pax) <= 4:
                    small_on_nonfixed += 1
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
                alerts.append(f"Dernier recours: table ronde pour {r.client_name} ({int(r.pax)}p)")
                placed = True
                try:
                    journal.debug("assign round -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_round.get("id"), _capacity_for_table(best_round))
                    _trace("DEBUG", f"assign round (last resort) -> res={r.id} pax={r.pax} table={best_round.get('id')}")
                except Exception as e:
                    journal.warning("assign round -> log failed: %s", str(e))
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
                    if int(r.pax) <= 4:
                        small_on_nonfixed += 1
                    alerts.append(f"Dernier recours: canapé pour {r.client_name} ({int(r.pax)}p)")
                    placed = True
                    try:
                        journal.debug("assign sofa -> res=%s pax=%s table=%s cap=%s", r.id, r.pax, best_sofa.get("id"), _capacity_for_table(best_sofa))
                        _trace("DEBUG", f"assign sofa (last resort) -> res={r.id} pax={r.pax} table={best_sofa.get('id')}")
                    except Exception as e:
                        journal.warning("assign sofa -> log failed: %s", str(e))
                        pass

        # 5) Create and place a new non-fixed table if still not placed (single large rect first)
        if not placed:
            unplaced_count += 1
            journal.debug(f"CREATING DYNAMIC TABLES for res={r.id} ({r.client_name}, {r.pax} pax) - no existing table available")
            _trace("INFO", f"CREATING DYNAMIC TABLES for {r.client_name} ({r.pax} pax) - stock: rect {max_rect_dynamic-rect_dynamic_created}/{max_rect_dynamic}, round {max_round_dynamic-round_dynamic_created}/{max_round_dynamic}")
            remaining = int(r.pax)
            created_any = False
            # Petits groupes (≤ seuil_droite) : rect simple centrée dans T
            if remaining <= pax_threshold_right:
                width = 120
                cap = 8  # 6 + head
                spot = _find_spot_for_table(plan_data, "rect", w=width, h=60, require_rect_zone=True, prefer_center=True, prefer_center_y=True)
                if spot and rect_dynamic_created < max_rect_dynamic and cap >= remaining:
                    new_id = str(uuid.uuid4())
                    new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": 1}
                    (plan_data.setdefault("tables", [])).append(new_tbl)
                    assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": remaining})
                    if int(r.pax) <= 4:
                        small_on_nonfixed += 1
                    remaining = 0
                    rect_dynamic_created += 1
                    created_any = True
                    journal.debug(f"✓ Created single rect (8 cap) {rect_dynamic_created}/{max_rect_dynamic}")
                    _trace("INFO", f"✓ Created single rect (cap 8) {rect_dynamic_created}/{max_rect_dynamic}")
                else:
                    _trace("WARNING", f"No space for small rect (8) in center of T for {r.client_name} ({int(r.pax)}p)")
                    alerts.append(f"Pas d'espace pour petite rect (8) pour {r.client_name} ({int(r.pax)}p)")
            else:
                # Grands groupes : vertical portrait si > seuil_vertical
                if remaining > pax_threshold_vertical and rect_dynamic_created < max_rect_dynamic:
                    h_seg, gap = 60, 10
                    needed_v = min(vertical_span_max, math.ceil(remaining / 6))
                    h_total = needed_v * h_seg + (needed_v - 1) * gap
                    cap_v = 6 * needed_v
                    if cap_v >= remaining:
                        spot = _find_spot_for_table(plan_data, "rect", w=120, h=h_total, prefer_vertical=True, prefer_right=True)
                        if spot:
                            new_id = str(uuid.uuid4())
                            new_tbl = {"id": new_id, "kind": "rect", "capacity": cap_v, **spot, "dynamic": True, "span": needed_v, "orientation": "vertical"}
                            (plan_data.setdefault("tables", [])).append(new_tbl)
                            assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": remaining})
                            remaining = 0
                            rect_dynamic_created += 1
                            created_any = True
                            journal.debug(f"✓ Created vertical rect {rect_dynamic_created}/{max_rect_dynamic} (span {needed_v}, h={h_total})")
                            _trace("INFO", f"✓ Created vertical rect {rect_dynamic_created}/{max_rect_dynamic} span={needed_v} h={h_total}")
                # Fallback horizontal (paysage) si vertical non applicable ou pas de place
                if remaining > 0 and rect_dynamic_created < max_rect_dynamic:
                    needed = min(4, math.ceil(remaining / 6))
                    width = needed * 120 + (needed - 1) * 10
                    cap = 6 * needed
                    try:
                        if math.ceil(remaining / 6) > 4:
                            msg = f"Groupe {remaining}p dépasse la capacité rect dynamique max (24p, span 4)."
                            _trace("WARNING", msg)
                            alerts.append(msg)
                    except Exception:
                        pass
                    try:
                        z_ok = any((float(z.get('w',0)) >= width and float(z.get('h',0)) >= 60) for z in (plan_data.get('rect_only_zones') or []))
                        if not z_ok:
                            msg = f"Zone T trop étroite pour span {needed} (largeur requise {width}px)."
                            _trace("INFO", msg)
                            alerts.append(msg)
                    except Exception:
                        pass
                    if cap >= remaining:
                        spot = _find_spot_for_table(plan_data, "rect", w=width, h=60, require_rect_zone=True, prefer_right=True, prefer_center_y=True)
                        if spot:
                            new_id = str(uuid.uuid4())
                            new_tbl = {"id": new_id, "kind": "rect", "capacity": cap, **spot, "dynamic": True, "span": needed}
                            (plan_data.setdefault("tables", [])).append(new_tbl)
                            assignments_by_table.setdefault(new_id, {"res_id": str(r.id), "name": (r.client_name or "").upper(), "pax": remaining})
                            remaining = 0
                            rect_dynamic_created += 1
                            created_any = True
                            journal.debug(f"✓ Created large rect table {rect_dynamic_created}/{max_rect_dynamic} (span {needed})")
                            _trace("INFO", f"✓ Created large rect {rect_dynamic_created}/{max_rect_dynamic} span={needed}")
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
                        journal.debug(f"✓ Created round table {round_dynamic_created}/{max_round_dynamic}")
                        _trace("INFO", f"✓ Created round {round_dynamic_created}/{max_round_dynamic}")
                        alerts.append(f"Dernier recours dynamique: table ronde créée pour {r.client_name} ({int(r.pax)}p)")
                    else:
                        journal.warning("Round 10 insufficient for %s (%d pax)", r.client_name, int(r.pax))
                        _trace("WARNING", f"Round 10 insufficient for {r.client_name} ({int(r.pax)} pax)")
                else:
                    journal.warning("No space found for new round table")
                    _trace("WARNING", "No space for new round table")
                    alerts.append("Impossible de placer une table ronde en dernier recours")
            if remaining <= 0 and created_any:
                placed = True
            elif remaining > 0:
                if (rect_dynamic_created) >= max_rect_dynamic:
                    journal.warning("⚠️ STOCK LIMIT REACHED: rect tables %d/%d (dynamic created)", rect_dynamic_created, max_rect_dynamic)
                    _trace("WARNING", f"STOCK LIMIT: rect {rect_dynamic_created}/{max_rect_dynamic}")
                    alerts.append(f"Stock rect dynamiques atteint: {rect_dynamic_created}/{max_rect_dynamic}")
                if (round_dynamic_created) >= max_round_dynamic:
                    journal.warning("⚠️ STOCK LIMIT REACHED: round tables %d/%d (dynamic created)", round_dynamic_created, max_round_dynamic)
                    _trace("WARNING", f"STOCK LIMIT: round {round_dynamic_created}/{max_round_dynamic}")
                    alerts.append(f"Stock rondes dynamiques atteint: {round_dynamic_created}/{max_round_dynamic}")

        # If not placed, leave unassigned; frontend will show conflict
        if not placed:
            journal.warning("UNPLACED reservation: %s (%s, %d pax) - no space found even after trying to create tables", r.id, r.client_name, r.pax)
            _trace("WARNING", f"UNPLACED: {r.client_name} ({r.pax} pax)")

    # Aggregate unassigned reservations as a final alert
    try:
        assigned_res_ids = {str(v.get("res_id")) for v in assignments_by_table.values()}
        unassigned = [r for r in reservations if str(r.id) not in assigned_res_ids]
        if len(unassigned) > 0:
            names = ", ".join((r.client_name or "").upper()[:18] for r in unassigned[:8])
            extra = "" if len(unassigned) <= 8 else f" (+{len(unassigned)-8} autres)"
            msg = f"{len(unassigned)} réservation(s) non assignée(s): {names}{extra}"
            _trace("WARNING", msg)
            alerts.append(msg)
        # Warn if small groups went to non-fixed while fixed stock remains
        if small_on_nonfixed > 0 and fixed_chairs_used < fixed_chair_stock:
            alerts.append(f"{small_on_nonfixed} groupe(s) 1–4 pax placés sur non-fixes alors qu'il restait des chaises fixes ({fixed_chairs_used}/{fixed_chair_stock})")
            _trace("WARNING", f"Small-on-nonfixed={small_on_nonfixed} with fixed chairs remaining {fixed_chairs_used}/{fixed_chair_stock}")
    except Exception:
        pass

    journal.debug(f"_auto_assign SUMMARY: {len(reservations)} reservations, {unplaced_count} tried dynamic, {len(assignments_by_table)} assignments | STOCK USED: rect {rect_dynamic_created}/{max_rect_dynamic}, round {round_dynamic_created}/{max_round_dynamic}")
    _trace("INFO", f"_auto_assign SUMMARY: {len(reservations)} res, {unplaced_count} tried dynamic, {len(assignments_by_table)} assigned | STOCK: rect {rect_dynamic_created}/{max_rect_dynamic}, round {round_dynamic_created}/{max_round_dynamic}")
    return {"tables": assignments_by_table, "alerts": alerts}
