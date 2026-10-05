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
