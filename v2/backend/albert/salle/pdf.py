"""PDF du plan de salle : plan numéroté, liste des tables, liste du service avec les tables."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

from .geometrie import _capacity_for_table, _label_sort_key, _numbering_kind

journal = logging.getLogger("albert.salle")


def _trace(_niveau: str, message: str) -> None:
    journal.debug(message)


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
        # Same resolution as the numbering, so the sanitizer below can never
        # reject a label that _assign_table_numbers just produced.
        kind = _numbering_kind(t)
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

        # Determine pax/capacity to display (pax if assigned, otherwise capacity)
        pax_val: Optional[int] = None
        has_assignments = bool(assignments and isinstance(assignments.get("tables"), dict))
        if has_assignments:
            a = assignments["tables"].get(str(t.get("id")))
            if a and isinstance(a, dict):
                try:
                    pax_val = int(a.get("pax"))
                except Exception:
                    pax_val = None
        else:
            try:
                pax_val = int(_capacity_for_table(t))
            except Exception:
                try:
                    pax_val = int(t.get("capacity") or 0)
                except Exception:
                    pax_val = 0

        def draw_centered_table_text(cx: float, cy: float, lbl: str, pax: Optional[int]) -> None:
            if not lbl and (pax is None or pax == 0):
                return
            num_size = 10
            pax_size = 8
            c.setFillColor(colors.white)
            if lbl:
                c.setFont("Helvetica-Bold", num_size)
                c.drawCentredString(cx, cy + 3, str(lbl))
            if pax is not None and pax != 0:
                c.setFont("Helvetica", pax_size)
                c.drawCentredString(cx, cy - 8, f"{int(pax)} pl.")

        if kind in ("round", "standing") and t.get("r"):
            x = float(t.get("x") or 0)
            y = float(t.get("y") or 0)
            r = float(t.get("r") or 0)
            c.circle(tx(x), ty(y), scale * r, stroke=1, fill=1)
            draw_centered_table_text(tx(x), ty(y), lbl, pax_val)
        else:
            x = float(t.get("x") or 0)
            y = float(t.get("y") or 0)
            w = float(t.get("w") or 120)
            h = float(t.get("h") or 60)
            c.rect(tx(x), ty(y + h), scale * w, scale * h, stroke=1, fill=1)
            cx = tx(x + w / 2.0)
            cy = ty(y + h / 2.0)
            draw_centered_table_text(cx, cy, lbl, pax_val)

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
            journal.warning("_draw_table_list_page -> failed to get capacity for table %s: %s", t.get("id"), str(e))
            _trace("WARNING", f"_draw_table_list_page -> capacity error table={t.get('id')}: {str(e)[:50]}")
        kind = str(t.get("kind") or "")
        rows.append((lbl, cap, kind))
    # Sort by label natural (numbers first, then T, R, C, D)
    rows.sort(key=lambda r: _label_sort_key(r[0]))
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
    reservations: List[Any],
    assignments: Dict[str, Any],
    id_to_label: Dict[str, str],
) -> None:
    page_w, page_h = A4
    margin = 15 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, page_h - margin, "Liste du service avec numéros de table")
    y = page_h - margin - 10 * mm
    header_h = 7 * mm
    line_h = 6 * mm
    pad_x = 2.0

    def _wrap_text(text: str, max_w: float, font_name: str, font_size: float) -> List[str]:
        s = str(text or "").strip()
        if not s:
            return [""]
        words = s.split()
        lines: List[str] = []
        cur = ""
        for w in words:
            nxt = (cur + " " + w).strip() if cur else w
            if stringWidth(nxt, font_name, font_size) <= max_w:
                cur = nxt
                continue
            if cur:
                lines.append(cur)
            if stringWidth(w, font_name, font_size) <= max_w:
                cur = w
            else:
                part = w
                while part and stringWidth(part, font_name, font_size) > max_w:
                    cut = len(part)
                    while cut > 1 and stringWidth(part[:cut] + "…", font_name, font_size) > max_w:
                        cut -= 1
                    lines.append(part[:cut] + "…")
                    part = part[cut:]
                cur = part
        if cur:
            lines.append(cur)
        return lines if lines else [""]
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
    col_time_x = margin
    col_client_x = margin + 25 * mm
    col_pax_x = margin + 110 * mm
    col_tables_x = margin + 125 * mm
    pax_col_w = col_tables_x - col_pax_x
    c.drawString(col_time_x + pad_x, y, "Heure")
    c.drawString(col_client_x + pad_x, y, "Client")
    c.drawCentredString(col_pax_x + pax_col_w / 2.0, y, "Pax")
    c.drawString(col_tables_x + pad_x, y, "Table(s)")
    y -= header_h
    c.setFont("Helvetica", 9)
    col_client_w = col_pax_x - col_client_x - 4
    col_tables_w = (page_w - margin) - col_tables_x - 4
    for i, r in enumerate(rows):
        t = getattr(r, "arrival_time", None)
        tstr = str(t)[:5] if t else ""
        lst_raw = ", ".join(sorted(lab_by_res.get(str(r.id), []), key=_label_sort_key))

        client_lines = _wrap_text((r.client_name or "").upper(), col_client_w, "Helvetica", 9)
        tables_lines = _wrap_text(lst_raw, col_tables_w, "Helvetica", 9)
        row_lines = max(1, len(client_lines), len(tables_lines))
        row_h = row_lines * line_h

        if y - row_h < margin + 2 * line_h:
            c.showPage()
            # Redraw header on new page
            c.setFont("Helvetica-Bold", 10)
            y = page_h - margin - 10 * mm
            c.setFillColor(colors.whitesmoke)
            c.rect(margin - 2, y - 1.5, page_w - 2 * margin + 4, header_h, stroke=0, fill=1)
            c.setFillColor(colors.black)
            c.drawString(col_time_x + pad_x, y, "Heure")
            c.drawString(col_client_x + pad_x, y, "Client")
            c.drawCentredString(col_pax_x + pax_col_w / 2.0, y, "Pax")
            c.drawString(col_tables_x + pad_x, y, "Table(s)")
            y -= header_h
            c.setFont("Helvetica", 9)

        if i % 2 == 1:
            c.setFillColor(colors.Color(0.965, 0.965, 0.965))
            c.rect(margin - 2, y - row_h + 2, page_w - 2 * margin + 4, row_h, stroke=0, fill=1)
            c.setFillColor(colors.black)

        c.drawString(col_time_x + pad_x, y, tstr)
        c.drawRightString(col_tables_x - 2 * mm, y, str(r.pax or 0))

        for li in range(row_lines):
            yy = y - li * line_h
            if li < len(client_lines):
                c.drawString(col_client_x + pad_x, yy, client_lines[li])
            if li < len(tables_lines):
                c.drawString(col_tables_x + pad_x, yy, tables_lines[li])

        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.5)
        c.line(margin - 2, y - row_h + 2, page_w - margin + 2, y - row_h + 2)
        c.line(col_client_x, y + 3, col_client_x, y - row_h + 2)
        c.line(col_pax_x, y + 3, col_pax_x, y - row_h + 2)
        c.line(col_tables_x, y + 3, col_tables_x, y - row_h + 2)

        y -= row_h


# ---------------------------------------------------------------- documents complets

def _reservations_pdf(liste: List[Dict[str, Any]]) -> List[Any]:
    from datetime import time as dtime
    from types import SimpleNamespace

    sortie = []
    for r in liste:
        if r.get("doublon_de"):
            continue
        hh, mi = (int(x) for x in r["heure"].split(":"))
        sortie.append(SimpleNamespace(id=r["id"], client_name=r["nom"], pax=r["pax"], arrival_time=dtime(hh, mi)))
    return sortie


def pdf_plan(plan: Dict[str, Any], etiquettes: Dict[str, str]) -> bytes:
    import io

    tampon = io.BytesIO()
    c = pdfcanvas.Canvas(tampon, pagesize=A4)
    _draw_plan_page(c, plan, etiquettes)
    c.showPage()
    _draw_table_list_page(c, etiquettes, plan)
    c.showPage()
    c.save()
    return tampon.getvalue()


def pdf_service(plan: Dict[str, Any], etiquettes: Dict[str, str], affectations: Dict[str, Any],
                liste: List[Dict[str, Any]]) -> bytes:
    """Liste du service avec les numéros de table, puis le plan avec les couverts placés."""
    import io

    tampon = io.BytesIO()
    c = pdfcanvas.Canvas(tampon, pagesize=A4)
    _draw_reservations_page(c, _reservations_pdf(liste), affectations, etiquettes)
    c.showPage()
    _draw_plan_page(c, plan, etiquettes, assignments=affectations)
    c.showPage()
    c.save()
    return tampon.getvalue()


def pdf_annote(original: bytes, plan: Dict[str, Any], etiquettes: Dict[str, str], affectations: Dict[str, Any],
               liste: List[Dict[str, Any]], page_debut: int = 0, debut_y_mm: float = 95.0,
               hauteur_ligne_mm: float = 13.5, colonne_x_mm: float = 137.0) -> bytes:
    """Écrit les numéros de table dans la colonne du PDF de réservations d'origine, puis ajoute
    la liste et le plan. Les lignes du PDF sont supposées dans l'ordre (heure, nom) de l'import."""
    import io

    from pypdf import PdfReader, PdfWriter

    par_res: Dict[str, List[str]] = {}
    for table_id, a in (affectations.get("tables") or {}).items():
        lbl = etiquettes.get(table_id)
        if lbl:
            par_res.setdefault(str(a.get("res_id")), []).append(lbl)
    lignes = [r for r in liste if r.get("source") == "import"]
    lecteur = PdfReader(io.BytesIO(original))
    sortie = PdfWriter()
    i = 0
    for numero, page in enumerate(lecteur.pages):
        largeur, hauteur = float(page.mediabox.width), float(page.mediabox.height)
        calque = io.BytesIO()
        c = pdfcanvas.Canvas(calque, pagesize=(largeur, hauteur))
        y = hauteur - debut_y_mm * mm
        dessine = False
        if numero >= page_debut:
            while i < len(lignes):
                r = lignes[i]
                cle_res = r.get("doublon_de") or r["id"]
                texte = ", ".join(sorted(par_res.get(cle_res, []), key=_label_sort_key))
                if texte:
                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(colonne_x_mm * mm, y, texte)
                    dessine = True
                i += 1
                y -= hauteur_ligne_mm * mm
                if y < 15 * mm:
                    break
        c.save()
        if dessine:
            page.merge_page(PdfReader(io.BytesIO(calque.getvalue())).pages[0])
        sortie.add_page(page)
    for page in PdfReader(io.BytesIO(pdf_service(plan, etiquettes, affectations, liste))).pages:
        sortie.add_page(page)
    resultat = io.BytesIO()
    sortie.write(resultat)
    return resultat.getvalue()
