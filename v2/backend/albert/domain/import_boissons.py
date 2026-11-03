"""Lecture d'une liste de boissons (carte en texte, CSV ou PDF).

Repris de l'ancienne version (app/backend/routers/drinks.py) : retire prix et contenances,
recolle les lettres espacées d'une carte mise en page, détecte les intertitres de catégorie.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Optional


def _espaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace(" ", " ")).strip()


def _sans_prix_ni_contenance(s: str) -> str:
    t = re.sub(r"(?:\d\s*)+(c\s*l|m\s*l|l)\b", "", s, flags=re.I)
    t = re.sub(r"\b\d+\s*(cl|ml|l)\b", "", t, flags=re.I)
    # Colonnes de prix « 2.5 / 5 » avant le prix final, sinon il resterait « 2.5 / ».
    t = re.sub(r"\b\d+(?:[\.,]\d+)?\b(?:\s*/\s*\d+(?:[\.,]\d+)?\b)+", "", t)
    t = re.sub(r"\s*[€$]?(?:\d+[\.,]\d+|\d+)(?:\s*(eur|€))?\s*$", "", t, flags=re.I)
    t = re.sub(r"\(.*?\)", "", t)
    return _espaces(t)


def _recoller_lettres(s: str) -> str:
    sortie: list[str] = []
    tampon: list[str] = []
    for mot in s.split(" "):
        if len(mot) == 1 and mot.isalpha():
            tampon.append(mot)
            continue
        if tampon:
            sortie.append("".join(tampon))
            tampon = []
        if mot:
            sortie.append(mot)
    if tampon:
        sortie.append("".join(tampon))
    return " ".join(sortie)


def _categorie(s: str) -> Optional[str]:
    k = s.lower()
    if any(x in k for x in ("bier", "bière", "beer")):
        return "bière"
    if any(x in k for x in ("aperitif", "aperitief", "apéritif")):
        return "apéritif"
    if "digestif" in k:
        return "digestif"
    if any(x in k for x in ("non-alcoholic", "sans alcool")):
        return "sans alcool"
    if any(x in k for x in ("fris", "soda", "soft")):
        return "soft"
    if any(x in k for x in ("warm", "hot", "chaud")):
        return "chaud"
    if any(x in k for x in ("vin", "wine", "wijn")):
        return "vin"
    if any(x in k for x in ("low-alcoholic", "wild")):
        return "low-alcoholic"
    return None


def _est_intertitre(s: str) -> bool:
    return len(s) <= 64 and _categorie(s) is not None and not re.search(r"\d", s)


IGNORES = ("page", "automatic zoom", "actual size", "page fit", "width", "boissons", "prix", "menu", "carte", "tva")


def lire_texte(texte: str, categorie_defaut: Optional[str] = None) -> list[tuple[str, Optional[str]]]:
    """Renvoie [(nom, catégorie)] sans doublon."""
    vus: set[str] = set()
    sortie: list[tuple[str, Optional[str]]] = []
    courante: Optional[str] = None
    for brute in texte.splitlines():
        ligne = _espaces(brute)
        if not ligne or re.fullmatch(r"[-=*\s]+", ligne):
            continue
        source = _recoller_lettres(ligne)
        if _est_intertitre(source):
            courante = _categorie(source)
            continue
        nom = _sans_prix_ni_contenance(source)
        if len(nom) < 2 or len(nom) > 120 or nom.lower() in IGNORES or any(m == nom.lower() for m in IGNORES):
            continue
        if nom.lower() in vus:
            continue
        vus.add(nom.lower())
        sortie.append((nom, courante or categorie_defaut))
    return sortie


def lire_csv(texte: str, categorie_defaut: Optional[str] = None) -> list[tuple[str, Optional[str]]]:
    lignes = list(csv.reader(io.StringIO(texte), delimiter=";" if texte.count(";") > texte.count(",") else ","))
    if not lignes:
        return []
    entete = [c.strip().lower() for c in lignes[0]]
    i_nom = next((i for i, c in enumerate(entete) if c in ("nom", "name", "boisson")), None)
    i_cat = next((i for i, c in enumerate(entete) if c in ("categorie", "catégorie", "category")), None)
    corps = lignes[1:] if i_nom is not None else lignes
    i_nom = i_nom or 0
    vus: set[str] = set()
    sortie: list[tuple[str, Optional[str]]] = []
    for ligne in corps:
        if len(ligne) <= i_nom or not ligne[i_nom].strip():
            continue
        nom = _espaces(ligne[i_nom])
        if nom.lower() in vus:
            continue
        vus.add(nom.lower())
        cat = ligne[i_cat].strip() if i_cat is not None and len(ligne) > i_cat and ligne[i_cat].strip() else categorie_defaut
        sortie.append((nom, cat))
    return sortie


def lire_pdf(contenu: bytes, categorie_defaut: Optional[str] = None) -> list[tuple[str, Optional[str]]]:
    from pypdf import PdfReader

    texte = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(contenu)).pages)
    return lire_texte(texte, categorie_defaut)
