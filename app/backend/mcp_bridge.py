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
from typing import Any, Optional
from urllib.parse import urlsplit

import jwt
from pydantic import AnyHttpUrl
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
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
from .models import BillingInfoUpdate, Setting, User
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
    except ValueError as exc:
        return {
            "ok": False,
            "error": {
                "status_code": 422,
                "detail": str(exc),
            },
        }



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
    instructions=(
        "Utiliser les outils fiches pour lire/mettre à jour les réservations et les outils Gmail "
        "pour rechercher/lire des échanges ou créer des brouillons. Ne jamais envoyer d'e-mail."
    ),
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


@mcp_server.tool()
def fiches_rechercher(
    q: Optional[str] = None,
    service_date: Optional[str] = None,
    scope: str = "upcoming",
    page: int = 1,
    per_page: int = 20,
) -> Any:
    """Rechercher/lister les fiches. Toujours chercher avant de créer une nouvelle fiche."""
    with session_context() as session:
        return _jsonable(list_fiches(q, service_date, scope, page, per_page, session))


@mcp_server.tool()
def fiche_lire(reservation_id: str) -> Any:
    """Lire une fiche complète par son UUID."""
    with session_context() as session:
        return _jsonable(get_fiche(uuid.UUID(reservation_id), session))


@mcp_server.tool()
def fiche_creer(
    client_name: str,
    pax: int,
    service_date: str,
    arrival_time: str,
    drink_formula: str = "sans alcool",
    menu_formula: str = "",
    notes: Optional[str] = None,
    allergens: Optional[list[str]] = None,
    on_invoice: bool = False,
    items: Optional[list[dict[str, Any]]] = None,
) -> Any:
    """Créer une fiche en brouillon. Nom, couverts, date et heure doivent être connus."""
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
            items=items or [],
        )
        with session_context() as session:
            return create_fiche(payload, session)

    return _tool_write_result(_run)


@mcp_server.tool()
def fiche_modifier(reservation_id: str, changes: dict[str, Any]) -> Any:
    """Modifier uniquement les champs demandés d'une fiche existante."""
    def _run():
        payload = GptFichePatch(**changes)
        with session_context() as session:
            return update_fiche(uuid.UUID(reservation_id), payload, session)

    return _tool_write_result(_run)


@mcp_server.tool()
def fiche_item_ajouter(
    reservation_id: str, type: str, name: str, quantity: int, comment: Optional[str] = None
) -> Any:
    """Ajouter un plat/supplément ou modifier sa quantité sans remplacer les autres items."""
    payload = GptItem(type=type, name=name, quantity=quantity, comment=comment)
    with session_context() as session:
        return _jsonable(add_item(uuid.UUID(reservation_id), payload, session))


@mcp_server.tool()
def fiche_item_retirer(reservation_id: str, type: str, name: str) -> Any:
    """Retirer un seul plat ou supplément sans toucher au reste."""
    with session_context() as session:
        return _jsonable(remove_item(uuid.UUID(reservation_id), type, name, session))


@mcp_server.tool()
def fiche_dupliquer(reservation_id: str) -> Any:
    """Dupliquer une fiche existante."""
    with session_context() as session:
        return _jsonable(duplicate_fiche(uuid.UUID(reservation_id), session))


@mcp_server.tool()
def fiche_supprimer(reservation_id: str) -> Any:
    """Supprimer une fiche. À appeler uniquement après demande explicite et confirmation."""
    with session_context() as session:
        return _jsonable(delete_fiche(uuid.UUID(reservation_id), session))


@mcp_server.tool()
def menu_rechercher(q: Optional[str] = None, type: Optional[str] = None) -> Any:
    """Rechercher les noms/types exacts des plats actifs du catalogue."""
    with session_context() as session:
        return _jsonable(search_menu_items(q, type, session))


@mcp_server.tool()
def facturation_lire(reservation_id: str) -> Any:
    """Lire les informations de facturation d'une fiche."""
    with session_context() as session:
        return _jsonable(get_billing(uuid.UUID(reservation_id), session))


@mcp_server.tool()
def facturation_mettre_a_jour(reservation_id: str, changes: dict[str, Any]) -> Any:
    """Créer ou mettre à jour la facturation. À la création, société/adresse/CP/ville sont obligatoires."""
    payload = BillingInfoUpdate(**changes)
    with session_context() as session:
        return _jsonable(upsert_billing(uuid.UUID(reservation_id), payload, session))


@mcp_server.tool()
def gmail_rechercher(q: str, max_results: int = 10) -> Any:
    """Rechercher des e-mails avec la syntaxe Gmail."""
    with session_context() as session:
        return _jsonable(search_gmail(q, max_results, session))


@mcp_server.tool()
def gmail_messages_client(email: str, max_results: int = 10) -> Any:
    """Récupérer les derniers e-mails échangés avec une adresse cliente."""
    with session_context() as session:
        return _jsonable(gmail_client_messages(email, max_results, session))


@mcp_server.tool()
def gmail_lire_fil(thread_id: str) -> Any:
    """Lire un fil Gmail complet."""
    with session_context() as session:
        return _jsonable(get_gmail_thread(thread_id, session))


@mcp_server.tool()
def gmail_lire_message(message_id: str) -> Any:
    """Lire un message Gmail précis."""
    with session_context() as session:
        return _jsonable(get_gmail_message(message_id, session))


@mcp_server.tool()
def gmail_creer_brouillon(
    to: str, subject: str, body: str, thread_id: Optional[str] = None
) -> Any:
    """Créer un brouillon Gmail, sans jamais envoyer le message."""
    payload = DraftCreate(to=to, subject=subject, body=body, thread_id=thread_id)
    with session_context() as session:
        return _jsonable(create_gmail_draft(payload, session))



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
