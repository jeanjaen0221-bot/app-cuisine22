import os
from datetime import date
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import HRFlowable

from .models import Reservation, ReservationItem

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.abspath(os.path.join(BASE_DIR, "../generated_pdfs"))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(PDF_DIR, exist_ok=True)


def _reservation_filename(reservation: Reservation) -> str:
    safe_client = str(reservation.client_name).replace(" ", "_")
    return os.path.join(PDF_DIR, f"fiche_{reservation.service_date}_{safe_client}_{reservation.id}.pdf")


def _day_filename(d: date) -> str:
    return os.path.join(PDF_DIR, f"fiches_{d}.pdf")


def _split_items(items: List[ReservationItem]):
    def norm(s: str) -> str:
        return s.lower().replace("é", "e")
    entrees = [i for i in items if norm(i.type) in ["entree", "entrees"]]
    plats = [i for i in items if norm(i.type) == "plat"]
    desserts = [i for i in items if norm(i.type) == "dessert"]
    return entrees, plats, desserts


def _draw_final_stamp(c: canvas.Canvas, page_width: float):
    c.saveState()
    # Try PNG first
    try:
        img_path = os.path.join(ASSETS_DIR, "final_stamp.png")
        if os.path.isfile(img_path):
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
    except Exception:
        # Fallback to text below
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


def generate_reservation_pdf(reservation: Reservation, items: List[ReservationItem]) -> str:
    filename = _reservation_filename(reservation)

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=54)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", fontSize=12, leading=14, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="Meta", fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="TitleBar", parent=styles['Title'], textColor=colors.white, backColor=colors.HexColor('#111827'), leading=22, spaceAfter=6))
    story = []

    title = f"FICHE CUISINE – {reservation.service_date}"
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
                data.append([str(it.quantity), it.name])
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
    fb_tbl = Table([[reservation.drink_formula or "-"]], colWidths=[None])
    fb_tbl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#60a5fa')),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(fb_tbl)
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


def generate_day_pdf(d: date, reservations: List[Reservation], items_by_res: dict) -> str:
    filename = _day_filename(d)
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    for idx, res in enumerate(reservations):
        if idx > 0:
            c.showPage()
        y = height - 40
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"FICHE CUISINE – {res.service_date}")
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
                    y = height - 40
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
