"""Plan de salle : plan de base, plans des services, placement, PDF."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.erreurs import ErreurMetier
from ..domain.normalisation import lire_date
from ..models import ServiceSalle
from ..pdf.documents import nom_fichier
from ..salle.pdf import pdf_annote, pdf_plan, pdf_service
from ..services import salle
from ..services.contexte import Acteur
from .deps import acteur_connecte, corps, reponse_pdf, session_db

router = APIRouter(prefix="/api/salle")
TAILLE_MAX_PDF = 10 * 1024 * 1024


def _plan(p: Any) -> dict[str, Any]:
    return {"id": str(p.id), "donnees": p.donnees, "etiquettes": salle.etiquettes(p.donnees or {}),
            "modifie_le": p.modifie_le.isoformat() if p.modifie_le else None}


async def _lire_pdf(fichier: UploadFile) -> bytes:
    contenu = await fichier.read()
    if len(contenu) > TAILLE_MAX_PDF:
        raise ErreurMetier("regle_metier", "PDF trop lourd (10 Mo au maximum).")
    if not contenu.startswith(b"%PDF"):
        raise ErreurMetier("valeur_non_permise", "Le fichier n'est pas un PDF.")
    return contenu


@router.get("/plan")
def lire_plan(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return _plan(salle.plan_de_base(session))


@router.put("/plan")
def enregistrer_plan(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                     session: Session = Depends(session_db)):
    return _plan(salle.enregistrer_plan(session, acteur, corps(donnees).get("donnees")))


@router.post("/plan/numeroter")
def numeroter_plan(donnees: dict = Body(default={}), acteur: Acteur = Depends(acteur_connecte),
                   session: Session = Depends(session_db)):
    d = corps(donnees or {})
    return _plan(salle.numeroter_plan(session, acteur, d.get("table_ids"), d.get("prefixe") or "", int(d.get("debut") or 1)))


@router.get("/plan/pdf")
def pdf_du_plan(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    p = salle.plan_de_base(session)
    return reponse_pdf(pdf_plan(p.donnees or {}, salle.etiquettes(p.donnees or {})), "plan_de_salle.pdf")


@router.get("/services")
def lister_services(du: Optional[str] = None, acteur: Acteur = Depends(acteur_connecte),
                    session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    stmt = select(ServiceSalle).order_by(ServiceSalle.date.desc(), ServiceSalle.service)
    if du:
        stmt = stmt.where(ServiceSalle.date >= lire_date(du))
    return [{"id": str(s.id), "date": s.date.isoformat(), "service": s.service} for s in session.scalars(stmt.limit(60))]


@router.post("/services")
def ouvrir_service(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                   session: Session = Depends(session_db)):
    """Ouvre le plan d'un service (le crée depuis le plan de base s'il n'existe pas)."""
    acteur.exiger("fiches")
    d = corps(donnees)
    return salle.service_dict(session, salle.obtenir_service(session, d.get("date"), d.get("service")))


@router.get("/services/{service_id}")
def lire_service(service_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return salle.service_dict(session, salle.service_par_id(session, service_id))


@router.put("/services/{service_id}")
def modifier_service(service_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                     session: Session = Depends(session_db)):
    svc = salle.service_par_id(session, service_id)
    return salle.service_dict(session, salle.modifier_service(session, acteur, svc, corps(donnees).get("donnees")))


@router.post("/services/{service_id}/import-pdf")
async def importer_pdf(service_id: str, fichier: UploadFile = File(...), acteur: Acteur = Depends(acteur_connecte),
                       session: Session = Depends(session_db)):
    svc = salle.service_par_id(session, service_id)
    return salle.service_dict(session, salle.importer_pdf(session, acteur, svc, await _lire_pdf(fichier)))


@router.get("/services/{service_id}/pdf")
def pdf_du_service(service_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    svc = salle.service_par_id(session, service_id)
    d = salle.service_dict(session, svc)
    return reponse_pdf(pdf_service(svc.donnees or {}, d["etiquettes"], {"tables": d["affectations"]["tables"]},
                                   d["reservations"]), nom_fichier("salle", svc.date, svc.service))


@router.post("/services/{service_id}/pdf-annote")
async def pdf_annote_du_service(service_id: str, fichier: UploadFile = File(...), page_debut: int = Form(0),
                                debut_y_mm: float = Form(95.0), hauteur_ligne_mm: float = Form(13.5),
                                colonne_x_mm: float = Form(137.0), acteur: Acteur = Depends(acteur_connecte),
                                session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    svc = salle.service_par_id(session, service_id)
    d = salle.service_dict(session, svc)
    contenu = pdf_annote(await _lire_pdf(fichier), svc.donnees or {}, d["etiquettes"],
                         {"tables": d["affectations"]["tables"]}, d["reservations"], page_debut, debut_y_mm,
                         hauteur_ligne_mm, colonne_x_mm)
    return reponse_pdf(contenu, nom_fichier("salle_annotee", svc.date, svc.service), telecharger=True)


# Après les routes précises (import-pdf, pdf-annote) : sinon elles seraient prises pour une action.
@router.post("/services/{service_id}/{action}")
def action_service(service_id: str, action: str, donnees: dict = Body(default={}),
                   acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    svc = salle.service_par_id(session, service_id)
    d = corps(donnees or {})
    if action == "placement-auto":
        svc = salle.placement_automatique(session, acteur, svc)
    elif action == "affecter":
        svc = salle.affecter(session, acteur, svc, d.get("table_id"), d.get("reservation_id"), d.get("pax"))
    elif action == "reinitialiser":
        svc = salle.reinitialiser(session, acteur, svc, bool(d.get("depuis_le_plan")))
    elif action == "numeroter":
        svc = salle.numeroter_service(session, acteur, svc, d.get("table_ids"), d.get("prefixe") or "", int(d.get("debut") or 1))
    elif action == "retirer-import":
        svc = salle.retirer_import(session, acteur, svc)
    elif action == "supprimer":
        salle.supprimer_service(session, acteur, svc)
        return {"ok": True}
    else:
        raise ErreurMetier("valeur_non_permise", f"Action inconnue : {action}.",
                           valeurs_permises=["placement-auto", "affecter", "reinitialiser", "numeroter",
                                             "retirer-import", "supprimer"])
    return salle.service_dict(session, svc)
