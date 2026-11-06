"""Notes on the PDF must look like the live preview of the fiche form and never
break the PDF generation.

Run from the repository root:  python -m pytest app/backend/tests
"""
import os
import tempfile
import uuid
from datetime import date, time

import pytest
from pypdf import PdfReader
from reportlab.lib.styles import getSampleStyleSheet

from app.backend.models import Reservation, ReservationItem
from app.backend.pdf_service import (
    format_notes_markup,
    generate_day_pdf,
    generate_reservation_pdf_both,
    generate_reservation_pdf_cuisine,
    generate_reservation_pdf_salle,
    notes_paragraph,
)


@pytest.mark.parametrize("text, expected", [
    ("**VIP** client", "<b>VIP</b> client"),
    ("**a** puis **b**", "<b>a</b> puis <b>b</b>"),
    ("*a*", "<b>a</b>"),
    ("_doux_", "<i>doux</i>"),
    ("Ligne 1\nLigne 2", "Ligne 1<br/>Ligne 2"),
    ("Liste :\n- un\n- deux", "Liste :<br/>• un<br/>• deux"),
    ("[color=#ff0000]urgent[/color]", '<font color="#ff0000">urgent</font>'),
    ("M & Mme < 20", "M &amp; Mme &lt; 20"),
    ("", "-"),
])
def test_markup_matches_form_preview(text, expected):
    assert format_notes_markup(text) == expected


@pytest.mark.parametrize("text", [
    "contact jean_dupont@x.be",
    "Attention *important",
    "**gras _mélangé** italique_",
    "[color=pasunecouleur]x[/color]",
    "<script>alert(1)</script>",
])
def test_odd_notes_never_raise(text):
    notes_paragraph(text, getSampleStyleSheet()["Normal"])


def _reservation(notes):
    r = Reservation(
        id=uuid.uuid4(), client_name="Dupont & fils", pax=4, service_date=date(2030, 9, 17),
        arrival_time=time(19, 30), drink_formula="sans alcool", menu_formula="",
        notes=notes, allergens="gluten,lait",
    )
    items = [ReservationItem(type="plat", name="Filet de bar", quantity=4, reservation_id=r.id)]
    return r, items


@pytest.fixture(autouse=True)
def _pdf_dir(monkeypatch):
    monkeypatch.chdir(tempfile.mkdtemp())


@pytest.mark.parametrize("notes", ["contact jean_dupont@x.be\n**VIP**\n- table fenêtre", "Attention *important"])
def test_every_pdf_variant_builds_with_odd_notes(notes):
    r, items = _reservation(notes)
    for path in (
        generate_reservation_pdf_salle(r, items, None),
        generate_reservation_pdf_cuisine(r, items),
        generate_reservation_pdf_both(r, items, None),
        generate_day_pdf(r.service_date, [r], {str(r.id): items}),
    ):
        assert os.path.isfile(path)


def test_pdf_keeps_line_breaks_and_bold_text():
    r, items = _reservation("**VIP**\nLigne deux")
    text = PdfReader(generate_reservation_pdf_salle(r, items, None)).pages[0].extract_text()
    assert "VIP\nLigne deux" in text
    assert "**" not in text


def test_notes_longer_than_a_page_continue_on_the_next_page():
    # A one-cell box cannot be split across pages: past ~55 lines the PDF used
    # to fail with LayoutError and the fiche could not be downloaded at all.
    r, items = _reservation(("- demande spéciale\n" * 250)[:4000])
    for path in (
        generate_reservation_pdf_salle(r, items, None),
        generate_reservation_pdf_both(r, items, None),
        generate_day_pdf(r.service_date, [r], {str(r.id): items}),
    ):
        assert len(PdfReader(path).pages) > 1


@pytest.mark.parametrize("name", ["Deloitte / Marie Dupont", "Fête 30/10", "Société Générale Électricité " * 7, "..", ""])
def test_any_client_name_gives_a_downloadable_pdf(name):
    # The client name went into the file name as is: a "/" or a long name made
    # every PDF of that fiche fail with an error 500.
    r, items = _reservation("")
    r.client_name = name[:200]
    for path in (
        generate_reservation_pdf_salle(r, items, None),
        generate_reservation_pdf_cuisine(r, items),
        generate_reservation_pdf_both(r, items, None),
    ):
        assert os.path.isfile(path)
        assert len(os.path.basename(path).encode()) < 255


@pytest.mark.parametrize("comment, printed", [
    ("Préparation standard.", ""),
    ("Adaptation à valider par la cuisine.", ""),
    ("Sans viande ni poisson, si possible sans champignons. À valider par la cuisine.",
     "Sans viande ni poisson, si possible sans champignons."),
    ("sans sauce", "sans sauce"),
])
def test_printed_comment_drops_filler(comment, printed):
    from app.backend.pdf_service import print_comment
    assert print_comment(comment) == printed


def test_printed_comment_is_one_short_line():
    from app.backend.pdf_service import PRINT_COMMENT_MAX, print_comment
    out = print_comment("Cuisson saignante, sauce à part, servir en premier car la personne part tôt et a un train à prendre")
    assert len(out) <= PRINT_COMMENT_MAX and out.endswith("…")


def test_cuisine_copy_with_comments_fits_one_page():
    # The lines of a real fiche (7 dishes, each with a comment) used to push the
    # allergens onto a page of their own: 2 copies took 4 pages.
    r, _ = _reservation("")
    r.pax = 37
    lines = [
        ("plat", "Poule faisane à la brabançonne", 28, "Préparation standard."),
        ("plat", "Poule faisane à la brabançonne – adaptation sans gluten", 3, "Adaptation à valider par la cuisine."),
        ("plat", "Plat végétarien – à définir", 5, "Sans viande ni poisson, si possible sans champignons. À valider par la cuisine."),
        ("plat", "Plat végétarien sans gluten et sans lactose – à définir", 1, "Sans viande ni poisson, si possible sans champignons. À valider par la cuisine."),
        ("dessert", "Le grand retour du apfelstrudel et sa crème montée", 33, "Dessert standard."),
        ("dessert", "Dessert sans gluten – à définir", 3, "À valider par la cuisine."),
        ("dessert", "Dessert sans gluten et sans lactose – à définir", 1, "Pour la même personne que le plat végétarien sans gluten et sans lactose. À valider par la cuisine."),
    ]
    items = [ReservationItem(type=t, name=n, quantity=q, comment=c, reservation_id=r.id) for t, n, q, c in lines]
    # Two copies (desserts present), one page each.
    assert len(PdfReader(generate_reservation_pdf_cuisine(r, items)).pages) == 2


@pytest.mark.parametrize("name, expected", [
    ("Chef’s choice, sharingdishes", True),
    ("Chef's choice", True),
    ("Choix du chef", True),
    ("Poule faisane à la brabançonne", False),
])
def test_chefs_choice_line_leaves_room_to_write_the_choice(name, expected):
    from app.backend.pdf_service import is_chefs_choice
    assert is_chefs_choice(name) is expected
    r, _ = _reservation("")
    items = [ReservationItem(type="entrée", name=name, quantity=4, reservation_id=r.id)]
    text = PdfReader(generate_reservation_pdf_cuisine(r, items)).pages[0].extract_text()
    assert ("Choix du chef :" in text) is expected


def test_notes_never_leave_a_page_with_only_the_frame():
    # A real fiche: its notes ended at the bottom of the salle page, and only the
    # frame's bottom padding moved on to a new, otherwise empty, sheet.
    r, _ = _reservation(
        "**Société :** Conseil de l’Union européenne\n"
        "**Contact :** Isabelle Schaerlaken – isabelle.schaerlaken@consilium.europa.eu / "
        "Silja Scholtes – silja.scholtes@consilium.europa.eu\n"
        "**Occasion :** Teambuilding au Palais du Coudenberg\n"
        "**Demandes :**\n"
        "- Vin et bière à la pièce, sur une seule addition.\n"
        "- Servir l’alternative végétarienne sans gluten et sans lactose et le dessert sans "
        "gluten et sans lactose à la même personne."
    )
    r.pax, r.allergens = 37, "gluten"
    lines = [
        ("plat", "Poule faisane à la brabançonne", 28, None),
        ("plat", "Poule faisane à la brabançonne — sans gluten", 3, None),
        ("plat", "Alternative végétarienne (à valider)", 5, "Éviter les champignons si possible."),
        ("plat", "Alternative végétarienne sans gluten et sans lactose (à valider)", 1, "Éviter les champignons si possible."),
        ("dessert", "Le grand retour du apfelstrudel et sa crème montée", 33, None),
        ("dessert", "Alternative sans gluten (à valider)", 3, None),
        ("dessert", "Alternative sans gluten et sans lactose (à valider)", 1, None),
    ]
    items = [ReservationItem(type=t, name=n, quantity=q, comment=c, reservation_id=r.id) for t, n, q, c in lines]
    pages = PdfReader(generate_reservation_pdf_both(r, items, None)).pages
    assert all(p.extract_text().strip() for p in pages)
    assert len(pages) == 3  # salle + 2 cuisine copies
