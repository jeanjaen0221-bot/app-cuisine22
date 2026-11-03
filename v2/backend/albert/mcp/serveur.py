"""Connecteur ChatGPT (MCP) : les mêmes services que le site, au nom de la personne connectée.

Chaque outil vérifie le droit (scope) accordé à la connexion, puis appelle le service :
les règles, le journal et les refus sont donc exactement ceux du site. Les erreurs
reviennent lisibles : {"ok": false, "erreur": {"code", "message", "valeurs_permises"}}.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import AnyHttpUrl
from starlette.responses import Response

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from ..config import reglages
from ..db import session_contexte
from ..domain.erreurs import ErreurMetier
from ..models import Utilisateur
from ..services import achats, bons, catalogue, clients, comptes, devis, fiches, plaintes, salle
from . import liens
from .oauth import SCOPES, SCOPES_PERMIS, FournisseurOAuth, url_ressource, utilisateur_autorise

CONSIGNES = (Path(__file__).parent / "consignes.txt").read_text(encoding="utf-8")
LECTURE = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
ECRITURE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
ANNULATION = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)

fournisseur = FournisseurOAuth()
serveur = MCPServer(
    name="Restaurant Albert",
    title="Restaurant Albert – fiches et devis",
    description="Clients, fiches d'événement, devis et bons pour facturation du Restaurant Albert (prix TVA comprise).",
    instructions=CONSIGNES,
    auth_server_provider=fournisseur,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(url_ressource()),
        resource_server_url=AnyHttpUrl(url_ressource()),
        required_scopes=["lecture"],
        validate_token_resource=True,
        client_registration_options=ClientRegistrationOptions(enabled=True, valid_scopes=SCOPES_PERMIS,
                                                              default_scopes=SCOPES_PERMIS),
        revocation_options=RevocationOptions(enabled=True),
    ),
)


# --------------------------------------------------------------- exécution d'un outil

def executer(scope: str, action: Callable[[Any, Any], Any]) -> dict[str, Any]:
    """Vérifie le droit, ouvre une session, appelle le service, met l'erreur en forme."""
    jeton = get_access_token()
    with session_contexte() as session:
        try:
            if jeton is None or not jeton.subject:
                raise ErreurMetier("non_connecte", "Connexion ChatGPT expirée : se reconnecter.")
            u = session.get(Utilisateur, uuid.UUID(jeton.subject))
            if u is None or not utilisateur_autorise(u):
                raise ErreurMetier("interdit", "Ce compte ne peut plus utiliser ChatGPT.")
            if scope not in jeton.scopes:
                raise ErreurMetier("interdit", f"Droit « {SCOPES[scope]} » non accordé à cette connexion ChatGPT.")
            acteur = comptes.acteur_de(u, canal="chatgpt", scopes=set(jeton.scopes))
            resultat = action(session, acteur)
            return {"ok": True, **resultat} if isinstance(resultat, dict) else {"ok": True, "resultats": resultat}
        except ErreurMetier as e:
            session.rollback()
            return e.en_dict()


def _fiche(session, fiche, alertes: Optional[list[str]] = None) -> dict[str, Any]:
    d = fiches.fiche_dict(session, fiche)
    d["alertes"] = list(dict.fromkeys(d["alertes"] + (alertes or [])))
    return {"fiche": d}


def _devis(session, d, alertes: Optional[list[str]] = None) -> dict[str, Any]:
    sortie = devis.devis_dict(session, d)
    sortie["lien_pdf"] = liens.lien_pdf("devis", d.id)
    return {"devis": sortie, "alertes": alertes or []}


# --------------------------------------------------------------- lecture

@serveur.tool(annotations=LECTURE)
def references_lister() -> dict:
    """Listes à utiliser telles quelles sur une fiche : formules repas et boissons (avec prix TVA comprise),
    privatisations, espaces, types de ligne, allergènes, statuts, heures proposées."""
    return executer("lecture", lambda s, a: catalogue.references(s))


@serveur.tool(annotations=LECTURE)
def clients_rechercher(q: Optional[str] = None, email: Optional[str] = None, tva: Optional[str] = None) -> dict:
    """Chercher un client (nom, contact, email, téléphone, n° TVA). Toujours chercher avant de créer."""
    return executer("lecture", lambda s, a: [clients.client_dict(c) for c in clients.rechercher(s, q, email, tva, limite=20)])


@serveur.tool(annotations=LECTURE)
def client_lire(client_id: str) -> dict:
    """Lire un client, ses 10 dernières fiches et ses devis."""
    def lire(s, a):
        c = clients.obtenir(s, client_id)
        return {"client": clients.client_dict(c),
                "fiches": [fiches.fiche_dict(s, f, complet=False)
                           for f in fiches.lister(s, client_id=str(c.id), periode="toutes", limite=10)],
                "devis": [devis.devis_dict(s, d) for d in devis.lister(s, client_id=str(c.id))][:10]}
    return executer("lecture", lire)


@serveur.tool(annotations=LECTURE)
def fiches_rechercher(q: Optional[str] = None, client_id: Optional[str] = None, jour: Optional[str] = None,
                      du: Optional[str] = None, au: Optional[str] = None, statut: Optional[str] = None,
                      espace: Optional[str] = None, periode: str = "a_venir") -> dict:
    """Chercher des fiches (20 au plus). Par défaut les fiches à venir ; periode = a_venir, passees ou toutes.
    jour/du/au au format AAAA-MM-JJ. Toujours chercher avant de créer une fiche."""
    return executer("lecture", lambda s, a: [fiches.fiche_dict(s, f, complet=False) for f in
                                             fiches.lister(s, q, client_id, jour, du, au, statut, espace, periode, 20)])


@serveur.tool(annotations=LECTURE)
def fiche_lire(fiche_id: str) -> dict:
    """Lire une fiche complète (lignes, notes, version, alertes, devis et bon liés)."""
    return executer("lecture", lambda s, a: _fiche(s, fiches.obtenir(s, fiche_id)))


@serveur.tool(annotations=LECTURE)
def catalogue_rechercher(q: Optional[str] = None, categorie: Optional[str] = None) -> dict:
    """Chercher dans le menu Prix (insensible aux accents et à l'ordre des mots). categorie : entree, plat,
    dessert, supplement, coupe, formule_repas, formule_boissons, privatisation. Prix TVA comprise."""
    return executer("lecture", lambda s, a: [catalogue.produit_dict(p) for p in
                                             catalogue.lister_produits(s, categorie, q, actifs_seulement=True)][:30])


@serveur.tool(annotations=LECTURE)
def devis_rechercher(client_id: Optional[str] = None, fiche_id: Optional[str] = None,
                     statut: Optional[str] = None) -> dict:
    """Lister des devis (statuts : brouillon, valide, transmis, envoye, accepte, refuse)."""
    return executer("lecture", lambda s, a: [devis.devis_dict(s, d) for d in
                                             devis.lister(s, statut, client_id, fiche_id)][:20])


@serveur.tool(annotations=LECTURE)
def devis_lire(devis_id: str) -> dict:
    """Lire un devis : lignes, total TVA comprise, statut, manques, lien PDF."""
    return executer("lecture", lambda s, a: _devis(s, devis.obtenir(s, devis_id)))


@serveur.tool(annotations=LECTURE)
def bon_facturation_lire(bon_id: str) -> dict:
    """Lire un bon pour facturation (réel servi, total TVA comprise, écart avec le devis)."""
    return executer("lecture", lambda s, a: {"bon": {**bons.bon_dict(s, bons.obtenir(s, bon_id)),
                                                     "lien_pdf": liens.lien_pdf("bon", bon_id)}})


@serveur.tool(annotations=LECTURE)
def pdf_lien(type: str, id: str) -> dict:
    """Lien de téléchargement valable 15 minutes. type : fiche_salle, fiche_cuisine, fiche_complete, devis, bon."""
    def lien(s, a):
        if type.startswith("fiche"):
            fiches.obtenir(s, id)
        elif type == "devis":
            devis.obtenir(s, id)
        elif type == "bon":
            bons.obtenir(s, id)
        return {"lien": liens.lien_pdf(type, id), "valable": "15 minutes"}
    return executer("lecture", lien)


@serveur.tool(annotations=LECTURE)
def salle_lire(date: str, service: str) -> dict:
    """Plan de salle d'un service (date AAAA-MM-JJ, service midi ou soir) : réservations et tables attribuées.
    Lecture seule : le placement se fait dans l'outil."""
    def lire(s, a):
        svc = salle.obtenir_service(s, date, service, creer=False)
        if svc is None:
            return {"service": None, "message": "Aucun plan de salle pour ce service."}
        d = salle.service_dict(s, svc)
        return {"service": {k: d[k] for k in ("date", "service", "reservations", "alertes", "totaux")}}
    return executer("lecture", lire)


# --------------------------------------------------------------- clients et fiches

@serveur.tool(annotations=ECRITURE)
def client_creer(nom: str, type: str = "particulier", email: Optional[str] = None, telephone: Optional[str] = None,
                 contact_prenom: Optional[str] = None, contact_nom: Optional[str] = None,
                 rue: Optional[str] = None, numero: Optional[str] = None, boite: Optional[str] = None,
                 code_postal: Optional[str] = None, ville: Optional[str] = None, pays: Optional[str] = None,
                 tva: Optional[str] = None, reference_po: Optional[str] = None, langue: Optional[str] = None,
                 preferences: Optional[str] = None, confirmer_doublon: bool = False) -> dict:
    """Créer un client (type : particulier ou entreprise). Nom + email ou téléphone obligatoires.
    Refusé avec doublon_probable si un client proche existe : utiliser plutôt celui-là."""
    donnees = {k: v for k, v in locals().items() if v is not None}
    return executer("fiches:ecrire", lambda s, a: {"client": clients.client_dict(clients.creer(s, a, donnees))})


@serveur.tool(annotations=ECRITURE)
def client_modifier(client_id: str, version: int, changements: dict) -> dict:
    """Modifier seulement les champs donnés d'un client (avec la version lue juste avant)."""
    return executer("fiches:ecrire", lambda s, a: {"client": clients.client_dict(
        clients.modifier(s, a, uuid.UUID(client_id), changements, version))})


@serveur.tool(annotations=ECRITURE)
def fiche_creer(client_id: str, date: str, heure: str, couverts: int, cle_idempotence: str,
                formule_repas: Optional[str] = None, formule_boissons: Optional[str] = None,
                privatisation: Optional[str] = None, espace: Optional[str] = None,
                allergenes: Optional[list[str]] = None, notes_salle: Optional[str] = None,
                notes_cuisine: Optional[str] = None, contact_sur_place: Optional[str] = None,
                telephone_sur_place: Optional[str] = None, lignes: Optional[list[dict]] = None) -> dict:
    """Créer une fiche en brouillon. client_id, date (AAAA-MM-JJ), heure (HH:MM) et couverts sont obligatoires :
    les demander plutôt que de les deviner. cle_idempotence : identifiant unique de cette demande (évite un doublon
    si l'appel est répété). lignes : [{type: entrée|plat|dessert|supplément, libelle, quantite, commentaire?}]."""
    donnees = {k: v for k, v in locals().items() if v is not None}
    return executer("fiches:ecrire", lambda s, a: _fiche(s, *fiches.creer(s, a, donnees)))


@serveur.tool(annotations=ECRITURE)
def fiche_modifier(fiche_id: str, version: int, changements: dict) -> dict:
    """Modifier seulement les champs demandés (date, heure, couverts, formule_repas, formule_boissons,
    privatisation, espace, allergenes, notes_salle, notes_cuisine, contact_sur_place, telephone_sur_place,
    lignes). « lignes » remplace toute la liste : pour une seule ligne, utiliser fiche_ligne_ajouter/retirer."""
    return executer("fiches:ecrire", lambda s, a: _fiche(s, *fiches.modifier(s, a, fiche_id, changements, version)))


@serveur.tool(annotations=ECRITURE)
def fiche_ligne_ajouter(fiche_id: str, version: int, type: str, libelle: str, quantite: int,
                        commentaire: Optional[str] = None) -> dict:
    """Ajouter un plat ou un supplément ; si la même ligne existe, sa quantité est remplacée."""
    ligne = {"type": type, "libelle": libelle, "quantite": quantite, "commentaire": commentaire}
    return executer("fiches:ecrire", lambda s, a: _fiche(s, *fiches.ajouter_ligne(s, a, fiche_id, ligne, version)))


@serveur.tool(annotations=ECRITURE)
def fiche_ligne_retirer(fiche_id: str, version: int, type: str, libelle: str) -> dict:
    """Retirer une ligne (plat ou supplément) sans toucher au reste."""
    return executer("fiches:ecrire", lambda s, a: _fiche(s, *fiches.retirer_ligne(s, a, fiche_id, type, libelle, version)))


@serveur.tool(annotations=ECRITURE)
def fiche_dupliquer(fiche_id: str, nouvelle_date: Optional[str] = None) -> dict:
    """Copier une fiche (en brouillon), éventuellement à une autre date."""
    return executer("fiches:ecrire", lambda s, a: _fiche(s, fiches.dupliquer(s, a, fiche_id, nouvelle_date)))


@serveur.tool(annotations=ANNULATION)
def fiche_annuler(fiche_id: str, motif: str, jeton_confirmation: Optional[str] = None) -> dict:
    """Annuler une fiche en deux temps. Premier appel sans jeton : renvoie l'aperçu et un jeton_confirmation.
    Montrer l'aperçu, attendre un « oui » explicite, puis rappeler avec ce jeton. Rien n'est jamais supprimé."""
    return executer("fiches:ecrire", lambda s, a: _fiche(s, fiches.annuler(s, a, fiche_id, motif, jeton_confirmation)))


# --------------------------------------------------------------- devis et bons

@serveur.tool(annotations=ECRITURE)
def devis_preparer(fiche_id: str, remarques_client: Optional[str] = None, validite_jours: Optional[int] = None) -> dict:
    """Préparer (ou actualiser) le devis en brouillon d'une fiche, aux prix TVA comprise du menu Prix.
    Le total est calculé par le serveur. La validation et la transmission à la compta se font dans l'outil."""
    donnees = {k: v for k, v in {"remarques_client": remarques_client, "validite_jours": validite_jours}.items()
               if v is not None}
    return executer("devis:preparer", lambda s, a: _devis(s, *devis.preparer(s, a, fiche_id, donnees)))


@serveur.tool(annotations=ECRITURE)
def devis_nouvelle_version(devis_id: str) -> dict:
    """Après un changement demandé par le client sur un devis déjà transmis : nouvelle version en brouillon
    calculée depuis la fiche actuelle (l'ancienne passe en « remplacé »)."""
    return executer("devis:preparer", lambda s, a: _devis(s, *devis.nouvelle_version(s, a, devis_id)))


@serveur.tool(annotations=ECRITURE)
def bon_facturation_preparer(devis_id: str, couverts_reels: Optional[int] = None,
                             extras: Optional[list[dict]] = None, remarques_compta: Optional[str] = None) -> dict:
    """Après l'événement : bon pour facturation en brouillon depuis un devis accepté. extras :
    [{nom, quantite}] pris dans le menu Prix. Renvoie le total TVA comprise et l'écart avec le devis."""
    def preparer(s, a):
        b, alertes = bons.preparer(s, a, devis_id, couverts_reels, extras, remarques_compta)
        return {"bon": {**bons.bon_dict(s, b), "lien_pdf": liens.lien_pdf("bon", b.id)}, "alertes": alertes}
    return executer("devis:preparer", preparer)


# --------------------------------------------------------------- plaintes

@serveur.tool(annotations=ECRITURE)
def plainte_preparer(recit: str, date: Optional[str] = None, heure: Optional[str] = None,
                     lieu: Optional[str] = None, employes: Optional[str] = None, client_nom: Optional[str] = None,
                     client_id: Optional[str] = None, fiche_id: Optional[str] = None,
                     contexte: Optional[str] = None, description: Optional[str] = None,
                     reaction_personnel: Optional[str] = None, consequences: Optional[str] = None,
                     mesures_prises: Optional[str] = None, observations: Optional[str] = None,
                     gravite: str = "faible", plainte_id: Optional[str] = None, version: Optional[int] = None) -> dict:
    """Rédiger (ou corriger, avec plainte_id et version) un rapport de plainte en brouillon. recit = récit de
    l'utilisateur tel quel. Ton neutre et factuel, ordre chronologique, rien d'inventé : une donnée inconnue reste
    vide. gravite : faible, moyen ou eleve. L'équipe relit et valide la plainte dans l'outil."""
    donnees = {k: v for k, v in {
        "recit_brut": recit, "date": date, "heure": heure, "lieu": lieu, "employes": employes,
        "client_nom": client_nom, "client_id": client_id, "fiche_id": fiche_id, "contexte": contexte,
        "description": description, "reaction_personnel": reaction_personnel, "consequences": consequences,
        "mesures_prises": mesures_prises, "observations": observations, "gravite": gravite}.items() if v is not None}

    def preparer(s, a):
        p = plaintes.modifier(s, a, plainte_id, donnees, version) if plainte_id else plaintes.creer(s, a, donnees)
        return {"plainte": plaintes.plainte_dict(p)}
    return executer("plaintes:preparer", preparer)


# --------------------------------------------------------------- commandes fournisseurs

@serveur.tool(annotations=LECTURE)
def reassort_lire(restant: Optional[dict] = None) -> dict:
    """Quantités de boissons à commander, calculées par l'outil. restant : {boisson_id: quantité restante en stock}
    donnée par l'utilisateur (0 si non précisé). Renvoie aussi le fournisseur préféré de chaque boisson."""
    def lire(s, a):
        return {"reassort": [r for r in achats.reassort(s, restant or {}) if r["reassort"]]}
    return executer("achats:preparer", lire)


@serveur.tool(annotations=ECRITURE)
def achat_preparer(lignes: list[dict], cle_idempotence: str, fournisseur_id: Optional[str] = None,
                   note: Optional[str] = None) -> dict:
    """Préparer un bon de commande fournisseur en brouillon. lignes : [{boisson_id ou nom, quantite}] — quantités
    données par l'utilisateur ou reprises de reassort_lire, jamais inventées. Le bon n'est pas envoyé : l'équipe le
    relit et l'envoie elle-même au fournisseur."""
    return executer("achats:preparer", lambda s, a: {"commande": achats.bon_dict(
        achats.creer_bon(s, a, fournisseur_id, lignes, note, cle_idempotence))})


# --------------------------------------------------------------- montage dans FastAPI

def _securite_transport() -> TransportSecuritySettings:
    publique = urlsplit(reglages.url_publique)
    hotes = ["127.0.0.1:*", "localhost:*", "localhost", "[::1]:*"]
    origines = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if publique.netloc:
        hotes.append(publique.netloc)
        origines.append(f"{publique.scheme}://{publique.netloc}")
    return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hotes,
                                     allowed_origins=origines)


@serveur.custom_route("/connexion", methods=["GET"])
async def _page_connexion(request: Request) -> Response:
    return await fournisseur.page_connexion(request)


@serveur.custom_route("/connexion", methods=["POST"])
async def _valider_connexion(request: Request) -> Response:
    return await fournisseur.valider_connexion(request)


def monter_mcp(app: FastAPI) -> None:
    sous_app = serveur.streamable_http_app(streamable_http_path="/", json_response=True, stateless_http=False,
                                           transport_security=_securite_transport())

    @app.middleware("http")
    async def decouverte_oauth(request: Request, call_next):
        # RFC 8414 : les métadonnées d'un serveur monté sous /mcp sont cherchées à la racine.
        if request.url.path == "/.well-known/oauth-authorization-server/mcp":
            chemin = "/mcp/.well-known/oauth-authorization-server"
            request.scope["path"] = chemin
            request.scope["raw_path"] = chemin.encode("ascii")
        return await call_next(request)

    @app.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
    def ressource_protegee():
        return JSONResponse({"resource": url_ressource(), "authorization_servers": [url_ressource()],
                             "scopes_supported": SCOPES_PERMIS, "bearer_methods_supported": ["header"]})

    app.mount("/mcp", sous_app)
    contextes = getattr(app.state, "contextes", [])
    contextes.append(serveur.session_manager.run)
    app.state.contextes = contextes
