"""OAuth 2.1 + PKCE pour le connecteur ChatGPT, adossé aux comptes de l'outil.

Tout est en base (clients, demandes, codes, connexions) : un redémarrage ou un
second processus ne casse pas une connexion en cours. Chaque jeton porte l'id de
sa « connexion » : la révoquer dans l'outil coupe aussitôt l'accès.
"""
from __future__ import annotations

import html
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from pydantic import AnyHttpUrl
from sqlalchemy import delete
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from ..config import reglages
from ..db import session_contexte
from ..domain.erreurs import ErreurMetier
from ..models import ConnexionChatGPT, OAuthAttente, OAuthClient, Utilisateur
from ..services import comptes

# Droits qu'une connexion ChatGPT peut recevoir. Valider, transmettre, toucher aux prix,
# supprimer : jamais (refusé par les services, quel que soit le droit).
SCOPES = {
    "lecture": "Lire les clients, fiches, devis, bons et le menu Prix",
    "fiches:ecrire": "Créer et modifier des clients et des fiches (en brouillon)",
    "devis:preparer": "Préparer des devis et des bons pour facturation en brouillon",
    "plaintes:preparer": "Rédiger des rapports de plainte en brouillon",
    "achats:preparer": "Préparer des bons de commande fournisseur en brouillon (jamais envoyés)",
}
OFFLINE = "offline_access"
SCOPES_PERMIS = [*SCOPES, OFFLINE]
DUREE_ACCES = 60 * 60
DUREE_RAFRAICHISSEMENT = 30 * 24 * 60 * 60


def url_ressource() -> str:
    return f"{reglages.url_publique}/mcp"


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _attente(session, cle: str, genre: str) -> Optional[dict[str, Any]]:
    ligne = session.get(OAuthAttente, cle)
    if ligne is None or ligne.genre != genre:
        return None
    expire = ligne.expire_le if ligne.expire_le.tzinfo else ligne.expire_le.replace(tzinfo=timezone.utc)
    if expire < _maintenant():
        session.delete(ligne)
        session.commit()
        return None
    return ligne.donnees


def utilisateur_autorise(u: Utilisateur) -> bool:
    return u.actif and u.role in ("admin", "equipe") and (u.role == "admin" or "chatgpt" in (u.droits or []))


class FournisseurOAuth(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):

    # ------------------------------------------------------------ clients
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with session_contexte() as session:
            ligne = session.get(OAuthClient, client_id)
            return OAuthClientInformationFull.model_validate(ligne.donnees) if ligne else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise ValueError("client_id manquant")
        with session_contexte() as session:
            donnees = client_info.model_dump(mode="json")
            ligne = session.get(OAuthClient, client_info.client_id)
            if ligne is None:
                session.add(OAuthClient(client_id=client_info.client_id, donnees=donnees))
            else:
                ligne.donnees = donnees
            session.commit()

    # ------------------------------------------------------------ autorisation
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        cle = secrets.token_urlsafe(32)
        demandes = [s for s in (params.scopes or list(SCOPES)) if s in SCOPES_PERMIS]
        with session_contexte() as session:
            session.execute(delete(OAuthAttente).where(OAuthAttente.expire_le < _maintenant()))
            session.add(OAuthAttente(cle=cle, genre="demande", expire_le=_maintenant() + timedelta(minutes=10), donnees={
                "redirect_uri": str(params.redirect_uri),
                "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                "code_challenge": params.code_challenge, "client_id": client.client_id,
                "client_nom": client.client_name or client.client_id, "state": params.state,
                "resource": params.resource or url_ressource(), "scopes": demandes or list(SCOPES),
            }))
            session.commit()
        return f"{url_ressource()}/connexion?demande={cle}"

    async def page_connexion(self, request: Request, erreur: str = "") -> HTMLResponse:
        cle = request.query_params.get("demande", "") or str((await request.form()).get("demande", ""))
        with session_contexte() as session:
            demande = _attente(session, cle, "demande")
        if demande is None:
            return HTMLResponse(_page("Demande expirée", "<p>La demande de connexion a expiré. Relancer la connexion "
                                      "depuis ChatGPT.</p>"), status_code=400)
        cases = "".join(
            f'<label class="case"><input type="checkbox" name="scope" value="{html.escape(s)}" checked> '
            f"{html.escape(SCOPES[s])}</label>" for s in demande["scopes"] if s in SCOPES)
        corps = f"""
<p class="muted">« {html.escape(demande['client_nom'])} » demande l'accès à l'outil du restaurant avec votre compte.
ChatGPT ne pourra jamais valider ni transmettre un devis, modifier un prix ou supprimer quoi que ce soit.</p>
{f'<p class="erreur">{html.escape(erreur)}</p>' if erreur else ''}
<form method="post" action="{html.escape(url_ressource())}/connexion">
<input type="hidden" name="demande" value="{html.escape(cle)}">
<label>E-mail<input name="email" type="email" autocomplete="username" required></label>
<label>Mot de passe<input name="mot_de_passe" type="password" autocomplete="current-password" required></label>
<fieldset><legend>Droits accordés</legend>{cases}</fieldset>
<button type="submit">Autoriser ChatGPT</button></form>"""
        return HTMLResponse(_page("Connecter ChatGPT", corps), status_code=400 if erreur else 200)

    async def valider_connexion(self, request: Request) -> Response:
        formulaire = await request.form()
        cle = str(formulaire.get("demande", ""))
        email = str(formulaire.get("email", ""))
        mot_de_passe = str(formulaire.get("mot_de_passe", ""))
        choisis = [str(s) for s in formulaire.getlist("scope")]
        ip = request.client.host if request.client else ""
        with session_contexte() as session:
            demande = _attente(session, cle, "demande")
            if demande is None:
                return HTMLResponse(_page("Demande expirée", "<p>Relancer la connexion depuis ChatGPT.</p>"), 400)
            try:
                u = comptes.authentifier(session, email, mot_de_passe, ip)
            except ErreurMetier as e:
                return await self.page_connexion(request, e.message)
            if not utilisateur_autorise(u):
                return await self.page_connexion(request, "Ce compte n'a pas le droit de connecter ChatGPT "
                                                          "(à demander à un administrateur).")
            scopes = [s for s in demande["scopes"] if s in choisis and s in SCOPES]
            if "lecture" not in scopes:
                return await self.page_connexion(request, "Le droit « lecture » est nécessaire.")
            if OFFLINE in demande["scopes"]:
                scopes.append(OFFLINE)
            connexion = ConnexionChatGPT(utilisateur_id=u.id, client_id=demande["client_id"],
                                         client_nom=demande["client_nom"][:200], scopes=scopes)
            session.add(connexion)
            session.flush()
            code = "albert_" + secrets.token_urlsafe(32)
            session.add(OAuthAttente(cle=code, genre="code", expire_le=_maintenant() + timedelta(minutes=5), donnees={
                **demande, "scopes": scopes, "sujet": str(u.id), "connexion": str(connexion.id)}))
            session.delete(session.get(OAuthAttente, cle))
            session.commit()
        return RedirectResponse(construct_redirect_uri(demande["redirect_uri"], code=code, state=demande["state"]),
                                status_code=302)

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str):
        with session_contexte() as session:
            d = _attente(session, authorization_code, "code")
        if d is None or d["client_id"] != client.client_id:
            return None
        return AuthorizationCode(
            code=authorization_code, client_id=d["client_id"], redirect_uri=AnyHttpUrl(d["redirect_uri"]),
            redirect_uri_provided_explicitly=bool(d["redirect_uri_provided_explicitly"]),
            expires_at=time.time() + 60, scopes=d["scopes"], code_challenge=d["code_challenge"],
            resource=d["resource"], subject=d["sujet"],
        )

    async def exchange_authorization_code(self, client, authorization_code: AuthorizationCode) -> OAuthToken:
        with session_contexte() as session:
            d = _attente(session, authorization_code.code, "code")
            ligne = session.get(OAuthAttente, authorization_code.code)
            if ligne is not None:
                session.delete(ligne)  # usage unique
                session.commit()
        if d is None:
            raise ValueError("Code déjà utilisé ou expiré")
        return self._jetons(client.client_id, d["sujet"], d["connexion"], authorization_code.scopes)

    # ------------------------------------------------------------ jetons
    def _emettre(self, genre: str, client_id: str, sujet: str, connexion: str, scopes: list[str], duree: int) -> str:
        maintenant = int(time.time())
        return jwt.encode({"typ": genre, "sub": sujet, "cid": connexion, "client_id": client_id, "scopes": scopes,
                           "resource": url_ressource(), "iss": url_ressource(), "iat": maintenant,
                           "exp": maintenant + duree, "jti": secrets.token_hex(8)},
                          reglages.secret, algorithm="HS256")

    def _jetons(self, client_id: str, sujet: str, connexion: str, scopes: list[str]) -> OAuthToken:
        return OAuthToken(
            access_token=self._emettre("mcp_acces", client_id, sujet, connexion, scopes, DUREE_ACCES),
            token_type="Bearer", expires_in=DUREE_ACCES, scope=" ".join(scopes),
            refresh_token=self._emettre("mcp_rafraichissement", client_id, sujet, connexion, scopes,
                                        DUREE_RAFRAICHISSEMENT),
        )

    def _lire(self, jeton: str, genre: str) -> Optional[dict[str, Any]]:
        try:
            contenu = jwt.decode(jeton, reglages.secret, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return None
        if contenu.get("typ") != genre or contenu.get("resource") != url_ressource():
            return None
        with session_contexte() as session:
            connexion = session.get(ConnexionChatGPT, uuid.UUID(contenu["cid"]))
            if connexion is None or connexion.revoquee or not utilisateur_autorise(connexion.utilisateur):
                return None
            if genre == "mcp_acces" and (connexion.derniere_utilisation is None or
                                         connexion.derniere_utilisation.replace(tzinfo=timezone.utc)
                                         < _maintenant() - timedelta(minutes=5)):
                connexion.derniere_utilisation = _maintenant()
                session.commit()
            # Les droits retirés dans l'outil s'appliquent aussi aux jetons déjà émis.
            contenu["scopes"] = [s for s in contenu.get("scopes", []) if s in connexion.scopes]
        return contenu

    async def load_access_token(self, token: str) -> AccessToken | None:
        c = self._lire(token, "mcp_acces")
        if c is None:
            return None
        return AccessToken(token=token, client_id=c["client_id"], scopes=c["scopes"], expires_at=int(c["exp"]),
                           resource=c["resource"], subject=c["sub"], claims={"iss": url_ressource(), "cid": c["cid"]})

    async def load_refresh_token(self, client, refresh_token: str) -> RefreshToken | None:
        c = self._lire(refresh_token, "mcp_rafraichissement")
        if c is None or c["client_id"] != client.client_id:
            return None
        return RefreshToken(token=refresh_token, client_id=c["client_id"], scopes=c["scopes"],
                            expires_at=int(c["exp"]), resource=c["resource"], subject=c["sub"])

    async def exchange_refresh_token(self, client, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        c = self._lire(refresh_token.token, "mcp_rafraichissement")
        if c is None:
            raise ValueError("Connexion révoquée")
        accordes = [s for s in (scopes or refresh_token.scopes) if s in refresh_token.scopes]
        return self._jetons(client.client_id, c["sub"], c["cid"], accordes)

    async def revoke_token(self, token: str, token_type_hint: str | None = None) -> None:  # type: ignore[override]
        try:
            contenu = jwt.decode(token, reglages.secret, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return None
        with session_contexte() as session:
            connexion = session.get(ConnexionChatGPT, uuid.UUID(contenu["cid"]))
            if connexion is not None:
                connexion.revoquee = True
                session.commit()
        return None


def _page(titre: str, corps: str) -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(titre)} – Restaurant Albert</title>
<style>body{{font-family:system-ui,sans-serif;max-width:440px;margin:48px auto;padding:0 16px;color:#1f2937}}
h1{{font-size:22px}}label{{display:block;margin-top:14px}}input[type=email],input[type=password]{{width:100%;box-sizing:border-box;
padding:10px;margin-top:6px;border:1px solid #d1d5db;border-radius:8px}}fieldset{{margin-top:18px;border:1px solid #e5e7eb;
border-radius:8px}}.case{{margin-top:8px}}button{{margin-top:20px;padding:11px 18px;border:0;border-radius:8px;
background:#6d28d9;color:#fff;font-weight:600;cursor:pointer}}.muted{{color:#6b7280}}.erreur{{color:#b91c1c}}</style>
</head><body><h1>{html.escape(titre)}</h1>{corps}</body></html>"""
