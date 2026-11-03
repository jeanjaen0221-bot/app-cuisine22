"""MCP bridge for ChatGPT plugins.

This module reuses the existing, battle-tested GPT API functions instead of
reimplementing reservation/Gmail business logic. It exposes them as MCP tools
and protects the MCP endpoint with OAuth 2.1 (authorization-code + PKCE).

OAuth clients are stored in the existing Setting table, so Railway restarts do
not lose ChatGPT's dynamic client registration. Access/refresh tokens are
signed JWTs using the application's existing JWT_SECRET.
"""
from __future__ import annotations

import html
import json
import os
import secrets
import time
import uuid
from typing import Annotated, Any, Literal, Optional
from urllib.parse import urlsplit

import jwt
from pydantic import AnyHttpUrl, Field, ValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .database import session_context
from .gpt_api import (
    _ALLERGENS_DESC,
    _FINAL_DESC,
    _ITEM_TYPE_ALIASES,
    _MENU_DESC,
    _NOTES_DESC,
    _STATUS_DESC,
    DrinkFormula,
    FicheStatus,
    ItemType,
    MenuFormula,
    _normalize_choice,
    GptBillingPatch,
    GptFicheCreate,
    GptFichePatch,
    GptItem,
    DraftCreate,
    add_item,
    create_fiche,
    create_gmail_draft,
    delete_fiche,
    duplicate_fiche,
    get_billing,
    get_fiche,
    get_gmail_message,
    get_gmail_thread,
    gmail_client_messages,
    list_fiches,
    remove_item,
    search_gmail,
    search_menu_items,
    update_fiche,
    upsert_billing,
)
from .gpt_rules import FICHE_RULES
from .models import Setting, User
from .security import ALGORITHM, JWT_SECRET, normalize_email, verify_password

MCP_SCOPE = "albert"
OFFLINE_SCOPE = "offline_access"
MCP_ALLOWED_SCOPES = [MCP_SCOPE, OFFLINE_SCOPE]
ACCESS_TTL_SECONDS = int(os.getenv("MCP_ACCESS_TOKEN_TTL_SECONDS", "28800"))
REFRESH_TTL_SECONDS = int(os.getenv("MCP_REFRESH_TOKEN_TTL_SECONDS", "2592000"))
_CLIENT_PREFIX = "mcp_oauth_client:"


def _public_base_url() -> str:
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        # Production must set this already for /api/gpt/openapi.json.
        base = "http://localhost:8000"
    return base


def _resource_url() -> str:
    return f"{_public_base_url()}/mcp"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _tool_write_result(fn) -> Any:
    """Return validation/business errors as structured MCP results.

    ChatGPT otherwise only receives a generic "Error executing tool", which hides
    the actionable 4xx detail from the model and user.
    """
    try:
        return _jsonable(fn())
    except HTTPException as exc:
        return {
            "ok": False,
            "error": {
                "status_code": exc.status_code,
                "detail": exc.detail,
            },
        }
    except ValidationError as exc:
        return {
            "ok": False,
            "error": {
                "status_code": 422,
                "detail": [
                    {"champ": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
                    for e in exc.errors(include_url=False)
                ],
            },
        }
    except ValueError as exc:
        return {
            "ok": False,
            "error": {
                "status_code": 422,
                "detail": str(exc),
            },
        }


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ValueError(f"Identifiant de fiche invalide : {value!r}. Utiliser l'id renvoyé par fiches_rechercher.")



class AlbertOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """OAuth provider backed by the app's existing users and JWT secret."""

    def __init__(self) -> None:
        self._pending: dict[str, dict[str, Any]] = {}
        self._codes: dict[str, AuthorizationCode] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with session_context() as session:
            row = session.get(Setting, _CLIENT_PREFIX + client_id)
            if row is None:
                return None
            try:
                return OAuthClientInformationFull.model_validate_json(row.value)
            except Exception:
                return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise ValueError("client_id manquant")
        with session_context() as session:
            key = _CLIENT_PREFIX + client_info.client_id
            row = session.get(Setting, key)
            payload = client_info.model_dump_json()
            if row is None:
                session.add(Setting(key=key, value=payload))
            else:
                row.value = payload
                session.add(row)
            session.commit()

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        state = secrets.token_urlsafe(32)
        self._pending[state] = {
            "redirect_uri": str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "code_challenge": params.code_challenge,
            "client_id": client.client_id,
            "oauth_state": params.state,
            "resource": params.resource or _resource_url(),
            "scopes": params.scopes or [MCP_SCOPE],
            "created_at": time.time(),
        }
        return f"{_resource_url()}/login?state={state}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        if code is None or code.client_id != client.client_id:
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self._codes.pop(authorization_code.code, None)
        access = self._issue_token(
            "mcp_access",
            authorization_code.client_id,
            authorization_code.subject or "",
            authorization_code.scopes,
            authorization_code.resource or _resource_url(),
            ACCESS_TTL_SECONDS,
        )
        refresh = self._issue_token(
            "mcp_refresh",
            authorization_code.client_id,
            authorization_code.subject or "",
            authorization_code.scopes,
            authorization_code.resource or _resource_url(),
            REFRESH_TTL_SECONDS,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL_SECONDS,
            refresh_token=refresh,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        payload = self._decode_token(token, "mcp_access")
        if payload is None:
            return None
        return AccessToken(
            token=token,
            client_id=payload["client_id"],
            scopes=payload.get("scopes", [MCP_SCOPE]),
            expires_at=int(payload["exp"]),
            resource=payload.get("resource"),
            subject=payload.get("sub"),
            claims={"iss": _resource_url()},
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        payload = self._decode_token(refresh_token, "mcp_refresh")
        if payload is None or payload.get("client_id") != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=payload["client_id"],
            scopes=payload.get("scopes", [MCP_SCOPE]),
            expires_at=int(payload["exp"]),
            resource=payload.get("resource"),
            subject=payload.get("sub"),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        access = self._issue_token(
            "mcp_access",
            refresh_token.client_id,
            refresh_token.subject or "",
            scopes,
            refresh_token.resource or _resource_url(),
            ACCESS_TTL_SECONDS,
        )
        new_refresh = self._issue_token(
            "mcp_refresh",
            refresh_token.client_id,
            refresh_token.subject or "",
            scopes,
            refresh_token.resource or _resource_url(),
            REFRESH_TTL_SECONDS,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL_SECONDS,
            refresh_token=new_refresh,
            scope=" ".join(scopes),
        )

    async def revoke_token(self, token: str, token_type_hint: str | None = None) -> None:  # type: ignore[override]
        # Tokens are short-lived signed JWTs. Revocation takes effect by expiry;
        # rotating JWT_SECRET invalidates every token immediately.
        return None

    def _issue_token(
        self,
        token_type: str,
        client_id: str,
        subject: str,
        scopes: list[str],
        resource: str,
        ttl: int,
    ) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "typ": token_type,
                "sub": subject,
                "client_id": client_id,
                "scopes": scopes,
                "resource": resource,
                "iat": now,
                "exp": now + ttl,
                "iss": _resource_url(),
            },
            JWT_SECRET,
            algorithm=ALGORITHM,
        )

    def _decode_token(self, token: str, expected_type: str) -> dict[str, Any] | None:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
            if payload.get("typ") != expected_type:
                return None
            if payload.get("resource") != _resource_url():
                return None
            return payload
        except jwt.InvalidTokenError:
            return None

    async def login_page(self, state: str) -> HTMLResponse:
        data = self._pending.get(state)
        if data is None or time.time() - float(data["created_at"]) > 600:
            raise HTTPException(400, "Demande de connexion expirée ou invalide.")
        action = html.escape(f"{_resource_url()}/login/callback", quote=True)
        state_value = html.escape(state, quote=True)
        return HTMLResponse(
            f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connexion Albert</title>
<style>body{{font-family:system-ui,sans-serif;max-width:420px;margin:60px auto;padding:0 20px;color:#202124}}
label{{display:block;margin-top:16px}}input{{width:100%;box-sizing:border-box;padding:11px;margin-top:6px}}
button{{margin-top:22px;padding:11px 18px;cursor:pointer}}.muted{{color:#666;font-size:14px}}</style></head>
<body><h2>Connexion Restaurant Albert</h2><p class="muted">Connectez ChatGPT avec votre compte du site des fiches.</p>
<form method="post" action="{action}">
<input type="hidden" name="state" value="{state_value}">
<label>E-mail<input name="email" type="email" autocomplete="username" required></label>
<label>Mot de passe<input name="password" type="password" autocomplete="current-password" required></label>
<button type="submit">Autoriser ChatGPT</button></form></body></html>"""
        )

    async def login_callback(self, request: Request) -> Response:
        form = await request.form()
        state = form.get("state")
        email = form.get("email")
        password = form.get("password")
        if not all(isinstance(v, str) and v for v in (state, email, password)):
            raise HTTPException(400, "Paramètres de connexion invalides.")
        data = self._pending.get(state)
        if data is None or time.time() - float(data["created_at"]) > 600:
            raise HTTPException(400, "Demande de connexion expirée ou invalide.")

        with session_context() as session:
            from sqlmodel import select
            user = session.exec(select(User).where(User.email == normalize_email(email))).first()
            if user is None or not verify_password(password, user.password_hash):
                raise HTTPException(401, "Adresse e-mail ou mot de passe incorrect.")
            if (user.role or "admin") != "admin":
                raise HTTPException(403, "Le connecteur ChatGPT est réservé aux administrateurs.")
            user_id = str(user.id)

        code_value = "mcp_" + secrets.token_urlsafe(32)
        code = AuthorizationCode(
            code=code_value,
            client_id=data["client_id"],
            redirect_uri=AnyHttpUrl(data["redirect_uri"]),
            redirect_uri_provided_explicitly=bool(data["redirect_uri_provided_explicitly"]),
            expires_at=time.time() + 300,
            scopes=[scope for scope in data["scopes"] if scope in MCP_ALLOWED_SCOPES] or [MCP_SCOPE],
            code_challenge=data["code_challenge"],
            resource=data["resource"],
            subject=user_id,
        )
        self._codes[code_value] = code
        self._pending.pop(state, None)
        return RedirectResponse(
            construct_redirect_uri(data["redirect_uri"], code=code_value, state=data["oauth_state"]),
            status_code=302,
        )


oauth_provider = AlbertOAuthProvider()

mcp_server = MCPServer(
    name="Restaurant Albert",
    title="Restaurant Albert – Fiches & Gmail",
    description="Gestion des fiches de réservation et de la boîte Gmail du Restaurant Albert.",
    # Same rules as the Custom GPT (GPT_INSTRUCTIONS.md), so both write fiches alike.
    instructions=FICHE_RULES,
    auth_server_provider=oauth_provider,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(_resource_url()),
        resource_server_url=AnyHttpUrl(_resource_url()),
        required_scopes=[MCP_SCOPE],
        validate_token_resource=True,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=MCP_ALLOWED_SCOPES,
            default_scopes=MCP_ALLOWED_SCOPES,
        ),
    ),
)


@mcp_server.custom_route("/login", methods=["GET"])
async def mcp_login(request: Request) -> Response:
    state = request.query_params.get("state", "")
    return await oauth_provider.login_page(state)


@mcp_server.custom_route("/login/callback", methods=["POST"])
async def mcp_login_callback(request: Request) -> Response:
    return await oauth_provider.login_callback(request)


_READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

# Typed parameters: the JSON schema ChatGPT receives lists the exact allowed values
# and explains every field, so it does not have to guess names or spellings.
ReservationId = Annotated[str, Field(description="UUID de la fiche (champ id renvoyé par fiches_rechercher).")]
ClientName = Annotated[str, Field(max_length=200, description="Nom de classement : société seule (ex. « Deloitte ») ou « Prénom Nom » pour un particulier. Sans titre, date, couverts ni emoji.")]
Pax = Annotated[int, Field(ge=1, le=500, description="Nombre de couverts.")]
ServiceDate = Annotated[str, Field(description="Date du service, AAAA-MM-JJ. Ne jamais deviner.")]
ArrivalTime = Annotated[str, Field(description="Heure d'arrivée, HH:MM (24 h). Ne jamais deviner.")]
Notes = Annotated[str, Field(max_length=4000, description=_NOTES_DESC)]
Allergens = Annotated[list[str], Field(description=_ALLERGENS_DESC)]
OnInvoice = Annotated[bool, Field(description="Case « Sur facture » : true seulement si le client paie sur facture.")]
Status = Annotated[FicheStatus, Field(description=_STATUS_DESC)]
FinalVersion = Annotated[bool, Field(description=_FINAL_DESC)]
DrinkField = Annotated[DrinkFormula, Field(description="Formule boissons, valeur exacte de la liste (défaut du site : « sans alcool »).")]
MenuField = Annotated[MenuFormula, Field(description=_MENU_DESC)]
Items = Annotated[list[GptItem], Field(description="Plats et suppléments. Noms exacts du catalogue (menu_rechercher). Total par type (entrée/plat/dessert) ≤ couverts.")]


@mcp_server.tool(annotations=_READ_ONLY)
def regles_fiches() -> str:
    """Règles et conventions pour écrire une fiche comme l'équipe la remplit dans le site.

    À lire au début de chaque conversation, avant de créer ou modifier une fiche.
    """
    return FICHE_RULES


@mcp_server.tool(annotations=_READ_ONLY)
def fiches_rechercher(
    q: Annotated[Optional[str], Field(description="Recherche dans le nom, la société et le contact.")] = None,
    service_date: Annotated[Optional[str], Field(description="Jour précis AAAA-MM-JJ (ignore scope).")] = None,
    scope: Annotated[Literal["upcoming", "past"], Field(description="upcoming = à venir, past = historique.")] = "upcoming",
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=50)] = 20,
    status: Annotated[Optional[Literal["draft", "confirmed", "printed"]], Field(description="Filtrer par statut de la réservation.")] = None,
    final_version: Annotated[Optional[bool], Field(description="Filtrer par fiche finalisée (true) ou non (false).")] = None,
) -> Any:
    """Rechercher/lister les fiches. Toujours chercher avant de créer une nouvelle fiche.

    status='confirmed' et final_version=false = réservations confirmées dont la fiche
    n'est pas encore finalisée.
    """
    def _run():
        with session_context() as session:
            return list_fiches(q, service_date, scope, page, per_page, session, status, final_version)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_READ_ONLY)
def fiche_lire(reservation_id: ReservationId) -> Any:
    """Lire une fiche complète (champs, plats, notes) par son UUID."""
    def _run():
        with session_context() as session:
            return get_fiche(_uuid(reservation_id), session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_WRITE)
def fiche_creer(
    client_name: ClientName,
    pax: Pax,
    service_date: ServiceDate,
    arrival_time: ArrivalTime,
    drink_formula: DrinkField = "sans alcool",
    menu_formula: MenuField = "",
    notes: Optional[Notes] = None,
    allergens: Optional[Allergens] = None,
    on_invoice: OnInvoice = False,
    status: Status = "draft",
    final_version: FinalVersion = False,
    items: Optional[Items] = None,
) -> Any:
    """Créer une fiche (brouillon par défaut). Nom, couverts, date et heure doivent être connus.

    Chercher d'abord la fiche avec fiches_rechercher : si elle existe, la modifier.
    """
    def _run():
        payload = GptFicheCreate(
            client_name=client_name,
            pax=pax,
            service_date=service_date,
            arrival_time=arrival_time,
            drink_formula=drink_formula,
            menu_formula=menu_formula,
            notes=notes,
            allergens=allergens or [],
            on_invoice=on_invoice,
            status=status,
            final_version=final_version,
            items=items or [],
        )
        with session_context() as session:
            return create_fiche(payload, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_WRITE)
def fiche_modifier(
    reservation_id: ReservationId,
    client_name: Optional[ClientName] = None,
    pax: Optional[Pax] = None,
    service_date: Optional[ServiceDate] = None,
    arrival_time: Optional[ArrivalTime] = None,
    drink_formula: Optional[DrinkField] = None,
    menu_formula: Optional[MenuField] = None,
    notes: Optional[Annotated[str, Field(max_length=4000, description=_NOTES_DESC + " Remplace tout le texte : repartir des notes actuelles.")]] = None,
    allergens: Optional[Annotated[list[str], Field(description=_ALLERGENS_DESC + " Remplace la liste existante.")]] = None,
    on_invoice: Optional[OnInvoice] = None,
    status: Optional[Status] = None,
    final_version: Optional[FinalVersion] = None,
    items: Optional[Annotated[list[GptItem], Field(description="REMPLACE toute la liste des plats. Pour un seul plat, utiliser fiche_item_ajouter / fiche_item_retirer.")]] = None,
) -> Any:
    """Modifier uniquement les champs demandés d'une fiche existante (ne pas envoyer les autres).

    status = réservation confirmée ('confirmed', preuve Gmail/Zenchef) ou 'draft'.
    final_version = fiche finalisée pour la cuisine (menus, quantités, infos validés).
    Les deux sont indépendants. Changer couverts, date, heure, formule, allergènes ou
    plats d'une fiche finalisée la repasse en non finalisée (à revalider par le chef).
    La fiche est relue après écriture : si la réponse
    contient ok=false, la modification a échoué et il faut l'annoncer comme un échec.
    """
    changes = {
        k: v
        for k, v in {
            "client_name": client_name,
            "pax": pax,
            "service_date": service_date,
            "arrival_time": arrival_time,
            "drink_formula": drink_formula,
            "menu_formula": menu_formula,
            "notes": notes,
            "allergens": allergens,
            "on_invoice": on_invoice,
            "status": status,
            "final_version": final_version,
            "items": items,
        }.items()
        if v is not None
    }

    def _run():
        if not changes:
            raise ValueError("Aucun champ à modifier : préciser au moins un champ.")
        payload = GptFichePatch(**changes)
        with session_context() as session:
            return update_fiche(_uuid(reservation_id), payload, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_WRITE)
def fiche_item_ajouter(
    reservation_id: ReservationId,
    type: Annotated[ItemType, Field(description="entrée, plat, dessert, ou supplément (extras : Champagne, Planche apéro, Privatisation…).")],
    name: Annotated[str, Field(min_length=1, max_length=200, description="Nom exact du plat du catalogue (menu_rechercher).")],
    quantity: Annotated[int, Field(ge=1, le=500, description="Nombre de portions.")],
    comment: Annotated[Optional[str], Field(max_length=500)] = None,
) -> Any:
    """Ajouter un plat/supplément ou modifier sa quantité sans remplacer les autres items."""
    def _run():
        payload = GptItem(type=type, name=name, quantity=quantity, comment=comment)
        with session_context() as session:
            return add_item(_uuid(reservation_id), payload, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_WRITE)
def fiche_item_retirer(
    reservation_id: ReservationId,
    type: Annotated[ItemType, Field(description="Type de l'item à retirer.")],
    name: Annotated[str, Field(min_length=1, description="Nom de l'item tel qu'il figure sur la fiche.")],
) -> Any:
    """Retirer un seul plat ou supplément sans toucher au reste."""
    def _run():
        with session_context() as session:
            return remove_item(_uuid(reservation_id), _normalize_choice(type, _ITEM_TYPE_ALIASES), name, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_WRITE)
def fiche_dupliquer(reservation_id: ReservationId) -> Any:
    """Dupliquer une fiche existante."""
    def _run():
        with session_context() as session:
            return duplicate_fiche(_uuid(reservation_id), session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
def fiche_supprimer(
    reservation_id: ReservationId,
    nom_client_confirme: Annotated[str, Field(description="Nom exact de la fiche (client_name), relu avant suppression.")],
) -> Any:
    """Supprimer une fiche. À appeler uniquement après demande explicite et confirmation."""
    def _run():
        with session_context() as session:
            return delete_fiche(_uuid(reservation_id), nom_client_confirme, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_READ_ONLY)
def menu_rechercher(
    q: Annotated[Optional[str], Field(description="Mots du nom du plat (accents et ordre des mots ignorés).")] = None,
    type: Annotated[Optional[Literal["entrée", "plat", "dessert"]], Field(description="Filtrer par type.")] = None,
) -> Any:
    """Rechercher les noms/types exacts des plats actifs du catalogue. Reprendre le nom renvoyé tel quel."""
    def _run():
        with session_context() as session:
            return search_menu_items(q, type, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_READ_ONLY)
def facturation_lire(reservation_id: ReservationId) -> Any:
    """Lire les informations de facturation d'une fiche."""
    def _run():
        with session_context() as session:
            return get_billing(_uuid(reservation_id), session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_WRITE)
def facturation_mettre_a_jour(
    reservation_id: ReservationId,
    company_name: Annotated[Optional[str], Field(description="Raison sociale (obligatoire à la création).")] = None,
    address_line1: Annotated[Optional[str], Field(description="Adresse (obligatoire à la création).")] = None,
    address_line2: Annotated[Optional[str], Field(description="Complément d'adresse.")] = None,
    zip_code: Annotated[Optional[str], Field(description="Code postal (obligatoire à la création).")] = None,
    city: Annotated[Optional[str], Field(description="Ville (obligatoire à la création).")] = None,
    country: Annotated[Optional[str], Field(description="Pays (défaut du site : « Belgique »).")] = None,
    vat_number: Annotated[Optional[str], Field(description="Numéro de TVA (ex. BE0123456789).")] = None,
    po_reference: Annotated[Optional[str], Field(description="Référence de bon de commande du client.")] = None,
    email: Annotated[Optional[str], Field(description="E-mail de facturation.")] = None,
    phone: Annotated[Optional[str], Field(description="Téléphone de facturation.")] = None,
    payment_terms: Annotated[Optional[str], Field(description="Conditions de paiement (défaut du site : « Paiement à 30 jours »).")] = None,
    notes: Annotated[Optional[str], Field(description="Remarques de facturation.")] = None,
) -> Any:
    """Créer ou mettre à jour la facturation. À la création, société/adresse/CP/ville sont obligatoires.

    N'envoyer que les champs à créer ou changer.
    """
    changes = {
        k: v
        for k, v in {
            "company_name": company_name,
            "address_line1": address_line1,
            "address_line2": address_line2,
            "zip_code": zip_code,
            "city": city,
            "country": country,
            "vat_number": vat_number,
            "po_reference": po_reference,
            "email": email,
            "phone": phone,
            "payment_terms": payment_terms,
            "notes": notes,
        }.items()
        if v is not None
    }

    def _run():
        payload = GptBillingPatch(**changes)
        with session_context() as session:
            return upsert_billing(_uuid(reservation_id), payload, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_READ_ONLY)
def gmail_rechercher(
    q: Annotated[str, Field(description="Requête Gmail, ex. 'from:client@exemple.com newer_than:30d'.")],
    max_results: Annotated[int, Field(ge=1, le=50)] = 10,
) -> Any:
    """Rechercher des e-mails avec la syntaxe Gmail."""
    def _run():
        with session_context() as session:
            return search_gmail(q, max_results, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_READ_ONLY)
def gmail_messages_client(
    email: Annotated[str, Field(description="Adresse e-mail du client.")],
    max_results: Annotated[int, Field(ge=1, le=50)] = 10,
) -> Any:
    """Récupérer les derniers e-mails échangés avec une adresse cliente."""
    def _run():
        with session_context() as session:
            return gmail_client_messages(email, max_results, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_READ_ONLY)
def gmail_lire_fil(thread_id: str) -> Any:
    """Lire un fil Gmail complet."""
    def _run():
        with session_context() as session:
            return get_gmail_thread(thread_id, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_READ_ONLY)
def gmail_lire_message(message_id: str) -> Any:
    """Lire un message Gmail précis."""
    def _run():
        with session_context() as session:
            return get_gmail_message(message_id, session)

    return _tool_write_result(_run)


@mcp_server.tool(annotations=_WRITE)
def gmail_creer_brouillon(
    to: Annotated[str, Field(description="Destinataire.")],
    subject: Annotated[str, Field(description="Objet.")],
    body: Annotated[str, Field(description="Texte du message.")],
    thread_id: Annotated[Optional[str], Field(description="Fil Gmail existant où placer le brouillon.")] = None,
) -> Any:
    """Créer un brouillon Gmail, sans jamais envoyer le message."""
    def _run():
        payload = DraftCreate(to=to, subject=subject, body=body, thread_id=thread_id)
        with session_context() as session:
            return create_gmail_draft(payload, session)

    return _tool_write_result(_run)



def _mcp_transport_security() -> TransportSecuritySettings:
    """Allow the configured public host while retaining DNS rebinding checks."""
    public_url = urlsplit(_public_base_url())
    public_host = public_url.netloc
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if public_host:
        allowed_hosts.append(public_host)
        allowed_origins.append(f"{public_url.scheme}://{public_host}")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def create_mcp_asgi_app():
    """Build the mounted Streamable HTTP ASGI app."""
    return mcp_server.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=False,
        transport_security=_mcp_transport_security(),
    )
