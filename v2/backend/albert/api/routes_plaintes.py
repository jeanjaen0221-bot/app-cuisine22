"""Plaintes et notes de l'équipe."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ..pdf.documents import nom_fichier, pdf_plainte
from ..services import plaintes
from ..services.contexte import Acteur
from .deps import acteur_connecte, corps, reponse_pdf, session_db

router = APIRouter(prefix="/api")


@router.get("/plaintes")
def lister(q: Optional[str] = None, statut: Optional[str] = None, client_id: Optional[str] = None,
           acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return [plaintes.plainte_dict(p) for p in plaintes.lister(session, q, statut, client_id)]


@router.post("/plaintes", status_code=201)
def creer(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    return plaintes.plainte_dict(plaintes.creer(session, acteur, corps(donnees)))


@router.get("/plaintes/{plainte_id}")
def lire(plainte_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return plaintes.plainte_dict(plaintes.obtenir(session, plainte_id))


@router.patch("/plaintes/{plainte_id}")
def modifier(plainte_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
             session: Session = Depends(session_db)):
    donnees = corps(donnees)
    version = donnees.pop("version", None)
    return plaintes.plainte_dict(plaintes.modifier(session, acteur, plainte_id, donnees, version))


@router.delete("/plaintes/{plainte_id}")
def supprimer(plainte_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    plaintes.supprimer(session, acteur, plainte_id)
    return {"ok": True}


@router.get("/plaintes/{plainte_id}/pdf")
def pdf(plainte_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    p = plaintes.plainte_dict(plaintes.obtenir(session, plainte_id))
    return reponse_pdf(pdf_plainte(p), nom_fichier("plainte", p["date"], p.get("client_nom")))


@router.get("/notes")
def notes(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return [plaintes.note_dict(n) for n in plaintes.lister_notes(session)]


@router.post("/notes", status_code=201)
def creer_note(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    return plaintes.note_dict(plaintes.enregistrer_note(session, acteur, corps(donnees)))


@router.patch("/notes/{note_id}")
def modifier_note(note_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                  session: Session = Depends(session_db)):
    return plaintes.note_dict(plaintes.enregistrer_note(session, acteur, corps(donnees), note_id))


@router.delete("/notes/{note_id}")
def supprimer_note(note_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    plaintes.supprimer_note(session, acteur, note_id)
    return {"ok": True}
