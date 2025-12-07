from __future__ import annotations
def _reservation_filename_variant(reservation: Reservation, variant: str) -> str:
    safe_client = str(reservation.client_name).replace(" ", "_")
    v = (variant or "").lower()
    if v not in ("cuisine", "salle", "both"):
        v = "cuisine"
    return os.path.join(PDF_DIR, f"fiche_{v}_{reservation.service_date}_{safe_client}_{reservation.id}.pdf")

import os
from datetime import date
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.units import cm

from .models import Reservation, ReservationItem, BillingInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.abspath(os.path.join(BASE_DIR, "../generated_pdfs"))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(PDF_DIR, exist_ok=True)


def _reservation_filename(reservation: Reservation) -> str:
    safe_client = str(reservation.client_name).replace(" ", "_")
    return os.path.join(PDF_DIR, f"fiche_{reservation.service_date}_{safe_client}_{reservation.id}.pdf")


def _day_filename(d: date) -> str:
    return os.path.join(PDF_DIR, f"fiches_{d}.pdf")


def _invoice_filename(reservation: Reservation) -> str:
    safe_client = str(reservation.client_name).replace(" ", "_")
    return os.path.join(PDF_DIR, f"facture_{reservation.service_date}_{safe_client}_{reservation.id}.pdf")


def _split_items(items: List[ReservationItem]):
    def norm(s: str) -> str:
        return s.lower().strip().replace("é", "e")
    entrees = [i for i in items if norm(i.type) in ["entree", "entrees"]]
    plats = [i for i in items if norm(i.type) in ["plat", "plats"]]
    desserts = [i for i in items if norm(i.type) in ["dessert", "desserts"]]
    return entrees, plats, desserts


def _find_stamp_path() -> str | None:
    # 1) Explicit path via ENV
    env_path = os.getenv("FINAL_STAMP_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    # 2) Default filename in assets/
    candidate = os.path.join(ASSETS_DIR, "final_stamp.png")
    if os.path.isfile(candidate):
        return candidate
    # 3) Any png in assets/ (first match)
    try:
        for name in os.listdir(ASSETS_DIR):
            if name.lower().endswith(".png"):
                return os.path.join(ASSETS_DIR, name)
    except Exception:
        pass
    return None


def _draw_final_stamp(c: canvas.Canvas, page_width: float):
    c.saveState()
    # Try PNG first
    try:
        img_path = _find_stamp_path()
        if img_path and os.path.isfile(img_path):
            # Target width, keep aspect
            target_w = 160
            from PIL import Image as PILImage  # pillow is in requirements
            with PILImage.open(img_path) as im:
                w, h = im.size
                ratio = target_w / float(w)
                target_h = h * ratio
            x = (page_width - target_w) / 2
            y = 18  # bottom padding
            c.drawImage(img_path, x, y, width=target_w, height=target_h, mask='auto', preserveAspectRatio=True, anchor='sw')
            c.restoreState()
            return
    except Exception as e:
        # Fallback to text below
        try:
            print(f"PDF: final stamp PNG not used ({e}). Falling back to text.")
        except Exception:
            pass

    # Fallback: simple red text
    c.setStrokeColor(colors.HexColor('#EF4444'))
    c.setFillColor(colors.HexColor('#EF4444'))
    c.setFont("Helvetica-Bold", 12)
    text = "VERSION FINALE"
    w = c.stringWidth(text, "Helvetica-Bold", 12)
    x = (page_width - w) / 2
    y = 20
    c.drawString(x, y, text)
    c.restoreState()


def _parse_allergens(csv: str | None) -> list[str]:
    if not csv:
        return []
    return [s.strip() for s in str(csv).split(',') if s and s.strip()]


def _find_allergen_icon(key: str) -> str | None:
    p = os.path.join(ASSETS_DIR, "allergens", f"{key}.png")
    return p if os.path.isfile(p) else None


def _drink_variant(label: str | None) -> str:
    s = (label or "").lower()
    if not s or s == 'sans formule':
        return 'none'
    if s in ('à la carte', 'a la carte'):
        return 'a_la_carte'
    if ('sans alcool' in s) and ('champ' in s):
        return 'na_champ'
    if ('avec alcool' in s) and ('champ' in s):
        return 'alcool_champ'
    if ('sans alcool' in s) and ('cava' in s):
        return 'na_cava'
    if ('avec alcool' in s) and ('cava' in s):
        return 'alcool_cava'
    if 'sans alcool' in s:
        return 'na'
    if 'avec alcool' in s:
        return 'alcool'
    return 'default'


def _drink_palette(variant: str) -> tuple:
    # returns (bg, text, border)
    mapping = {
        'na': (colors.HexColor('#eff6ff'), colors.HexColor('#1d4ed8'), colors.HexColor('#bfdbfe')),
        'alcool': (colors.HexColor('#fff1f2'), colors.HexColor('#be123c'), colors.HexColor('#fecdd3')),
        'na_cava': (colors.HexColor('#ecfeff'), colors.HexColor('#0e7490'), colors.HexColor('#a5f3fc')),
        'alcool_cava': (colors.HexColor('#fdf4ff'), colors.HexColor('#6b21a8'), colors.HexColor('#e9d5ff')),
        'na_champ': (colors.HexColor('#f0fdf4'), colors.HexColor('#047857'), colors.HexColor('#bbf7d0')),
        'alcool_champ': (colors.HexColor('#fffbeb'), colors.HexColor('#b45309'), colors.HexColor('#fde68a')),
        'a_la_carte': (colors.HexColor('#eef2ff'), colors.HexColor('#4338ca'), colors.HexColor('#c7d2fe')),
        'none': (colors.HexColor('#f9fafb'), colors.HexColor('#374151'), colors.HexColor('#e5e7eb')),
        'default': (colors.HexColor('#f3f4f6'), colors.HexColor('#111827'), colors.HexColor('#e5e7eb')),
    }
    return mapping.get(variant, mapping['default'])


def _format_date_fr(d: date) -> str:
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    return f"{jours[d.weekday()]} {d.day:02d}/{d.month:02d}/{d.year}"


def generate_reservation_pdf(reservation: Reservation, items: List[ReservationItem]) -> str:
    filename = _reservation_filename(reservation)

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36 + 5*cm, bottomMargin=54)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", fontSize=12, leading=14, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="Meta", fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="TitleBar", parent=styles['Title'], textColor=colors.white, backColor=colors.HexColor('#111827'), leading=22, spaceAfter=6))
    story = []

    title = f"{reservation.client_name} – {_format_date_fr(reservation.service_date)}"
    story.append(Paragraph(title, styles['TitleBar']))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#60a5fa')))
    story.append(Spacer(1, 10))

    meta_data = [
        [Paragraph("Client", styles['Meta']), Paragraph(str(reservation.client_name), styles['Meta'])],
        [Paragraph("Heure d’arrivée", styles['Meta']), Paragraph(str(reservation.arrival_time), styles['Meta'])],
        [Paragraph("Couverts", styles['Meta']), Paragraph(str(reservation.pax), styles['Meta'])],
    ]
    meta_tbl = Table(meta_data, colWidths=[110, None])
    meta_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#374151')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 14))

    entrees, plats, desserts = _split_items(items)

    def section(title: str, collection: List[ReservationItem]):
        story.append(Paragraph(f"<b>{title}</b>", styles['Section']))
        # En-têtes sans le texte 'Intitulé' (retiré)
        data = [[Paragraph("Qté", styles['Meta']), Paragraph("", styles['Meta'])]]
        if not collection:
            data.append(["-", "-"])
        else:
            for it in collection:
                desc = it.name
                if getattr(it, 'comment', None):
                    safe_c = str(it.comment)
                    desc = f"{it.name}<br/><font size=9 color='#6b7280'>{safe_c}</font>"
                data.append([str(it.quantity), Paragraph(desc, styles['Meta'])])
        tbl = Table(data, colWidths=[40, None])
        tbl.setStyle(TableStyle([
            # Ligne d'en-tête colorée
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,1), (0,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            # Alternance légère des lignes de données
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 10))

    section("Entrées :", entrees)
    section("Plats :", plats)
    section("Desserts :", desserts)

    story.append(Paragraph("<b>Formule boissons :</b>", styles['Section']))
    drink_text = reservation.drink_formula or "-"
    variant = _drink_variant(drink_text)
    bg, fg, bd = _drink_palette(variant)
    fb_tbl = Table([[drink_text]], colWidths=[None])
    fb_tbl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, bd),
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('TEXTCOLOR', (0,0), (-1,-1), fg),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(fb_tbl)
    story.append(Spacer(1, 10))

    # Allergens section
    story.append(Paragraph("<b>Allergènes :</b>", styles['Section']))
    alls = _parse_allergens(getattr(reservation, 'allergens', ''))
    if not alls:
        story.append(Paragraph("-", styles['Meta']))
    else:
        row = []
        for key in alls:
            icon = _find_allergen_icon(key)
            if icon:
                try:
                    row.append(RLImage(icon, width=20, height=20))
                    # Afficher aussi le libellé à côté de l'icône
                    row.append(Paragraph(key, styles['Meta']))
                except Exception:
                    row.append(Paragraph(key, styles['Meta']))
            else:
                row.append(Paragraph(key, styles['Meta']))
        tbl = Table([row])
        tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(tbl)
    story.append(Spacer(1, 10))

    notes = reservation.notes or ""
    story.append(Paragraph("<b>Notes :</b>", styles['Section']))
    
    # Convertir les marqueurs de formatage personnalisés en balises HTML
    def format_text(text):
        if not text:
            return "-"
        # Remplacer les marqueurs de formatage
        text = text.replace('*', '<b>', 1).replace('*', '</b>', 1)  # Gras
        text = text.replace('_', '<i>', 1).replace('_', '</i>', 1)  # Italique
        # Gérer les couleurs [color=#RRGGBB]texte[/color]
        import re
        text = re.sub(r'\[color=([^\]]+)\](.*?)\[/color\]', r'<font color="\1">\2</font>', text)
        # Gérer les listes à puces
        text = text.replace('\n- ', '<br/>• ')
        return text
    
    # Créer un style pour les notes avec support du HTML
    note_style = ParagraphStyle(
        'NoteStyle',
        parent=styles['Normal'],
        leading=14,
        spaceBefore=4,
        spaceAfter=4
    )
    
    # Créer un paragraphe avec formatage HTML
    formatted_notes = format_text(notes)
    note_para = Paragraph(formatted_notes, note_style)
    
    # Créer un tableau avec une seule cellule pour le paragraphe formaté
    note_tbl = Table([[note_para]], colWidths=[doc.width])
    note_tbl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#60a5fa')),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor('#bfdbfe')),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(note_tbl)

    # Build with onLaterPages to add stamp if needed by drawing after flowables
    def on_page(canvas_obj, doc_obj):
        if getattr(reservation, 'final_version', False):
            _draw_final_stamp(canvas_obj, A4[0])

    doc.build(story, onLaterPages=on_page, onFirstPage=on_page)
    return filename


def generate_reservation_pdf_both(reservation: Reservation, items: List[ReservationItem]) -> str:
    """Build a single PDF with salle page first (no extra top margin), then cuisine page
    (with 5cm top offset), and duplicate the cuisine page if desserts are present with
    quantity > 0.
    """
    filename = _reservation_filename_variant(reservation, "both")
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=54)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", fontSize=12, leading=14, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="Meta", fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="TitleBar", parent=styles['Title'], textColor=colors.white, backColor=colors.HexColor('#111827'), leading=22, spaceAfter=6))

    entrees, plats, desserts = _split_items(items)

    def salle_page_story():
        s: list = []
        title = f"{reservation.client_name} – {_format_date_fr(reservation.service_date)}"
        s.append(Paragraph(title, styles['TitleBar']))
        s.append(Spacer(1, 6))
        s.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#60a5fa')))
        s.append(Spacer(1, 10))

        meta_data = [
            [Paragraph("Client", styles['Meta']), Paragraph(str(reservation.client_name), styles['Meta'])],
            [Paragraph("Heure d’arrivée", styles['Meta']), Paragraph(str(reservation.arrival_time), styles['Meta'])],
            [Paragraph("Couverts", styles['Meta']), Paragraph(str(reservation.pax), styles['Meta'])],
        ]
        meta_tbl = Table(meta_data, colWidths=[110, None])
        meta_tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#374151')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        s.append(meta_tbl)
        s.append(Spacer(1, 14))

        def section(title: str, collection: List[ReservationItem]):
            s.append(Paragraph(f"<b>{title}</b>", styles['Section']))
            data = [[Paragraph("Qté", styles['Meta']), Paragraph("", styles['Meta'])]]
            if not collection:
                data.append(["-", "-"])
            else:
                for it in collection:
                    desc = it.name
                    if getattr(it, 'comment', None):
                        safe_c = str(it.comment)
                        desc = f"{it.name}<br/><font size=9 color='#6b7280'>{safe_c}</font>"
                    data.append([str(it.quantity), Paragraph(desc, styles['Meta'])])
            tbl = Table(data, colWidths=[40, None])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#e5e7eb')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,1), (0,-1), 'CENTER'),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ]))
            s.append(tbl)
            s.append(Spacer(1, 10))

        section("Entrées :", entrees)
        section("Plats :", plats)
        section("Desserts :", desserts)

        # Boissons (présent pour salle)
        s.append(Paragraph("<b>Formule boissons :</b>", styles['Section']))
        drink_text = reservation.drink_formula or "-"
        variant = _drink_variant(drink_text)
        bg, fg, bd = _drink_palette(variant)
        fb_tbl = Table([[drink_text]], colWidths=[None])
        fb_tbl.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, bd),
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('TEXTCOLOR', (0,0), (-1,-1), fg),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        s.append(fb_tbl)
        s.append(Spacer(1, 10))

        # Allergènes
        s.append(Paragraph("<b>Allergènes :</b>", styles['Section']))
        alls = _parse_allergens(getattr(reservation, 'allergens', ''))
        if not alls:
            s.append(Paragraph("-", styles['Meta']))
        else:
            row = []
            for key in alls:
                icon = _find_allergen_icon(key)
                if icon:
                    try:
                        row.append(RLImage(icon, width=20, height=20))
                        row.append(Paragraph(key, styles['Meta']))
                    except Exception:
                        row.append(Paragraph(key, styles['Meta']))
                else:
                    row.append(Paragraph(key, styles['Meta']))
            tbl = Table([row])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            s.append(tbl)
        s.append(Spacer(1, 10))

        # Notes (présent pour salle)
        notes = reservation.notes or ""
        s.append(Paragraph("<b>Notes :</b>", styles['Section']))
        def format_text(text):
            if not text:
                return "-"
            import re
            text = text.replace('*', '<b>', 1).replace('*', '</b>', 1)
            text = text.replace('_', '<i>', 1).replace('_', '</i>', 1)
            text = re.sub(r'\[color=([^\]]+)\](.*?)\[/color\]', r'<font color="\1">\2</font>', text)
            text = text.replace('\n- ', '<br/>• ')
            return text
        note_style = ParagraphStyle('NoteStyle', parent=styles['Normal'], leading=14, spaceBefore=4, spaceAfter=4)
        formatted_notes = format_text(notes)
        note_para = Paragraph(formatted_notes, note_style)
        note_tbl = Table([[note_para]], colWidths=[doc.width])
        note_tbl.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#60a5fa')),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor('#bfdbfe')),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        s.append(note_tbl)
        return s

    def cuisine_page_story():
        s: list = []
        # Simuler une marge haute +5cm pour la cuisine dans un seul document
        s.append(Spacer(1, 5*cm))
        title = f"{reservation.client_name} – {_format_date_fr(reservation.service_date)}"
        s.append(Paragraph(title, styles['TitleBar']))
        s.append(Spacer(1, 6))
        s.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#60a5fa')))
        s.append(Spacer(1, 10))

        meta_data = [
            [Paragraph("Client", styles['Meta']), Paragraph(str(reservation.client_name), styles['Meta'])],
            [Paragraph("Heure d’arrivée", styles['Meta']), Paragraph(str(reservation.arrival_time), styles['Meta'])],
            [Paragraph("Couverts", styles['Meta']), Paragraph(str(reservation.pax), styles['Meta'])],
        ]
        meta_tbl = Table(meta_data, colWidths=[110, None])
        meta_tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#374151')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        s.append(meta_tbl)
        s.append(Spacer(1, 14))

        def section(title: str, collection: List[ReservationItem]):
            s.append(Paragraph(f"<b>{title}</b>", styles['Section']))
            data = [[Paragraph("Qté", styles['Meta']), Paragraph("", styles['Meta'])]]
            if not collection:
                data.append(["-", "-"])
            else:
                for it in collection:
                    desc = it.name
                    if getattr(it, 'comment', None):
                        safe_c = str(it.comment)
                        desc = f"{it.name}<br/><font size=9 color='#6b7280'>{safe_c}</font>"
                    data.append([str(it.quantity), Paragraph(desc, styles['Meta'])])
            tbl = Table(data, colWidths=[40, None])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#e5e7eb')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,1), (0,-1), 'CENTER'),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ]))
            s.append(tbl)
            s.append(Spacer(1, 10))

        section("Entrées :", entrees)
        section("Plats :", plats)
        section("Desserts :", desserts)

        # Allergènes seulement (pas de boisson ni notes pour cuisine)
        s.append(Paragraph("<b>Allergènes :</b>", styles['Section']))
        alls = _parse_allergens(getattr(reservation, 'allergens', ''))
        if not alls:
            s.append(Paragraph("-", styles['Meta']))
        else:
            row = []
            for key in alls:
                icon = _find_allergen_icon(key)
                if icon:
                    try:
                        row.append(RLImage(icon, width=20, height=20))
                        row.append(Paragraph(key, styles['Meta']))
                    except Exception:
                        row.append(Paragraph(key, styles['Meta']))
                else:
                    row.append(Paragraph(key, styles['Meta']))
            tbl = Table([row])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            s.append(tbl)
        s.append(Spacer(1, 10))
        return s

    story: list = []
    # Page 1: salle
    story.extend(salle_page_story())
    # Page 2: cuisine
    story.append(PageBreak())
    story.extend(cuisine_page_story())
    # Page 3: cuisine (si desserts avec quantité)
    has_dessert_qty = False
    try:
        has_dessert_qty = any((int(getattr(it, 'quantity', 0) or 0) > 0) for it in desserts)
    except Exception:
        has_dessert_qty = bool(desserts)
    if has_dessert_qty:
        story.append(PageBreak())
        story.extend(cuisine_page_story())

    def on_page(canvas_obj, doc_obj):
        if getattr(reservation, 'final_version', False):
            _draw_final_stamp(canvas_obj, A4[0])

    doc.build(story, onLaterPages=on_page, onFirstPage=on_page)
    return filename


def generate_reservation_pdf_cuisine(reservation: Reservation, items: List[ReservationItem]) -> str:
    filename = _reservation_filename_variant(reservation, "cuisine")

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36 + 5*cm, bottomMargin=54)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", fontSize=12, leading=14, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="Meta", fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="TitleBar", parent=styles['Title'], textColor=colors.white, backColor=colors.HexColor('#111827'), leading=22, spaceAfter=6))

    entrees, plats, desserts = _split_items(items)

    def make_page_story():
        page_story: list = []
        title = f"{reservation.client_name} – {_format_date_fr(reservation.service_date)}"
        page_story.append(Paragraph(title, styles['TitleBar']))
        page_story.append(Spacer(1, 6))
        page_story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#60a5fa')))
        page_story.append(Spacer(1, 10))

        meta_data = [
            [Paragraph("Client", styles['Meta']), Paragraph(str(reservation.client_name), styles['Meta'])],
            [Paragraph("Heure d’arrivée", styles['Meta']), Paragraph(str(reservation.arrival_time), styles['Meta'])],
            [Paragraph("Couverts", styles['Meta']), Paragraph(str(reservation.pax), styles['Meta'])],
        ]
        meta_tbl = Table(meta_data, colWidths=[110, None])
        meta_tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#374151')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        page_story.append(meta_tbl)
        page_story.append(Spacer(1, 14))

        def section(title: str, collection: List[ReservationItem]):
            page_story.append(Paragraph(f"<b>{title}</b>", styles['Section']))
            data = [[Paragraph("Qté", styles['Meta']), Paragraph("", styles['Meta'])]]
            if not collection:
                data.append(["-", "-"])
            else:
                for it in collection:
                    desc = it.name
                    if getattr(it, 'comment', None):
                        safe_c = str(it.comment)
                        desc = f"{it.name}<br/><font size=9 color='#6b7280'>{safe_c}</font>"
                    data.append([str(it.quantity), Paragraph(desc, styles['Meta'])])
            tbl = Table(data, colWidths=[40, None])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#e5e7eb')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,1), (0,-1), 'CENTER'),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
            ]))
            page_story.append(tbl)
            page_story.append(Spacer(1, 10))

        section("Entrées :", entrees)
        section("Plats :", plats)
        section("Desserts :", desserts)

        page_story.append(Paragraph("<b>Allergènes :</b>", styles['Section']))
        alls = _parse_allergens(getattr(reservation, 'allergens', ''))
        if not alls:
            page_story.append(Paragraph("-", styles['Meta']))
        else:
            row = []
            for key in alls:
                icon = _find_allergen_icon(key)
                if icon:
                    try:
                        row.append(RLImage(icon, width=20, height=20))
                        row.append(Paragraph(key, styles['Meta']))
                    except Exception:
                        row.append(Paragraph(key, styles['Meta']))
                else:
                    row.append(Paragraph(key, styles['Meta']))
            tbl = Table([row])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            page_story.append(tbl)
        page_story.append(Spacer(1, 10))
        return page_story

    # Assemble story (duplicate if desserts exist)
    story = make_page_story()
    has_dessert_qty = False
    try:
        has_dessert_qty = any((int(getattr(it, 'quantity', 0) or 0) > 0) for it in desserts)
    except Exception:
        has_dessert_qty = bool(desserts)
    if has_dessert_qty:
        story = story + [PageBreak()] + make_page_story()

    def on_page(canvas_obj, doc_obj):
        if getattr(reservation, 'final_version', False):
            _draw_final_stamp(canvas_obj, A4[0])

    doc.build(story, onLaterPages=on_page, onFirstPage=on_page)
    return filename


def generate_reservation_pdf_salle(reservation: Reservation, items: List[ReservationItem]) -> str:
    filename = _reservation_filename_variant(reservation, "salle")

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=54)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", fontSize=12, leading=14, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="Meta", fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="TitleBar", parent=styles['Title'], textColor=colors.white, backColor=colors.HexColor('#111827'), leading=22, spaceAfter=6))

    story: list = []
    title = f"{reservation.client_name} – {_format_date_fr(reservation.service_date)}"
    story.append(Paragraph(title, styles['TitleBar']))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#60a5fa')))
    story.append(Spacer(1, 10))

    meta_data = [
        [Paragraph("Client", styles['Meta']), Paragraph(str(reservation.client_name), styles['Meta'])],
        [Paragraph("Heure d’arrivée", styles['Meta']), Paragraph(str(reservation.arrival_time), styles['Meta'])],
        [Paragraph("Couverts", styles['Meta']), Paragraph(str(reservation.pax), styles['Meta'])],
    ]
    meta_tbl = Table(meta_data, colWidths=[110, None])
    meta_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#374151')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 14))

    entrees, plats, desserts = _split_items(items)

    def section(title: str, collection: List[ReservationItem]):
        story.append(Paragraph(f"<b>{title}</b>", styles['Section']))
        data = [[Paragraph("Qté", styles['Meta']), Paragraph("", styles['Meta'])]]
        if not collection:
            data.append(["-", "-"])
        else:
            for it in collection:
                desc = it.name
                if getattr(it, 'comment', None):
                    safe_c = str(it.comment)
                    desc = f"{it.name}<br/><font size=9 color='#6b7280'>{safe_c}</font>"
                data.append([str(it.quantity), Paragraph(desc, styles['Meta'])])
        tbl = Table(data, colWidths=[40, None])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,1), (0,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 10))

    section("Entrées :", entrees)
    section("Plats :", plats)
    section("Desserts :", desserts)

    # Drink formula (present in salle)
    story.append(Paragraph("<b>Formule boissons :</b>", styles['Section']))
    drink_text = reservation.drink_formula or "-"
    variant = _drink_variant(drink_text)
    bg, fg, bd = _drink_palette(variant)
    fb_tbl = Table([[drink_text]], colWidths=[None])
    fb_tbl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, bd),
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('TEXTCOLOR', (0,0), (-1,-1), fg),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(fb_tbl)
    story.append(Spacer(1, 10))

    # Allergens section
    story.append(Paragraph("<b>Allergènes :</b>", styles['Section']))
    alls = _parse_allergens(getattr(reservation, 'allergens', ''))
    if not alls:
        story.append(Paragraph("-", styles['Meta']))
    else:
        row = []
        for key in alls:
            icon = _find_allergen_icon(key)
            if icon:
                try:
                    row.append(RLImage(icon, width=20, height=20))
                    row.append(Paragraph(key, styles['Meta']))
                except Exception:
                    row.append(Paragraph(key, styles['Meta']))
            else:
                row.append(Paragraph(key, styles['Meta']))
        tbl = Table([row])
        tbl.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(tbl)
    story.append(Spacer(1, 10))

    # Notes block (present in salle)
    notes = reservation.notes or ""
    story.append(Paragraph("<b>Notes :</b>", styles['Section']))
    def format_text(text):
        if not text:
            return "-"
        import re
        text = text.replace('*', '<b>', 1).replace('*', '</b>', 1)
        text = text.replace('_', '<i>', 1).replace('_', '</i>', 1)
        text = re.sub(r'\[color=([^\]]+)\](.*?)\[/color\]', r'<font color="\1">\2</font>', text)
        text = text.replace('\n- ', '<br/>• ')
        return text
    note_style = ParagraphStyle('NoteStyle', parent=styles['Normal'], leading=14, spaceBefore=4, spaceAfter=4)
    formatted_notes = format_text(notes)
    note_para = Paragraph(formatted_notes, note_style)
    note_tbl = Table([[note_para]], colWidths=[doc.width])
    note_tbl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#60a5fa')),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor('#bfdbfe')),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(note_tbl)

    def on_page(canvas_obj, doc_obj):
        if getattr(reservation, 'final_version', False):
            _draw_final_stamp(canvas_obj, A4[0])

    doc.build(story, onLaterPages=on_page, onFirstPage=on_page)
    return filename
def generate_day_pdf(d: date, reservations: List[Reservation], items_by_res: dict) -> str:
    filename = _day_filename(d)
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    offset = 5 * cm

    for idx, res in enumerate(reservations):
        if idx > 0:
            c.showPage()
        y = height - 40 - offset
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"{res.client_name} – {_format_date_fr(res.service_date)}")
        c.setStrokeColorRGB(0.9, 0.9, 0.9)
        c.setLineWidth(1)
        c.line(40, y-6, width-40, y-6)
        y -= 30
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Client : {res.client_name}")
        y -= 16
        c.drawString(40, y, f"Heure d’arrivée : {res.arrival_time}")
        y -= 16
        c.drawString(40, y, f"Couverts : {res.pax}")
        y -= 24

        entrees, plats, desserts = _split_items(items_by_res.get(str(res.id), []))

        def draw_section(title: str, collection: List[ReservationItem]):
            nonlocal y
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, title)
            y -= 16
            c.setFont("Helvetica", 11)
            if not collection:
                c.drawString(50, y, "-")
                y -= 14
            for it in collection:
                c.drawString(50, y, f"- {it.quantity}x {it.name}")
                y -= 14
                if getattr(it, 'comment', None):
                    c.setFillColor(colors.HexColor('#6b7280'))
                    c.setFont("Helvetica", 9)
                    c.drawString(70, y, f"{it.comment}")
                    c.setFillColor(colors.black)
                    c.setFont("Helvetica", 10)
                    y -= 12
            y -= 10

        draw_section("Entrées :", entrees)
        draw_section("Plats :", plats)
        draw_section("Desserts :", desserts)

        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Formule boissons :")
        y -= 14
        c.setFont("Helvetica", 11)
        c.drawString(50, y, f"{res.drink_formula}")
        y -= 16

        # Allergens (icons if available)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Allergènes :")
        y -= 16
        alls = _parse_allergens(getattr(res, 'allergens', ''))
        if not alls:
            c.setFont("Helvetica", 11)
            c.drawString(50, y, "-")
            y -= 16
        else:
            x = 50
            size = 20
            for key in alls:
                icon = _find_allergen_icon(key)
                if icon:
                    try:
                        c.drawImage(icon, x, y - size + 4, width=size, height=size, mask='auto', preserveAspectRatio=True, anchor='sw')
                        # Afficher aussi le libellé à droite de l'icône
                        c.setFont("Helvetica", 10)
                        c.drawString(x + size + 4, y, key)
                        x += size + 8 + 60
                    except Exception:
                        c.setFont("Helvetica", 10)
                        c.drawString(x, y, key)
                        x += 60
                else:
                    c.setFont("Helvetica", 10)
                    c.drawString(x, y, key)
                    x += 60
            y -= size + 8

        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Notes :")
        y -= 14
        c.setFont("Helvetica", 11)
        
        def draw_formatted_text(text, x, y, max_width):
            if not text:
                c.drawString(x, y, "-")
                return y - 14
                
            # Découper le texte en lignes tout en préservant le formatage
            import re
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            # Essayer de charger une police à largeur fixe
            try:
                pdfmetrics.registerFont(TTFont('Courier', 'Courier'))
                c.setFont("Courier", 10)
            except:
                c.setFont("Helvetica", 10)
            
            # Simplifier le formatage pour la version PDF simple
            lines = []
            for line in text.split('\n'):
                # Supprimer les marqueurs de formatage pour la version simple
                clean_line = re.sub(r'\[color=[^\]]+\]|\[/color\]|\*|_', '', line)
                if clean_line.startswith('- '):
                    clean_line = '• ' + clean_line[2:]
                lines.append(clean_line)
            
            # Dessiner chaque ligne
            for line in lines or ["-"]:
                c.drawString(x, y, line)
                y -= 14
                if y < 40:  # Nouvelle page si on arrive en bas
                    c.showPage()
                    y = height - 40 - offset
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(40, y, "Notes (suite) :")
                    y -= 20
                    c.setFont("Courier" if 'Courier' in c.getAvailableFonts() else "Helvetica", 10)
            
            return y
        
        y = draw_formatted_text(res.notes, 50, y, width - 90)
        # Final stamp at bottom
        if getattr(res, 'final_version', False):
            _draw_final_stamp(c, width)

    c.save()
    return filename


def generate_invoice_pdf(reservation: Reservation, items: List[ReservationItem], billing: BillingInfo) -> str:
    filename = _invoice_filename(reservation)

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=48 + 5*cm, bottomMargin=48)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1", fontSize=18, leading=22, spaceAfter=10))
    styles.add(ParagraphStyle(name="H2", fontSize=12, leading=16, spaceAfter=6, textColor=colors.HexColor('#374151')))
    styles.add(ParagraphStyle(name="Meta", fontSize=10, leading=14))

    story: list = []

    # Header: Internal billing sheet
    title_tbl = Table([
        [Paragraph("<b>FEUILLE DE FACTURATION (INTERNE)</b>", styles['H1']), Paragraph(f"Date: {_format_date_fr(reservation.service_date)}<br/>N° facture: ", styles['Meta'])]
    ], colWidths=[None, 220])
    title_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 10))

    # Addresses: Billing to / Reservation client
    bill_to_lines = [
        f"<b>{billing.company_name}</b>",
        billing.address_line1,
    ]
    if billing.address_line2:
        bill_to_lines.append(billing.address_line2)
    bill_to_lines.append(f"{billing.zip_code} {billing.city}")
    if billing.country:
        bill_to_lines.append(billing.country)
    if billing.vat_number:
        bill_to_lines.append(f"TVA: {billing.vat_number}")
    if billing.email:
        bill_to_lines.append(f"Email: {billing.email}")
    if billing.phone:
        bill_to_lines.append(f"Tel: {billing.phone}")

    left = Paragraph("<br/>".join([str(x) for x in bill_to_lines if x]), styles['Meta'])
    right = Paragraph("<b>Client</b><br/>" + str(reservation.client_name), styles['Meta'])
    addr_tbl = Table([[left, right]], colWidths=[None, 220])
    addr_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(addr_tbl)
    story.append(Spacer(1, 16))

    # Reservation meta
    meta_rows = [
        [Paragraph("Date du service", styles['Meta']), Paragraph(_format_date_fr(reservation.service_date), styles['Meta'])],
        [Paragraph("Heure d’arrivée", styles['Meta']), Paragraph(str(reservation.arrival_time), styles['Meta'])],
        [Paragraph("Couverts", styles['Meta']), Paragraph(str(reservation.pax), styles['Meta'])],
        [Paragraph("Formule boisson", styles['Meta']), Paragraph(str(reservation.drink_formula or '-'), styles['Meta'])],
    ]
    meta_tbl = Table(meta_rows, colWidths=[120, None])
    meta_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 14))

    # Items table listing (no prices or VAT)
    data = [[
        Paragraph('<b>Qté</b>', styles['Meta']),
        Paragraph('<b>Description</b>', styles['Meta']),
    ]]
    for it in items:
        desc = it.name
        if getattr(it, 'comment', None):
            safe_c = str(it.comment)
            desc = f"{it.name}<br/><font size=9 color='#6b7280'>{safe_c}</font>"
        data.append([str(it.quantity), Paragraph(desc, styles['Meta'])])
    items_tbl = Table(data, colWidths=[50, None])
    items_tbl.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#e5e7eb')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,1), (0,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 14))

    # Notes / Payment terms
    if billing.payment_terms or billing.notes:
        story.append(Paragraph('<b>Conditions de paiement</b>', styles['H2']))
        story.append(Paragraph(str(billing.payment_terms or '-'), styles['Meta']))
        story.append(Spacer(1, 8))
        if billing.notes:
            story.append(Paragraph('<b>Notes</b>', styles['H2']))
            story.append(Paragraph(str(billing.notes), styles['Meta']))

    doc.build(story)
    return filename
