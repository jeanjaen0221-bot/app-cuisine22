"""Dedicated API surface for a Custom GPT Action to manage fiches and factures.

This is a separate FastAPI sub-application (mounted at /api/gpt by main.py) so it gets
its own, small OpenAPI schema (/api/gpt/openapi.json) sized for a GPT Action import,
instead of exposing the full internal API. Routes delegate to the existing route
handlers in routers/reservations.py and routers/menu_items.py for persistence.

Many rules of the fiche form only live in the React form (ReservationForm.tsx), so the
internal API accepts things a human could never enter. The GPT-specific input models
and `_apply_form_rules` below re-create those rules here, so a fiche written by the GPT
looks exactly like one typed by hand: fixed choice lists (exposed as OpenAPI enums),
required name/date/time, catalogue spelling for dishes, allergen keys, "dishes win over
the formula", and fiches always created as drafts.

Authentication is a single static API key (not the human JWT login), checked by
`require_gpt_api_key` below for every route on this sub-app.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import unicodedata
import uuid
from datetime import date, datetime
from typing import Any, List, Literal, Optional, get_args

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from . import gmail_service
from .database import get_session
from .models import (
    BillingInfo,
    BillingInfoRead,
    BillingInfoUpdate,
    MenuItem,
    MenuItemRead,
    Reservation,
    ReservationCreateIn,
    ReservationItem,
    ReservationItemCreate,
    ReservationRead,
    ReservationUpdate,
)
from .routers import allergens as allergens_router
from .routers import reservations as reservations_router

# A proper FastAPI security scheme (rather than a plain Header param) makes the
# Authorization header show up in the OpenAPI schema as `securitySchemes` +
# `security`, not as a per-operation "authorization" parameter — ChatGPT's
# Action importer otherwise flags/ignores the latter since it already manages
# that header itself via the configured API Key auth.
_bearer_scheme = HTTPBearer(auto_error=False)


# ===== Choice lists of the fiche form (ReservationForm.tsx) =====

DrinkFormula = Literal[
    "sans alcool",
    "avec alcool",
    "sans alcool + cava",
    "avec alcool + cava",
    "sans alcool + champ",
    "avec alcool + champ",
    "à la carte",
    "sans Formule",
]
MenuFormula = Literal["", "1 service", "2 services", "3 services", "À la carte", "Brunch"]
ItemType = Literal["entrée", "plat", "dessert", "supplément"]

DISH_TYPES = ("entrée", "plat", "dessert")
DEFAULT_ALLERGENS = (
    "gluten", "crustaces", "oeufs", "poisson", "arachides", "soja", "lait",
    "fruits_a_coque", "celeri", "moutarde", "sesame", "sulfites", "lupin", "mollusques",
)
DEFAULT_PAYMENT_TERMS = "Paiement à 30 jours"
DEFAULT_COUNTRY = "Belgique"


def _key(value: Any) -> str:
    """Comparison key: lowercase, no accents, single spaces ("Entrée " -> "entree")."""
    s = str(value or "").replace("œ", "oe").replace("Œ", "oe")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


_DRINK_ALIASES = {_key(v): v for v in get_args(DrinkFormula)}
_DRINK_ALIASES.update({
    "sans formule": "sans Formule",
    "aucune": "sans Formule",
    "aucune formule": "sans Formule",
    "pas de formule": "sans Formule",
    "carte": "à la carte",
})

_MENU_ALIASES = {_key(v): v for v in get_args(MenuFormula)}
_MENU_ALIASES.update({
    "aucune": "",
    "aucune formule": "",
    "1 services": "1 service",
    "un service": "1 service",
    "2 service": "2 services",
    "deux services": "2 services",
    "3 service": "3 services",
    "trois services": "3 services",
    "carte": "À la carte",
    "buffet": "Brunch",
    "brunch buffet": "Brunch",
})

_ITEM_TYPE_ALIASES = {
    "entree": "entrée", "entrees": "entrée", "starter": "entrée", "starters": "entrée",
    "appetizer": "entrée", "appetizers": "entrée",
    "plat": "plat", "plats": "plat", "plat principal": "plat", "plats principaux": "plat",
    "main": "plat", "mains": "plat", "main course": "plat", "main courses": "plat",
    "dessert": "dessert", "desserts": "dessert",
    "supplement": "supplément", "supplements": "supplément",
    "extra": "supplément", "extras": "supplément",
}

_ALLERGEN_ALIASES = {
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
    "mustard": "moutarde",
    "sulfite": "sulfites", "so2": "sulfites",
    "mollusque": "mollusques",
}


def _normalize_choice(value: Any, aliases: dict) -> Any:
    """Map an obvious variant to the exact form value; anything else is left as-is
    so the Literal validation rejects it with the list of allowed values."""
    if value is None or not isinstance(value, str):
        return value
    k = re.sub(r"\s*\+\s*", " + ", _key(value)).replace("champagne", "champ")
    return aliases.get(k, value)


def _parse_date_value(value: Any) -> str:
    """Parse a date from a Custom GPT, which doesn't reliably stick to ISO.

    Accepts ISO (2026-09-17) as well as the day/month/year format a model
    tends to fall back to when echoing a date a user typed in French
    (17/09/2026). Returns ISO.
    """
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Date invalide : {s!r}. Utiliser le format AAAA-MM-JJ.")


def _parse_time_value(value: Any) -> str:
    """Parse an arrival time: '19:30', '19:30:00', '19h30', '19h', '1930'. Returns HH:MM."""
    s = _key(value).replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})(?:[:h](\d{2})?(?::\d{2})?)?", s) or re.fullmatch(r"(\d{2})(\d{2})", s)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"
    raise ValueError(f"Heure invalide : {value!r}. Utiliser le format HH:MM (ex: 19:30).")


def _parse_gpt_date(value: str) -> date:
    try:
        return date.fromisoformat(_parse_date_value(value))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


def _clean_notes(value: Any) -> Any:
    """Notes are printed on the PDF with the site's markup only (**gras**, _italique_,
    '- ' bullet lines): turn the Markdown a model likes to produce (headings,
    '* ' bullets) into that."""
    if not isinstance(value, str):
        return value
    lines = []
    for line in value.replace("\r\n", "\n").split("\n"):
        line = re.sub(r"^\s*#+\s*", "", line)
        line = re.sub(r"^\s*[*•]\s+", "- ", line)
        lines.append(line)
    return "\n".join(lines).strip()


def _split_allergens(value: Any) -> Any:
    if isinstance(value, str):
        return [p for p in re.split(r"[,;/\n]", value) if p.strip()]
    return value


# ===== Input models exposed to the GPT =====

_NOTES_DESC = (
    "Texte libre imprimé sur la fiche. Mise en forme du site uniquement : **gras**, "
    "_italique_, lignes commençant par '- ' pour les listes. Pas de titres ni de "
    "tableaux. Mettre ici "
    "les infos sans champ dédié (société, contact, occasion, demandes spéciales)."
)
_ALLERGENS_DESC = (
    "Liste de clés d'allergènes : gluten, crustaces, oeufs, poisson, arachides, soja, "
    "lait, fruits_a_coque, celeri, moutarde, sesame, sulfites, lupin, mollusques. "
    "Ne mettre que les allergènes demandés par le client."
)
_MENU_DESC = (
    "Formule repas. Laisser vide si des plats sont listés dans items : comme dans le "
    "site, les plats prévalent et la formule est alors vidée. 'Brunch' = buffet, sans "
    "entrée/plat/dessert (uniquement des suppléments)."
)


class GptItem(BaseModel):
    type: ItemType = Field(description="entrée, plat, dessert, ou supplément (extras : Champagne, Planche apéro, Privatisation…).")
    name: str = Field(min_length=1, max_length=200, description="Nom exact du plat du catalogue (voir /menu-items/search).")
    quantity: int = Field(ge=1, le=500, description="Nombre de portions.")
    comment: Optional[str] = Field(default=None, max_length=500)

    @field_validator("type", mode="before")
    @classmethod
    def _norm_type(cls, v: Any) -> Any:
        return _normalize_choice(v, _ITEM_TYPE_ALIASES)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le nom du plat est vide.")
        return v


class _FicheFields(BaseModel):
    @field_validator("client_name", check_fields=False)
    @classmethod
    def _client_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Le nom du client est obligatoire.")
        return v

    @field_validator("service_date", mode="before", check_fields=False)
    @classmethod
    def _date(cls, v: Any) -> Any:
        return None if v is None else _parse_date_value(v)

    @field_validator("arrival_time", mode="before", check_fields=False)
    @classmethod
    def _time(cls, v: Any) -> Any:
        return None if v is None else _parse_time_value(v)

    @field_validator("drink_formula", mode="before", check_fields=False)
    @classmethod
    def _drink(cls, v: Any) -> Any:
        return _normalize_choice(v, _DRINK_ALIASES)

    @field_validator("menu_formula", mode="before", check_fields=False)
    @classmethod
    def _menu(cls, v: Any) -> Any:
        return _normalize_choice(v, _MENU_ALIASES)

    @field_validator("notes", mode="before", check_fields=False)
    @classmethod
    def _notes(cls, v: Any) -> Any:
        return _clean_notes(v)

    @field_validator("allergens", mode="before", check_fields=False)
    @classmethod
    def _allergens(cls, v: Any) -> Any:
        return _split_allergens(v)


class GptFicheCreate(_FicheFields):
    client_name: str = Field(max_length=200, description="Nom sous lequel la fiche est classée (obligatoire).")
    pax: int = Field(ge=1, le=500, description="Nombre de couverts.")
    service_date: str = Field(description="Date du service, AAAA-MM-JJ (obligatoire, ne jamais deviner).")
    arrival_time: str = Field(description="Heure d'arrivée, HH:MM (obligatoire, ne jamais deviner).")
    drink_formula: DrinkFormula = Field(default="sans alcool", description="Formule boissons (défaut du site : 'sans alcool').")
    menu_formula: MenuFormula = Field(default="", description=_MENU_DESC)
    notes: Optional[str] = Field(default=None, max_length=4000, description=_NOTES_DESC)
    allergens: List[str] = Field(default_factory=list, description=_ALLERGENS_DESC)
    on_invoice: bool = Field(default=False, description="Case 'Sur facture'.")
    items: List[GptItem] = Field(default_factory=list, description="Plats et suppléments. Total par type (entrée/plat/dessert) ≤ pax.")


class GptFichePatch(_FicheFields):
    client_name: Optional[str] = Field(default=None, max_length=200)
    pax: Optional[int] = Field(default=None, ge=1, le=500)
    service_date: Optional[str] = Field(default=None, description="AAAA-MM-JJ")
    arrival_time: Optional[str] = Field(default=None, description="HH:MM")
    drink_formula: Optional[DrinkFormula] = None
    menu_formula: Optional[MenuFormula] = Field(default=None, description=_MENU_DESC)
    notes: Optional[str] = Field(default=None, max_length=4000, description=_NOTES_DESC + " Remplace les notes existantes : repartir du texte actuel.")
    allergens: Optional[List[str]] = Field(default=None, description=_ALLERGENS_DESC + " Remplace la liste existante.")
    on_invoice: Optional[bool] = None
    items: Optional[List[GptItem]] = Field(
        default=None,
        description=(
            "REMPLACE toute la liste des plats. Pour ajouter/modifier/retirer un seul "
            "plat, utiliser POST/DELETE /fiches/{id}/items à la place."
        ),
    )


# ===== Form rules re-created server-side =====

def _allergen_keys(session: Session) -> dict:
    """Valid allergen keys (defaults + those managed in the site), by comparison key."""
    known = {_key(k): k for k in DEFAULT_ALLERGENS}
    for a in allergens_router.list_allergens(session):
        known[_key(a.key)] = a.key
        known.setdefault(_key(a.label), a.key)
    return known


def _resolve_allergens(values: List[str], session: Session) -> str:
    known = _allergen_keys(session)
    out: List[str] = []
    unknown: List[str] = []
    for raw in values:
        k = _key(raw).replace("_", " ")
        k = re.sub(r"^(sans|allergie|allergique|intolerance|intolerant)\s+((a la|au|aux|a|de|du|des)\s+)?", "", k)
        candidate = _ALLERGEN_ALIASES.get(k, k)
        key = known.get(_key(candidate)) or known.get(_key(candidate).replace(" ", "_"))
        if key is None:
            unknown.append(raw)
        elif key not in out:
            out.append(key)
    if unknown:
        raise HTTPException(
            422,
            f"Allergène(s) inconnu(s) : {', '.join(unknown)}. Clés permises : "
            + ", ".join(sorted(set(known.values())))
            + ". Si ce n'est pas un allergène de la liste, le mettre dans notes.",
        )
    return ",".join(out)


def _canonical_item(item: dict, catalogue: dict) -> dict:
    """Use the catalogue's spelling and type for a known dish, like clicking its tile."""
    if item["type"] == "supplément":
        return item
    hit = catalogue.get(_key(item["name"]))
    if hit is None:
        return item
    mapped_type = _ITEM_TYPE_ALIASES.get(_key(hit.type), item["type"])
    return {**item, "name": hit.name, "type": mapped_type}


def _catalogue(session: Session) -> dict:
    rows = session.exec(select(MenuItem).where(MenuItem.active == True)).all()  # noqa: E712
    return {_key(r.name): r for r in rows}


def _apply_form_rules(menu_formula: str, items: List[dict]) -> str:
    """Rules of ReservationForm.tsx; returns the menu_formula to store."""
    has_dishes = any(_key(i["type"]) in ("entree", "plat", "dessert") for i in items)
    if menu_formula == "Brunch" and has_dishes:
        raise HTTPException(
            422,
            "Brunch = buffet : pas d'entrée/plat/dessert. Mettre les extras en type "
            "'supplément', ou changer menu_formula si ce n'est pas un brunch.",
        )
    if has_dishes:
        # "Les plats prévalent": the form never stores a formula next to dishes.
        return ""
    # A draft fiche may legitimately be incomplete while waiting for the client's
    # choices. The human site already supports that workflow, so the MCP/GPT layer
    # must not reject an otherwise valid draft solely because menu/items are pending.
    if not menu_formula:
        return ""
    return menu_formula


def _items_payload(items: List[dict]) -> List[ReservationItemCreate]:
    return [ReservationItemCreate(**i) for i in items]


def _stored_items(session: Session, reservation_id: uuid.UUID) -> List[dict]:
    rows = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == reservation_id)).all()
    out = []
    for r in rows:
        t = _ITEM_TYPE_ALIASES.get(_key(r.type), r.type)
        out.append({"type": t, "name": r.name, "quantity": r.quantity, "comment": r.comment})
    return out


def _get_reservation_or_404(session: Session, reservation_id: uuid.UUID) -> Reservation:
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Fiche introuvable.")
    return res


def require_gpt_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)) -> None:
    expected_hash = os.getenv("GPT_API_KEY_HASH", "")
    if credentials is None or not credentials.credentials:
        raise HTTPException(401, "Clé API manquante.")
    if not expected_hash:
        raise HTTPException(401, "Aucune clé API GPT configurée côté serveur.")
    token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(token_hash, expected_hash):
        raise HTTPException(401, "Clé API invalide.")


# ChatGPT's Action importer requires an absolute URL in the OpenAPI `servers`
# entry (a bare "/api/gpt" is rejected with "Impossible de trouver une URL
# valide dans `servers`"). PUBLIC_BASE_URL must be set to the public origin
# (e.g. https://fichesfiches.up.railway.app) for this to resolve correctly.
_public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
_servers = [{"url": f"{_public_base_url}/api/gpt"}] if _public_base_url else None

gpt_app = FastAPI(
    title="FicheCuisineManager - GPT Actions API",
    description=(
        "Surface dédiée pour un Custom GPT : lire, créer, remplir et modifier des "
        "fiches de réservation, gérer leur facturation, consulter le catalogue de "
        "plats, et lire/rechercher des emails ou préparer des brouillons Gmail. "
        "Les valeurs suivent exactement les choix du formulaire du site ; une valeur "
        "hors liste est refusée avec la liste des valeurs permises. "
        "Authentification par clé API statique (Authorization: Bearer <clé>)."
    ),
    servers=_servers,
    # Without this, FastAPI auto-prepends a relative "/api/gpt" server entry
    # (derived from the mount's root_path) ahead of the absolute one above —
    # ChatGPT's Action importer rejects that relative entry outright.
    root_path_in_servers=False,
    dependencies=[Depends(require_gpt_api_key)],
)


@gpt_app.get(
    "/fiches",
    response_model=list[ReservationRead],
    summary="Lister/rechercher les fiches de réservation",
    description=(
        "Par défaut, seules les réservations à venir sont retournées, triées par "
        "date, paginées via page/per_page. Utiliser scope=past pour l'historique. "
        "service_date (jour précis, AAAA-MM-JJ ou JJ/MM/AAAA) ignore scope et "
        "remonte tout ce jour-là. q cherche dans le nom, la société et le contact. "
        "Toujours chercher une fiche existante avant d'en créer une."
    ),
)
def list_fiches(
    q: Optional[str] = None,
    service_date: Optional[str] = None,
    scope: str = "upcoming",
    page: int = 1,
    per_page: int = 20,
    session: Session = Depends(get_session),
):
    per_page = max(1, min(per_page, 50))
    page = max(1, page)
    parsed_date = _parse_gpt_date(service_date) if service_date else None
    if parsed_date is not None:
        # A specific day is naturally bounded in size, so the exact-match path
        # (used elsewhere for day exports) is fine here regardless of scope.
        rows = reservations_router.list_reservations(q=q, service_date=parsed_date, session=session)
        start = (page - 1) * per_page
        return rows[start : start + per_page]
    if (scope or "upcoming").lower().strip() == "past":
        return reservations_router.list_past_reservations(q=q, page=page, per_page=per_page, session=session)
    return reservations_router.list_upcoming_reservations(q=q, page=page, per_page=per_page, session=session)


@gpt_app.get("/fiches/{reservation_id}", response_model=ReservationRead, summary="Récupérer une fiche par son id")
def get_fiche(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.get_reservation(reservation_id, session)


@gpt_app.post(
    "/fiches",
    response_model=ReservationRead,
    status_code=201,
    summary="Créer une fiche de réservation",
    description=(
        "Crée la fiche en Brouillon, comme une saisie manuelle. Nom, couverts, date "
        "et heure sont obligatoires : les demander à l'utilisateur plutôt que de les "
        "deviner. Il faut au moins un plat ou une menu_formula. Si menu_formula="
        "'Brunch' (buffet), items ne contient que des suppléments."
    ),
)
def create_fiche(payload: GptFicheCreate, session: Session = Depends(get_session)):
    catalogue = _catalogue(session)
    items = [_canonical_item(i.model_dump(), catalogue) for i in payload.items]
    menu_formula = _apply_form_rules(payload.menu_formula, items)
    data = ReservationCreateIn(
        client_name=payload.client_name,
        pax=payload.pax,
        service_date=payload.service_date,
        arrival_time=payload.arrival_time,
        drink_formula=payload.drink_formula,
        menu_formula=menu_formula,
        notes=payload.notes,
        allergens=_resolve_allergens(payload.allergens, session),
        on_invoice=payload.on_invoice,
        status="draft",
        final_version=False,
        items=_items_payload(items),
    )
    try:
        return reservations_router.create_reservation(data, session)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            409,
            "Une fiche existe déjà avec ce nom, cette date, cette heure et ce nombre de "
            "couverts. La modifier (PATCH) au lieu d'en créer une nouvelle.",
        )


def _update(reservation_id: uuid.UUID, update: dict, session: Session) -> ReservationRead:
    try:
        return reservations_router.update_reservation(reservation_id, ReservationUpdate(**update), session)
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Une autre fiche a déjà ce nom, cette date, cette heure et ce nombre de couverts.")


@gpt_app.patch(
    "/fiches/{reservation_id}",
    response_model=ReservationRead,
    summary="Modifier ou remplir une fiche (mise à jour partielle)",
    description=(
        "Mise à jour partielle : seuls les champs fournis sont modifiés, n'envoyer que "
        "ce que l'utilisateur a demandé de changer. items, si fourni, REMPLACE toute la "
        "liste des plats (les suppléments existants sont conservés si items n'en "
        "contient aucun) : pour un seul plat, utiliser /fiches/{id}/items. Le statut et "
        "le tampon 'Version finale' se gèrent uniquement dans le site."
    ),
)
def update_fiche(reservation_id: uuid.UUID, payload: GptFichePatch, session: Session = Depends(get_session)):
    res = _get_reservation_or_404(session, reservation_id)
    update = payload.model_dump(exclude_unset=True)
    for field in ("client_name", "pax", "service_date", "arrival_time", "drink_formula", "on_invoice"):
        if field in update and update[field] is None:
            raise HTTPException(422, f"{field} ne peut pas être vidé.")
    if "allergens" in update:
        update["allergens"] = _resolve_allergens(update["allergens"] or [], session)

    if "items" in update or "menu_formula" in update:
        if update.get("items") is not None:
            catalogue = _catalogue(session)
            items = [_canonical_item(i, catalogue) for i in update["items"]]
            update["items"] = _items_payload(items)
            effective = items
        else:
            update.pop("items", None)
            effective = _stored_items(session, reservation_id)
        if update.get("items") is not None and not any(i["type"] == "supplément" for i in effective):
            # Supplements are preserved by update_reservation when the new list has none.
            effective = effective + [i for i in _stored_items(session, reservation_id) if i["type"] == "supplément"]
        menu = update["menu_formula"] if "menu_formula" in update else (res.menu_formula or "")
        update["menu_formula"] = _apply_form_rules(menu or "", effective)

    return _update(reservation_id, update, session)


@gpt_app.post(
    "/fiches/{reservation_id}/items",
    response_model=ReservationRead,
    summary="Ajouter un plat ou un supplément (ou changer sa quantité) sans toucher au reste",
    description=(
        "Si un item du même type et du même nom existe déjà, sa quantité (et son "
        "commentaire) sont remplacés ; sinon il est ajouté. Les autres plats ne bougent pas."
    ),
)
def add_item(reservation_id: uuid.UUID, payload: GptItem, session: Session = Depends(get_session)):
    res = _get_reservation_or_404(session, reservation_id)
    new = _canonical_item(payload.model_dump(), _catalogue(session))
    items = _stored_items(session, reservation_id)
    for existing in items:
        if existing["type"] == new["type"] and _key(existing["name"]) == _key(new["name"]):
            existing["quantity"] = new["quantity"]
            if new.get("comment") is not None:
                existing["comment"] = new["comment"]
            break
    else:
        items.append(new)
    menu = _apply_form_rules(res.menu_formula or "", items)
    return _update(reservation_id, {"menu_formula": menu, "items": _items_payload(items)}, session)


@gpt_app.delete(
    "/fiches/{reservation_id}/items",
    response_model=ReservationRead,
    summary="Retirer un plat ou un supplément d'une fiche sans toucher au reste",
)
def remove_item(reservation_id: uuid.UUID, type: ItemType, name: str, session: Session = Depends(get_session)):
    res = _get_reservation_or_404(session, reservation_id)
    target = _canonical_item({"type": type, "name": name, "quantity": 1, "comment": None}, _catalogue(session))
    items = _stored_items(session, reservation_id)
    kept = [i for i in items if not (i["type"] == target["type"] and _key(i["name"]) == _key(target["name"]))]
    if len(kept) == len(items):
        raise HTTPException(404, f"Aucun item {type} '{name}' sur cette fiche.")
    menu = _apply_form_rules(res.menu_formula or "", kept)
    return _update(reservation_id, {"menu_formula": menu, "items": _items_payload(kept)}, session)


@gpt_app.delete("/fiches/{reservation_id}", summary="Supprimer une fiche de réservation")
def delete_fiche(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.delete_reservation(reservation_id, session)


@gpt_app.post("/fiches/{reservation_id}/duplicate", response_model=ReservationRead, summary="Dupliquer une fiche")
def duplicate_fiche(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.duplicate_reservation(reservation_id, session)


# These two routes stream a PDF, but FastAPI cannot infer that from the handler
# and would otherwise advertise `application/json` in the schema (the default for
# a route without a response_model). A client that trusts the schema then parses
# the PDF bytes as JSON and blows up — for aiohttp-based callers such as ChatGPT
# Actions, with `ContentTypeError`, a subclass of `ClientResponseError` that
# carries no HTTP status of its own. Declaring the real media type keeps the
# schema honest.
_PDF_RESPONSES = {
    200: {
        "description": "Le document PDF.",
        "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
    }
}


@gpt_app.get(
    "/fiches/{reservation_id}/pdf",
    summary="Télécharger le PDF de la fiche (et sa facture si elle existe)",
    response_class=FileResponse,
    responses=_PDF_RESPONSES,
)
def download_fiche_pdf(
    reservation_id: uuid.UUID,
    variant: Optional[str] = None,
    session: Session = Depends(get_session),
):
    return reservations_router.export_reservation_pdf(reservation_id, variant, session)


@gpt_app.get("/fiches/{reservation_id}/billing", response_model=BillingInfoRead, summary="Récupérer la facturation d'une fiche")
def get_billing(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.get_billing(reservation_id, session)


@gpt_app.put(
    "/fiches/{reservation_id}/billing",
    response_model=BillingInfoRead,
    summary="Créer ou mettre à jour la facturation d'une fiche (upsert)",
    description=(
        "Création : company_name, address_line1, zip_code et city obligatoires ; "
        "country et payment_terms prennent les valeurs par défaut du site "
        "('Belgique', 'Paiement à 30 jours'). Mise à jour : seuls les champs fournis changent."
    ),
)
def upsert_billing(reservation_id: uuid.UUID, payload: BillingInfoUpdate, session: Session = Depends(get_session)):
    if session.get(BillingInfo, reservation_id) is None:
        defaults = {"country": DEFAULT_COUNTRY, "payment_terms": DEFAULT_PAYMENT_TERMS}
        data = payload.model_dump(exclude_unset=True)
        for field, value in defaults.items():
            if not data.get(field):
                data[field] = value
        payload = BillingInfoUpdate(**data)
    return reservations_router.update_billing(reservation_id, payload, session)


@gpt_app.get(
    "/fiches/{reservation_id}/facture-pdf",
    summary="Télécharger la facture PDF d'une fiche",
    response_class=FileResponse,
    responses=_PDF_RESPONSES,
)
def download_invoice_pdf(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    return reservations_router.export_invoice_pdf(reservation_id, session)


@gpt_app.get(
    "/menu-items/search",
    summary="Rechercher des plats du catalogue (pour connaître les noms/types valides avant de remplir une fiche)",
    response_model=list[MenuItemRead],
)
def search_menu_items(q: Optional[str] = None, type: Optional[str] = None, session: Session = Depends(get_session)):
    # Insensitive to case, accents and word order ("boeuf carpaccio" finds
    # "Carpaccio de bœuf"), so the GPT does not conclude a dish is missing and
    # type an off-catalogue name instead.
    rows = session.exec(select(MenuItem).where(MenuItem.active == True)).all()  # noqa: E712
    if type:
        wanted = _ITEM_TYPE_ALIASES.get(_key(type))
        if wanted not in DISH_TYPES:
            raise HTTPException(422, "type doit être entrée, plat ou dessert.")
        rows = [r for r in rows if _ITEM_TYPE_ALIASES.get(_key(r.type)) == wanted]
    if q:
        words = _key(q).split()
        rows = [r for r in rows if all(w in _key(r.name) for w in words)]
    return [MenuItemRead.model_validate(r) for r in sorted(rows, key=lambda r: _key(r.name))[:20]]


# ===== Gmail (boîte partagée, ex. info@albert.brussels) =====
# Lecture seule + brouillons uniquement : aucune route n'envoie de mail, même si
# le jeton OAuth sous-jacent (scope gmail.compose) le permettrait techniquement.

class DraftCreate(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: Optional[str] = None


@gpt_app.get(
    "/gmail/search",
    summary="Rechercher des emails (syntaxe de recherche Gmail)",
    description=(
        "q utilise la syntaxe de recherche Gmail, ex: 'from:client@exemple.com "
        "newer_than:30d' ou 'subject:facture'. Voir l'aide Gmail pour la syntaxe."
    ),
)
def search_gmail(q: str, max_results: int = 10, session: Session = Depends(get_session)):
    return gmail_service.search_messages(session, q, max_results)


@gpt_app.get(
    "/gmail/client-messages",
    summary="Récupérer les derniers emails échangés avec une adresse cliente",
)
def gmail_client_messages(email: str, max_results: int = 10, session: Session = Depends(get_session)):
    query = f"from:{email} OR to:{email}"
    return gmail_service.search_messages(session, query, max_results)


@gpt_app.get("/gmail/threads/{thread_id}", summary="Lire un fil de discussion complet")
def get_gmail_thread(thread_id: str, session: Session = Depends(get_session)):
    return gmail_service.get_thread(session, thread_id)


@gpt_app.get("/gmail/messages/{message_id}", summary="Lire un email précis")
def get_gmail_message(message_id: str, session: Session = Depends(get_session)):
    return gmail_service.get_message(session, message_id)


@gpt_app.post(
    "/gmail/drafts",
    status_code=201,
    summary="Préparer un brouillon de réponse (jamais envoyé automatiquement)",
    description=(
        "Crée un brouillon visible dans Gmail, à relire et envoyer manuellement. "
        "thread_id (optionnel) place le brouillon dans un fil existant plutôt "
        "que d'en créer un nouveau."
    ),
)
def create_gmail_draft(payload: DraftCreate, session: Session = Depends(get_session)):
    return gmail_service.create_draft(session, payload.to, payload.subject, payload.body, payload.thread_id)
