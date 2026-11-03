"""PDF : fiche salle, fiche cuisine (+ page dessert), devis, bon pour facturation.

Tout texte venant d'un utilisateur passe par `echapper()` avant ReportLab : sans cela,
« Steak <saignant> » s'imprimait « Steak » dans l'ancienne version.
"""
from __future__ import annotations

import html
import io
import os
import re
from datetime import date
from typing import Any, Iterable, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..domain.argent import format_euros
from ..domain.normalisation import ALLERGENES, LIBELLES_TYPES
from ..domain.regles import LIBELLES_UNITES

ICONES_ALLERGENES = os.path.join(os.path.dirname(__file__), "allergenes")

NOIR = colors.HexColor("#111827")
GRIS = colors.HexColor("#6b7280")
BORDURE = colors.HexColor("#e5e7eb")
FOND = colors.HexColor("#f9fafb")
ACCENT = colors.HexColor("#7c3aed")

# (fond, texte, bordure) — mêmes couleurs que les badges de l'ancienne fiche salle.
PALETTE_BOISSONS = {
    "bleu": ("#eff6ff", "#1d4ed8", "#bfdbfe"), "rouge": ("#fff1f2", "#be123c", "#fecdd3"),
    "cyan": ("#ecfeff", "#0e7490", "#a5f3fc"), "violet": ("#fdf4ff", "#6b21a8", "#e9d5ff"),
    "vert": ("#f0fdf4", "#047857", "#bbf7d0"), "ambre": ("#fffbeb", "#b45309", "#fde68a"),
    "indigo": ("#eef2ff", "#4338ca", "#c7d2fe"), "gris": ("#f9fafb", "#374151", "#e5e7eb"),
}

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def echapper(texte: Any) -> str:
    return html.escape(str(texte if texte is not None else ""), quote=False)


def notes_html(texte: Optional[str]) -> str:
    """Balisage du site -> mini-HTML ReportLab : **gras**, _italique_, lignes « - »."""
    if not texte:
        return "-"
    s = echapper(texte)
    s = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w])_([^_\n]+)_(?![\w])", r"<i>\1</i>", s)
    lignes = [("• " + l[2:]) if l.startswith("- ") else l for l in s.split("\n")]
    return "<br/>".join(lignes)


def date_longue(d: date) -> str:
    return f"{JOURS[d.weekday()]} {d.day:02d}/{d.month:02d}/{d.year}"


def nom_fichier(*morceaux: Any) -> str:
    texte = "_".join(str(m) for m in morceaux if m)
    texte = re.sub(r"[^\w\-]+", "_", texte, flags=re.UNICODE).strip("_")
    return (texte[:120] or "document") + ".pdf"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titre": ParagraphStyle("titre", parent=base["Title"], fontSize=17, leading=21, textColor=colors.white,
                                backColor=NOIR, borderPadding=(6, 8, 6, 8), alignment=0, spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, leading=15, spaceBefore=8, spaceAfter=4,
                             textColor=NOIR),
        "texte": ParagraphStyle("texte", parent=base["Normal"], fontSize=10, leading=13),
        "petit": ParagraphStyle("petit", parent=base["Normal"], fontSize=8.5, leading=11, textColor=GRIS),
        "droite": ParagraphStyle("droite", parent=base["Normal"], fontSize=10, leading=13, alignment=TA_RIGHT),
        "gros": ParagraphStyle("gros", parent=base["Normal"], fontSize=13, leading=16, alignment=TA_RIGHT),
    }


def _table_infos(lignes: list[tuple[str, str]], st: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(echapper(k), st["petit"]), Paragraph(v, st["texte"])] for k, v in lignes]
    t = Table(data, colWidths=[4 * cm, None])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _table_plats(titre: str, lignes: list[dict[str, Any]], st: dict[str, ParagraphStyle]) -> list:
    data = [[Paragraph("<b>Qté</b>", st["texte"]), Paragraph(f"<b>{echapper(titre)}</b>", st["texte"])]]
    if not lignes:
        data.append(["-", "-"])
    for l in lignes:
        texte = echapper(l["libelle"])
        if l.get("commentaire"):
            texte += f"<br/><font size=8.5 color='#6b7280'>{echapper(l['commentaire'])}</font>"
        data.append([str(l["quantite"]), Paragraph(texte, st["texte"])])
    t = Table(data, colWidths=[1.6 * cm, None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FOND), ("GRID", (0, 0), (-1, -1), 0.25, BORDURE),
        ("ALIGN", (0, 1), (0, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [KeepTogether([t]), Spacer(1, 8)]


def _allergenes(cles: Iterable[str], st: dict[str, ParagraphStyle]) -> list:
    cles = list(cles)
    if not cles:
        return [Paragraph("Aucun allergène signalé.", st["texte"])]
    cellules = []
    for k in cles:
        icone = os.path.join(ICONES_ALLERGENES, f"{k}.png")
        libelle = Paragraph(f"<b>{echapper(ALLERGENES.get(k, k))}</b>", st["texte"])
        if os.path.isfile(icone):
            cellules.append(Table([[Image(icone, width=18, height=18), libelle]], colWidths=[22, None]))
        else:
            cellules.append(libelle)
    lignes = [cellules[i:i + 4] for i in range(0, len(cellules), 4)]
    for ligne in lignes:
        ligne += [""] * (4 - len(ligne))
    t = Table(lignes, colWidths=[4.5 * cm] * 4)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [t]


# --------------------------------------------------------------- fiches

def _page_fiche(fiche: dict[str, Any], st: dict[str, ParagraphStyle], cuisine: bool) -> list:
    d = date.fromisoformat(fiche["date"])
    histoire: list = []
    if cuisine:
        histoire.append(Spacer(1, 5 * cm))  # marge haute de la fiche cuisine (affichage au passe)
    titre = f"{echapper(fiche['client']['nom'])} – {date_longue(d)}"
    histoire.append(Paragraph(titre, st["titre"]))
    infos = [("Heure d'arrivée", fiche["heure"]), ("Couverts", f"<b>{fiche['couverts']}</b>"),
             ("Espace", echapper(fiche["espace"]))]
    if fiche.get("formule_repas"):
        infos.append(("Formule repas", f"<b>{echapper(fiche['formule_repas'])}</b>"))
    if fiche.get("tables_salle"):
        infos.append(("Table(s)", f"<b>{echapper(', '.join(fiche['tables_salle']))}</b>"))
    if fiche.get("privatisation") and not cuisine:
        infos.append(("Privatisation", echapper(fiche["privatisation"])))
    if fiche.get("contact_sur_place") and not cuisine:
        contact = echapper(fiche["contact_sur_place"])
        if fiche.get("telephone_sur_place"):
            contact += " – " + echapper(fiche["telephone_sur_place"])
        infos.append(("Contact sur place", contact))
    histoire += [_table_infos(infos, st), Spacer(1, 8)]

    par_type = {t: [l for l in fiche["lignes"] if l["type"] == t] for t in ("entree", "plat", "dessert", "supplement")}
    if fiche.get("formule_sans_plats"):
        histoire.append(Paragraph(f"<b>{echapper(fiche['formule_repas'])}</b> : pas de service à table "
                                  "(voir les suppléments).", st["texte"]))
        histoire.append(Spacer(1, 8))
    else:
        for t in ("entree", "plat", "dessert"):
            histoire += _table_plats(LIBELLES_TYPES[t].capitalize() + "s", par_type[t], st)
    if par_type["supplement"]:
        histoire += _table_plats("Suppléments", par_type["supplement"], st)

    if not cuisine:
        fond, texte, bord = PALETTE_BOISSONS.get(fiche.get("couleur_boissons") or "gris", PALETTE_BOISSONS["gris"])
        badge = Table([[Paragraph(f"<font color='{texte}'><b>Boissons : {echapper(fiche.get('formule_boissons') or '-')}"
                                  "</b></font>", st["texte"])]], colWidths=[None])
        badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
                                   ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(bord))]))
        histoire += [badge, Spacer(1, 8)]

    histoire.append(Paragraph("Allergènes", st["h2"]))
    histoire += _allergenes(fiche.get("allergenes") or [], st)
    notes = fiche.get("notes_cuisine") if cuisine else fiche.get("notes_salle")
    titre_notes = "Notes cuisine" if cuisine else "Notes salle"
    if notes or not cuisine:
        histoire.append(Paragraph(titre_notes, st["h2"]))
        bloc = Table([[Paragraph(notes_html(notes), st["texte"])]], colWidths=[None])
        bloc.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c4b5fd")),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        histoire.append(bloc)
    if not cuisine and fiche.get("notes_cuisine"):
        histoire.append(Paragraph("Notes cuisine", st["h2"]))
        histoire.append(Paragraph(notes_html(fiche["notes_cuisine"]), st["texte"]))
    return histoire


class _PiedFiche(Paragraph):
    """Marqueur invisible : indique au pied de page quelle fiche est imprimée."""

    def __init__(self, fiche: dict[str, Any]):
        super().__init__("", ParagraphStyle("vide", fontSize=1, leading=1))
        self.fiche = fiche

    def draw(self):  # pragma: no cover - rendu
        self.canv._fiche_courante = self.fiche  # type: ignore[attr-defined]


def _histoire_fiche(fiche: dict[str, Any], variante: str, st: dict[str, ParagraphStyle]) -> list:
    histoire: list = [_PiedFiche(fiche)]
    a_desserts = any(l["type"] == "dessert" for l in fiche["lignes"])
    pages: list[bool] = []
    if variante in ("salle", "complete"):
        pages.append(False)
    if variante in ("cuisine", "complete"):
        pages += [True] * (2 if a_desserts else 1)  # une page de plus pour la pâtisserie
    for i, cuisine in enumerate(pages):
        if i:
            histoire.append(PageBreak())
        histoire += _page_fiche(fiche, st, cuisine=cuisine)
    return histoire


def pdf_fiches(liste: list[dict[str, Any]], variante: str = "complete") -> bytes:
    """Une ou plusieurs fiches. variante : salle, cuisine, ou complete
    (salle + cuisine + page dessert s'il y a des desserts)."""
    st = _styles()
    tampon = io.BytesIO()
    doc = _DocFiches(tampon, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                     topMargin=1.3 * cm, bottomMargin=1.5 * cm, title="Fiches")
    histoire: list = []
    for i, fiche in enumerate(liste):
        if i:
            histoire.append(PageBreak())
        histoire += _histoire_fiche(fiche, variante, st)
    if not histoire:
        histoire.append(Paragraph("Aucune fiche.", st["texte"]))
    doc.build(histoire)
    return tampon.getvalue()


class _DocFiches(SimpleDocTemplate):
    """Pied de page dessiné en fin de page, quand on sait quelle fiche y figure."""

    def afterPage(self):  # noqa: N802 - nom imposé par ReportLab
        canvas = self.canv
        fiche = getattr(canvas, "_fiche_courante", None)
        if fiche is None:
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(1.4 * cm, 0.8 * cm, f"{fiche['statut_libelle']} – version {fiche['version']}")
        if fiche.get("statut") in ("finale", "realisee"):
            canvas.setFillColor(colors.HexColor("#dc2626"))
            canvas.setFont("Helvetica-Bold", 11)
            canvas.drawRightString(A4[0] - 1.4 * cm, 0.8 * cm, "VERSION FINALE")
        canvas.restoreState()


def pdf_fiche(fiche: dict[str, Any], variante: str = "complete") -> bytes:
    return pdf_fiches([fiche], variante)


# --------------------------------------------------------------- devis et bons

def _entete_document(titre: str, reference: str, restaurant: dict[str, Any], client: dict[str, Any],
                     dates: list[tuple[str, str]], st: dict[str, ParagraphStyle]) -> list:
    resto = [f"<b>{echapper(restaurant.get('restaurant_nom'))}</b>"]
    for cle_param in ("restaurant_adresse", "restaurant_telephone", "restaurant_email"):
        if restaurant.get(cle_param):
            resto.append(echapper(restaurant[cle_param]))
    if restaurant.get("restaurant_tva"):
        resto.append("TVA " + echapper(restaurant["restaurant_tva"]))
    cli = [f"<b>{echapper(client.get('nom'))}</b>"]
    contact = " ".join(filter(None, [client.get("contact_prenom"), client.get("contact_nom")]))
    if contact:
        cli.append("À l'attention de " + echapper(contact))
    rue = " ".join(filter(None, [client.get("rue"), client.get("numero")]))
    if client.get("boite"):
        rue += f" bte {client['boite']}"
    if rue.strip():
        cli.append(echapper(rue))
    ville = " ".join(filter(None, [client.get("code_postal"), client.get("ville")]))
    if ville:
        cli.append(echapper(ville))
    if client.get("pays") and client.get("pays") != "Belgique":
        cli.append(echapper(client["pays"]))
    if client.get("tva"):
        cli.append("TVA " + echapper(client["tva"]))
    if client.get("reference_po"):
        cli.append("Votre référence : " + echapper(client["reference_po"]))
    entete = Table([[Paragraph("<br/>".join(resto), st["texte"]), Paragraph("<br/>".join(cli), st["texte"])]],
                   colWidths=[None, 8 * cm])
    entete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    infos = " · ".join(f"{echapper(k)} : <b>{echapper(v)}</b>" for k, v in dates)
    return [entete, Spacer(1, 14), Paragraph(f"{echapper(titre)} {echapper(reference)}", st["titre"]),
            Paragraph(infos, st["texte"]), Spacer(1, 10)]


def _table_lignes(lignes: list[dict[str, Any]], st: dict[str, ParagraphStyle], avec_devis: bool = False) -> Table:
    entete = ["Désignation", "Qté", "Unité", "Prix unitaire", "Total"]
    if avec_devis:
        entete.insert(1, "Prévu")
    data = [[Paragraph(f"<b>{h}</b>", st["droite"] if h in ("Prix unitaire", "Total") else st["texte"]) for h in entete]]
    for l in lignes:
        ligne = [Paragraph(echapper(l["libelle"]), st["texte"]), str(l["quantite"]),
                 LIBELLES_UNITES.get(l["unite"], l["unite"]),
                 Paragraph(format_euros(l["prix_unitaire_centimes"]), st["droite"]),
                 Paragraph(format_euros(l["total_centimes"]), st["droite"])]
        if avec_devis:
            ligne.insert(1, str(l.get("quantite_devis") or "–"))
        data.append(ligne)
    largeurs = [None, 1.4 * cm, 2.4 * cm, 2.8 * cm, 2.8 * cm]
    if avec_devis:
        largeurs.insert(1, 1.4 * cm)
    t = Table(data, colWidths=largeurs, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FOND), ("LINEBELOW", (0, 0), (-1, 0), 0.8, NOIR),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, BORDURE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-3, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _total(total_centimes: int, st: dict[str, ParagraphStyle]) -> Table:
    t = Table([[Paragraph("<b>Total TVA comprise</b>", st["gros"]),
                Paragraph(f"<b>{format_euros(total_centimes)}</b>", st["gros"])]], colWidths=[None, 4.5 * cm])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, NOIR), ("TOPPADDING", (0, 0), (-1, -1), 8)]))
    return t


def _construire(histoire: list, brouillon: bool, titre_pdf: str) -> bytes:
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.8 * cm, title=titre_pdf)

    def decor(canvas, _doc):
        canvas.saveState()
        if brouillon:
            canvas.setFillColor(colors.HexColor("#f3f4f6"))
            canvas.setFont("Helvetica-Bold", 70)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "BROUILLON")
            canvas.rotate(-35)
            canvas.translate(-A4[0] / 2, -A4[1] / 2)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(1.6 * cm, 0.9 * cm, "Prix TVA comprise.")
        canvas.drawRightString(A4[0] - 1.6 * cm, 0.9 * cm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(histoire, onFirstPage=decor, onLaterPages=decor)
    return tampon.getvalue()


def pdf_devis(devis: dict[str, Any], client: dict[str, Any], evenement: dict[str, Any],
              restaurant: dict[str, Any], brouillon: bool) -> bytes:
    st = _styles()
    d = date.fromisoformat(evenement["date"])
    reference = f"{devis['numero']}" + (f" (version {devis['version']})" if devis["version"] > 1 else "")
    histoire = _entete_document("Devis", reference, restaurant, client, [
        ("Date", date.fromisoformat(devis["cree_le"][:10]).strftime("%d/%m/%Y")),
        ("Valable jusqu'au", date.fromisoformat(devis["date_validite"]).strftime("%d/%m/%Y")),
    ], st)
    evt = [("Événement", f"{date_longue(d)} à {evenement['heure']}"), ("Couverts", str(devis["couverts"])),
           ("Espace", echapper(evenement.get("espace") or "salle"))]
    histoire += [_table_infos(evt, st), Spacer(1, 10), _table_lignes(devis["lignes"], st), Spacer(1, 6),
                 _total(devis["total_centimes"], st), Spacer(1, 14)]
    if devis.get("remarques_client"):
        histoire += [Paragraph("Remarques", st["h2"]), Paragraph(notes_html(devis["remarques_client"]), st["texte"])]
    mentions = restaurant.get("mentions_devis")
    conditions = client.get("conditions_paiement") or restaurant.get("conditions_paiement_defaut")
    if conditions:
        histoire += [Spacer(1, 8), Paragraph(f"Conditions de paiement : {echapper(conditions)}", st["petit"])]
    if mentions:
        histoire += [Paragraph(echapper(mentions), st["petit"])]
    return _construire(histoire, brouillon, f"Devis {reference}")


def pdf_bon(bon: dict[str, Any], client: dict[str, Any], evenement: dict[str, Any],
            restaurant: dict[str, Any], brouillon: bool) -> bytes:
    st = _styles()
    d = date.fromisoformat(evenement["date"])
    histoire = _entete_document("Bon pour facturation", bon["numero"], restaurant, client, [
        ("Devis", bon["devis_reference"]), ("Événement", f"{date_longue(d)} à {evenement['heure']}"),
    ], st)
    histoire += [
        _table_infos([("Couverts prévus", str(bon["couverts_devis"])), ("Couverts réels", f"<b>{bon['couverts_reels']}</b>")], st),
        Spacer(1, 10), _table_lignes(bon["lignes"], st, avec_devis=True), Spacer(1, 6), _total(bon["total_centimes"], st),
        Spacer(1, 4),
        Paragraph(f"Total du devis : {format_euros(bon['total_devis_centimes'])} · Écart : "
                  f"<b>{format_euros(bon['ecart_centimes'])}</b>", st["droite"]),
    ]
    if bon.get("remarques_compta"):
        histoire += [Spacer(1, 10), Paragraph("Remarques pour la comptabilité", st["h2"]),
                     Paragraph(notes_html(bon["remarques_compta"]), st["texte"])]
    return _construire(histoire, brouillon, f"Bon {bon['numero']}")


# --------------------------------------------------------------- plaintes

def pdf_plainte(p: dict[str, Any]) -> bytes:
    st = _styles()
    d = date.fromisoformat(p["date"])
    histoire: list = [
        Paragraph(f"Rapport de plainte – {date_longue(d)}", st["titre"]),
        _table_infos([
            ("Heure", echapper(p.get("heure") or "Non précisé")), ("Lieu", echapper(p.get("lieu") or "Non précisé")),
            ("Client", echapper(p.get("client_nom") or "Non précisé")),
            ("Employé(s)", echapper(p.get("employes") or "Non précisé")),
            ("Gravité", f"<b>{echapper(p['gravite_libelle'])}</b>"), ("Statut", echapper(p["statut_libelle"])),
        ], st),
        Spacer(1, 8),
    ]
    for cle_texte, titre in (("recit_brut", "Récit"), ("contexte", "Contexte"), ("description", "Description de l'incident"),
                             ("reaction_personnel", "Réaction du personnel"), ("consequences", "Conséquences"),
                             ("mesures_prises", "Mesures prises"), ("observations", "Observations")):
        if p.get(cle_texte):
            histoire += [Paragraph(titre, st["h2"]), Paragraph(notes_html(p[cle_texte]), st["texte"])]
    tampon = io.BytesIO()
    SimpleDocTemplate(tampon, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.5 * cm,
                      bottomMargin=1.5 * cm, title="Plainte").build(histoire)
    return tampon.getvalue()
