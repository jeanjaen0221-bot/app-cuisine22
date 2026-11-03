"""Connexion, références, tableau de bord, paramètres, utilisateurs, journal."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import reglages
from ..models import Audit, BonFacturation, Devis, Utilisateur
from ..services import catalogue, comptes, devis as devis_service, fiches
from ..services.contexte import Acteur, ecrire_parametres, lire_parametres
from .deps import COOKIE_SESSION, acteur_connecte, corps, session_db

router = APIRouter(prefix="/api")


def _avec_cookie(utilisateur: Utilisateur) -> JSONResponse:
    reponse = JSONResponse({"ok": True, "utilisateur": comptes.utilisateur_dict(utilisateur)})
    reponse.set_cookie(COOKIE_SESSION, comptes.emettre_jeton(utilisateur), httponly=True, samesite="lax",
                       secure=reglages.cookie_securise, max_age=reglages.session_heures * 3600, path="/")
    return reponse


@router.get("/auth/etat")
def etat(session: Session = Depends(session_db)):
    return {"configuration_requise": comptes.configuration_requise(session)}


@router.post("/auth/configuration")
def configuration(donnees: dict = Body(...), session: Session = Depends(session_db)):
    u = comptes.creer_premier_admin(session, donnees.get("email"), donnees.get("mot_de_passe") or "", donnees.get("nom") or "")
    return _avec_cookie(u)


@router.post("/auth/connexion")
def connexion(request: Request, donnees: dict = Body(...), session: Session = Depends(session_db)):
    ip = request.client.host if request.client else ""
    u = comptes.authentifier(session, donnees.get("email") or "", donnees.get("mot_de_passe") or "", ip)
    return _avec_cookie(u)


@router.post("/auth/deconnexion")
def deconnexion():
    reponse = JSONResponse({"ok": True})
    reponse.delete_cookie(COOKIE_SESSION, path="/")
    return reponse


@router.get("/auth/moi")
def moi(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    u = session.get(Utilisateur, acteur.utilisateur_id)
    return {**comptes.utilisateur_dict(u), "peut": {d: acteur.peut(d) for d in
                                                   ("fiches", "devis", "devis_valider", "compta", "prix", "admin")}}


@router.get("/references")
def references(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("lecture")
    return catalogue.references(session)


@router.get("/tableau-de-bord")
def tableau_de_bord(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("lecture")
    jour = fiches.aujourd_hui()
    sortie: dict[str, Any] = {"prix_manquants": catalogue.compter_prix_manquants(session)}
    if acteur.peut("fiches"):
        prochaines = fiches.lister(session, du=jour, au=jour + timedelta(days=7), limite=200)
        sortie["prochaines_fiches"] = [fiches.fiche_dict(session, f, complet=False) for f in prochaines
                                       if f.statut != "annulee"]
        sortie["rappels_plats"] = [fiches.fiche_dict(session, f, complet=False) for f in fiches.rappels(session)]
        a_mettre_a_jour, sans_reponse = [], []
        for d in devis_service.lister(session):
            dd = devis_service.devis_dict(session, d)
            if dd["a_mettre_a_jour"] and d.statut not in ("refuse",):
                a_mettre_a_jour.append(dd)
            if d.statut in ("transmis", "envoye"):
                sans_reponse.append(dd)
        sortie["devis_a_mettre_a_jour"] = a_mettre_a_jour
        sortie["devis_sans_reponse"] = sans_reponse
        # Événements passés dont le devis est accepté mais sans bon pour facturation.
        avec_bon = set(session.scalars(select(BonFacturation.devis_id)))
        sortie["bons_a_faire"] = [
            devis_service.devis_dict(session, d) for d in session.scalars(select(Devis).where(Devis.statut == "accepte"))
            if d.id not in avec_bon and d.fiche.date < jour
        ]
    if acteur.peut("compta"):
        sortie["compta"] = {
            "a_envoyer": len(devis_service.lister(session, statut="transmis")),
            "a_facturer": session.query(BonFacturation).filter(BonFacturation.statut == "transmis").count(),
        }
    return sortie


@router.get("/parametres")
def parametres(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("lecture")
    return lire_parametres(session)


@router.patch("/parametres")
def modifier_parametres(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                        session: Session = Depends(session_db)):
    return ecrire_parametres(session, acteur, corps(donnees))


@router.get("/utilisateurs")
def utilisateurs(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("admin")
    return [comptes.utilisateur_dict(u) for u in session.scalars(select(Utilisateur).order_by(Utilisateur.email))]


@router.post("/utilisateurs", status_code=201)
def creer_utilisateur(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                      session: Session = Depends(session_db)):
    return comptes.utilisateur_dict(comptes.creer(session, acteur, corps(donnees)))


@router.patch("/utilisateurs/{utilisateur_id}")
def modifier_utilisateur(utilisateur_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                         session: Session = Depends(session_db)):
    return comptes.utilisateur_dict(comptes.modifier(session, acteur, utilisateur_id, corps(donnees)))


@router.get("/journal")
def journal(objet_type: Optional[str] = None, objet_id: Optional[str] = None, canal: Optional[str] = None,
            limite: int = 200, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    if not (objet_type and objet_id):
        acteur.exiger("admin")  # le journal complet est réservé aux admins
    else:
        acteur.exiger("lecture")
    stmt = select(Audit)
    if objet_type:
        stmt = stmt.where(Audit.objet_type == objet_type)
    if objet_id:
        stmt = stmt.where(Audit.objet_id == objet_id)
    if canal:
        stmt = stmt.where(Audit.canal == canal)
    lignes = session.scalars(stmt.order_by(Audit.le.desc()).limit(max(1, min(limite, 1000))))
    return [{"id": str(a.id), "le": a.le.isoformat(), "utilisateur": a.utilisateur_email, "canal": a.canal,
             "action": a.action, "objet_type": a.objet_type, "objet_id": a.objet_id, "resume": a.resume,
             "avant": a.avant, "apres": a.apres} for a in lignes]



# --------------------------------------------------------------- connexions ChatGPT

@router.get("/chatgpt")
def chatgpt(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    from ..mcp.oauth import SCOPES, url_ressource, utilisateur_autorise
    from ..models import ConnexionChatGPT

    acteur.exiger("lecture")
    stmt = select(ConnexionChatGPT).order_by(ConnexionChatGPT.cree_le.desc())
    if not acteur.peut("admin"):
        stmt = stmt.where(ConnexionChatGPT.utilisateur_id == acteur.utilisateur_id)
    u = session.get(Utilisateur, acteur.utilisateur_id)
    return {
        "url_connecteur": url_ressource(),
        "droits": [{"cle": k, "libelle": v} for k, v in SCOPES.items()],
        "autorise": utilisateur_autorise(u),
        "connexions": [{
            "id": str(c.id), "utilisateur": c.utilisateur.email, "application": c.client_nom, "droits": c.scopes,
            "cree_le": c.cree_le.isoformat(), "revoquee": c.revoquee,
            "derniere_utilisation": c.derniere_utilisation.isoformat() if c.derniere_utilisation else None,
        } for c in session.scalars(stmt.limit(100))],
    }


@router.post("/chatgpt/connexions/{connexion_id}/revoquer")
def revoquer_connexion(connexion_id: str, acteur: Acteur = Depends(acteur_connecte),
                       session: Session = Depends(session_db)):
    import uuid

    from ..domain.erreurs import introuvable
    from ..models import ConnexionChatGPT
    from ..services.contexte import journaliser

    c = session.get(ConnexionChatGPT, uuid.UUID(connexion_id))
    if c is None or (c.utilisateur_id != acteur.utilisateur_id and not acteur.peut("admin")):
        raise introuvable("Connexion")
    c.revoquee = True
    journaliser(session, acteur, "chatgpt.revoquer", "connexion_chatgpt", c.id, f"{c.client_nom} ({c.utilisateur.email})")
    session.commit()
    return {"ok": True}
