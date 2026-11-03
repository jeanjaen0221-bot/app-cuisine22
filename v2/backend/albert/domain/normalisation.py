"""Lecture tolérante des saisies (site et ChatGPT).

Repris de l'ancienne API GPT (app/backend/gpt_api.py), éprouvé avec ChatGPT :
une variante évidente est corrigée (« 19h30 », « 17/09/2026 », « lactose »),
tout le reste est refusé avec la liste des valeurs permises.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time
from typing import Any, Iterable, Optional

from .erreurs import ErreurMetier


def cle(valeur: Any) -> str:
    """Clé de comparaison : minuscules, sans accents, espaces simples."""
    s = str(valeur or "").replace("œ", "oe").replace("Œ", "oe")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


# --------------------------------------------------------------- dates, heures

def lire_date(valeur: Any, champ: str = "date") -> date:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    s = str(valeur or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    if not s:
        raise ErreurMetier("champ_obligatoire", "La date est obligatoire.", champ=champ)
    raise ErreurMetier("valeur_non_permise", f"Date invalide : {s!r}. Format AAAA-MM-JJ.", champ=champ)


def lire_heure(valeur: Any, champ: str = "heure") -> time:
    if isinstance(valeur, time):
        return valeur.replace(second=0, microsecond=0)
    s = cle(valeur).replace(" ", "")
    if not s:
        raise ErreurMetier("champ_obligatoire", "L'heure d'arrivée est obligatoire.", champ=champ)
    m = re.fullmatch(r"(\d{1,2})(?:[:h](\d{2})?(?::\d{2})?)?", s) or re.fullmatch(r"(\d{2})(\d{2})", s)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return time(hh, mm)
    raise ErreurMetier("valeur_non_permise", f"Heure invalide : {valeur!r}. Format HH:MM (ex. 19:30).", champ=champ)


# --------------------------------------------------------------- types de ligne

TYPES_LIGNE = ("entree", "plat", "dessert", "supplement")
LIBELLES_TYPES = {"entree": "entrée", "plat": "plat", "dessert": "dessert", "supplement": "supplément"}
TYPES_PLATS = ("entree", "plat", "dessert")

_ALIAS_TYPES = {
    "entree": "entree", "entrees": "entree", "starter": "entree", "starters": "entree",
    "appetizer": "entree", "appetizers": "entree",
    "plat": "plat", "plats": "plat", "plat principal": "plat", "plats principaux": "plat",
    "main": "plat", "mains": "plat", "main course": "plat", "main courses": "plat",
    "dessert": "dessert", "desserts": "dessert",
    "supplement": "supplement", "supplements": "supplement", "extra": "supplement", "extras": "supplement",
}


def lire_type_ligne(valeur: Any) -> str:
    t = _ALIAS_TYPES.get(cle(valeur))
    if t is None:
        raise ErreurMetier(
            "valeur_non_permise",
            f"Type de ligne inconnu : {valeur!r}.",
            champ="type",
            valeurs_permises=[LIBELLES_TYPES[t] for t in TYPES_LIGNE],
        )
    return t


# --------------------------------------------------------------- choix nommés

_ALIAS_FORMULES = {
    "aucune": "", "aucune formule": "", "pas de formule": "",
    "1 services": "1 service", "un service": "1 service",
    "2 service": "2 services", "deux services": "2 services",
    "3 service": "3 services", "trois services": "3 services",
    "carte": "a la carte",
    "buffet": "brunch", "brunch buffet": "brunch",
    "partage": "sharing", "a partager": "sharing",
    "sans formule": "sans formule",
    "champagne": "champ",
}


def _cle_choix(valeur: Any) -> str:
    k = re.sub(r"\s*\+\s*", " + ", cle(valeur)).replace("champagne", "champ")
    return _ALIAS_FORMULES.get(k, k)


def choisir(valeur: Any, options: Iterable[tuple[str, Any]], champ: str, vide_permis: bool = False) -> Optional[Any]:
    """Retrouve une option par son nom (insensible aux accents, à la casse et aux alias).

    `options` : paires (nom, objet). Renvoie l'objet, ou None si vide et vide permis.
    """
    options = list(options)
    k = _cle_choix(valeur)
    if not k:
        if vide_permis:
            return None
        raise ErreurMetier("champ_obligatoire", f"{champ} est obligatoire.", champ=champ)
    for nom, objet in options:
        if _cle_choix(nom) == k:
            return objet
    raise ErreurMetier(
        "valeur_non_permise",
        f"Valeur inconnue pour {champ} : {valeur!r}.",
        champ=champ,
        valeurs_permises=[nom for nom, _ in options],
    )


# --------------------------------------------------------------- allergènes

ALLERGENES = {
    "gluten": "Gluten", "crustaces": "Crustacés", "oeufs": "Œufs", "poisson": "Poisson",
    "arachides": "Arachides", "soja": "Soja", "lait": "Lait", "fruits_a_coque": "Fruits à coque",
    "celeri": "Céleri", "moutarde": "Moutarde", "sesame": "Sésame", "sulfites": "Sulfites",
    "lupin": "Lupin", "mollusques": "Mollusques",
}

_ALIAS_ALLERGENES = {
    "ble": "gluten", "froment": "gluten", "cereales": "gluten",
    "crustace": "crustaces", "shellfish": "crustaces",
    "oeuf": "oeufs", "egg": "oeufs", "eggs": "oeufs",
    "poissons": "poisson", "fish": "poisson",
    "arachide": "arachides", "cacahuete": "arachides", "cacahuetes": "arachides",
    "peanut": "arachides", "peanuts": "arachides",
    "soy": "soja", "soya": "soja",
    "lactose": "lait", "produits laitiers": "lait", "produit laitier": "lait",
    "laitage": "lait", "laitages": "lait", "milk": "lait", "dairy": "lait",
    "fruits a coque": "fruits_a_coque", "fruit a coque": "fruits_a_coque",
    "noix": "fruits_a_coque", "nuts": "fruits_a_coque", "tree nuts": "fruits_a_coque",
    "fruits secs": "fruits_a_coque",
    "mustard": "moutarde", "celery": "celeri", "sesame seeds": "sesame",
    "sulfite": "sulfites", "so2": "sulfites",
    "mollusque": "mollusques",
}


def lire_allergenes(valeurs: Any) -> list[str]:
    if valeurs is None:
        return []
    if isinstance(valeurs, str):
        valeurs = [p for p in re.split(r"[,;/\n]", valeurs) if p.strip()]
    sortie: list[str] = []
    inconnus: list[str] = []
    for brut in valeurs:
        k = cle(brut).replace("_", " ")
        k = re.sub(r"^(sans|allergie|allergique|intolerance|intolerant)\s+((a la|au|aux|a|de|du|des)\s+)?", "", k)
        candidat = _ALIAS_ALLERGENES.get(k, k).replace(" ", "_")
        if candidat in ALLERGENES:
            if candidat not in sortie:
                sortie.append(candidat)
        else:
            inconnus.append(str(brut))
    if inconnus:
        raise ErreurMetier(
            "valeur_non_permise",
            f"Allergène(s) inconnu(s) : {', '.join(inconnus)}. S'il ne fait pas partie de la liste, "
            "l'écrire dans les notes cuisine.",
            champ="allergenes",
            valeurs_permises=list(ALLERGENES),
        )
    return sortie


# --------------------------------------------------------------- textes

def nettoyer_notes(valeur: Optional[str], maximum: int = 4000) -> Optional[str]:
    """Garde le balisage du site (**gras**, _italique_, lignes « - ») et retire
    le Markdown qu'un modèle aime produire (titres, puces « * »)."""
    if valeur is None:
        return None
    lignes = []
    for ligne in str(valeur).replace("\r\n", "\n").split("\n"):
        ligne = re.sub(r"^\s*#+\s*", "", ligne)
        ligne = re.sub(r"^\s*[*•]\s+", "- ", ligne)
        lignes.append(ligne.rstrip())
    texte = "\n".join(lignes).strip()
    if len(texte) > maximum:
        raise ErreurMetier("regle_metier", f"Texte trop long ({len(texte)} caractères, maximum {maximum}).", champ="notes")
    return texte or None


def texte_court(valeur: Any, champ: str, maximum: int = 200, obligatoire: bool = False) -> Optional[str]:
    s = re.sub(r"\s+", " ", str(valeur or "")).strip()
    if not s:
        if obligatoire:
            raise ErreurMetier("champ_obligatoire", f"{champ} est obligatoire.", champ=champ)
        return None
    if len(s) > maximum:
        raise ErreurMetier("regle_metier", f"{champ} : {maximum} caractères au maximum.", champ=champ)
    return s


# --------------------------------------------------------------- clients

_FORMES_JURIDIQUES = r"\b(s ?a|s ?r ?l|s ?p ?r ?l|b ?v|n ?v|a ?s ?b ?l|v ?z ?w|s ?c ?r ?l|s ?c|s ?n ?c|bvba|cvba|sas|sarl|ltd|gmbh)\b"


def cle_nom_client(nom: str) -> str:
    """« Dupont S.A. » et « dupont sa » donnent la même clé."""
    k = cle(nom)
    k = re.sub(r"[^\w\s]", " ", k)
    k = re.sub(_FORMES_JURIDIQUES, " ", k)
    return re.sub(r"\s+", " ", k).strip()


def lire_tva(valeur: Any) -> Optional[str]:
    """Normalise un n° TVA ; pour la Belgique, vérifie la clé de contrôle (modulo 97)."""
    s = re.sub(r"[\s.\-]", "", str(valeur or "")).upper()
    if not s:
        return None
    if re.fullmatch(r"\d{9,10}", s):
        s = "BE" + s
    if s.startswith("BE"):
        chiffres = s[2:]
        if len(chiffres) == 9:
            chiffres = "0" + chiffres
        if not re.fullmatch(r"[01]\d{9}", chiffres) or 97 - int(chiffres[:8]) % 97 != int(chiffres[8:]):
            raise ErreurMetier("valeur_non_permise", f"Numéro de TVA belge invalide : {valeur!r}.", champ="tva")
        return "BE" + chiffres
    if not re.fullmatch(r"[A-Z]{2}[0-9A-Z]{2,13}", s):
        raise ErreurMetier("valeur_non_permise", f"Numéro de TVA invalide : {valeur!r}.", champ="tva")
    return s


def lire_email(valeur: Any) -> Optional[str]:
    s = str(valeur or "").strip().lower()
    if not s:
        return None
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s):
        raise ErreurMetier("valeur_non_permise", f"Adresse e-mail invalide : {valeur!r}.", champ="email")
    return s
