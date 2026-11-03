"""Application FastAPI : API du site (/api), connecteur ChatGPT (/mcp), site compilé (/)."""
from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import reglages
from .db import session_contexte
from .domain.erreurs import ErreurMetier
from .services.initialisation import initialiser_catalogue
from .api import routes_base, routes_documents, routes_metier, routes_salle

journal = logging.getLogger("albert")

METHODES_SURES = {"GET", "HEAD", "OPTIONS"}


def creer_app(avec_mcp: bool = True, au_demarrage: bool = False) -> FastAPI:
    @asynccontextmanager
    async def cycle_de_vie(app: FastAPI):
        if au_demarrage:
            demarrage()
        async with AsyncExitStack() as pile:
            for contexte in getattr(app.state, "contextes", []):
                await pile.enter_async_context(contexte())
            yield

    app = FastAPI(title="Restaurant Albert — v2", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=cycle_de_vie)

    @app.middleware("http")
    async def protection_csrf(request: Request, call_next):
        # Le cookie de session est SameSite=Lax ; en plus, toute écriture sur /api doit porter
        # l'en-tête X-Albert, qu'un autre site ne peut pas ajouter sans autorisation CORS.
        if request.url.path.startswith("/api/") and request.method not in METHODES_SURES:
            if request.headers.get("x-albert") != "1":
                return JSONResponse(ErreurMetier("interdit", "Requête refusée (en-tête manquant).").en_dict(),
                                    status_code=403)
        return await call_next(request)

    @app.exception_handler(ErreurMetier)
    async def erreur_metier(_request: Request, exc: ErreurMetier):
        return JSONResponse(exc.en_dict(), status_code=exc.statut_http)

    @app.exception_handler(RequestValidationError)
    async def erreur_validation(_request: Request, exc: RequestValidationError):
        champs = ", ".join(".".join(str(x) for x in e.get("loc", [])[1:]) for e in exc.errors())
        return JSONResponse(ErreurMetier("valeur_non_permise", f"Requête invalide ({champs}).").en_dict(),
                            status_code=422)

    @app.exception_handler(Exception)
    async def erreur_inattendue(request: Request, exc: Exception):
        journal.exception("Erreur inattendue sur %s %s", request.method, request.url.path)
        return JSONResponse({"ok": False, "erreur": {"code": "erreur_serveur",
                                                     "message": "Erreur inattendue. Réessayer ou prévenir l'administrateur."}},
                            status_code=500)

    app.include_router(routes_base.router)
    app.include_router(routes_metier.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_salle.router)

    @app.get("/sante")
    def sante():
        return {"ok": True}

    if avec_mcp:
        from .mcp.serveur import monter_mcp

        monter_mcp(app)

    _servir_site(app)
    return app


def _servir_site(app: FastAPI) -> None:
    dossier = Path(reglages.dossier_frontend) if reglages.dossier_frontend else \
        Path(__file__).resolve().parents[2] / "frontend" / "dist"
    index = dossier / "index.html"
    if not index.exists():
        return
    if (dossier / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dossier / "assets"), name="assets")

    @app.get("/{chemin:path}", include_in_schema=False)
    def site(chemin: str):
        if chemin.startswith(("api/", "mcp")):
            return JSONResponse({"ok": False, "erreur": {"code": "introuvable", "message": "Introuvable."}}, 404)
        fichier = (dossier / chemin).resolve()
        if chemin and fichier.is_file() and dossier.resolve() in fichier.parents:
            return FileResponse(fichier)
        return FileResponse(index)


def demarrage() -> None:
    with session_contexte() as session:
        initialiser_catalogue(session)


app = creer_app(au_demarrage=True)
