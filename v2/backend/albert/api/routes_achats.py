"""Boissons, fournisseurs, réassort et bons de commande."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..domain.erreurs import ErreurMetier
from ..pdf.documents import nom_fichier, pdf_bon_commande
from ..services import achats
from ..services.contexte import Acteur, lire_parametres
from .deps import acteur_connecte, corps, reponse_pdf, session_db

router = APIRouter(prefix="/api/achats")


@router.get("/fournisseurs")
def fournisseurs(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return [achats.fournisseur_dict(f) for f in achats.lister_fournisseurs(session)]


@router.post("/fournisseurs", status_code=201)
def creer_fournisseur(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                      session: Session = Depends(session_db)):
    return achats.fournisseur_dict(achats.enregistrer_fournisseur(session, acteur, corps(donnees)))


@router.patch("/fournisseurs/{fid}")
def modifier_fournisseur(fid: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                         session: Session = Depends(session_db)):
    return achats.fournisseur_dict(achats.enregistrer_fournisseur(session, acteur, corps(donnees), fid))


@router.get("/boissons")
def boissons(q: Optional[str] = None, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return achats.lister_boissons(session, q)


@router.post("/boissons", status_code=201)
def creer_boisson(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    b = achats.enregistrer_boisson(session, acteur, corps(donnees))
    return next(x for x in achats.lister_boissons(session) if x["id"] == str(b.id))


@router.patch("/boissons/{bid}")
def modifier_boisson(bid: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                     session: Session = Depends(session_db)):
    b = achats.enregistrer_boisson(session, acteur, corps(donnees), bid)
    return next(x for x in achats.lister_boissons(session) if x["id"] == str(b.id))


@router.post("/boissons/import")
async def importer_boissons(fichier: UploadFile = File(...), categorie: Optional[str] = Form(None),
                            unite: Optional[str] = Form(None), acteur: Acteur = Depends(acteur_connecte),
                            session: Session = Depends(session_db)):
    contenu = await fichier.read()
    if len(contenu) > 10 * 1024 * 1024:
        raise ErreurMetier("regle_metier", "Fichier trop lourd (10 Mo au maximum).")
    return achats.importer_boissons(session, acteur, fichier.filename or "", contenu, categorie or None, unite or None)


@router.post("/reassort")
def calculer_reassort(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                      session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    d = corps(donnees)
    return achats.reassort(session, d.get("restant") or {}, d.get("cible") or "max", bool(d.get("arrondi_colis", True)))


@router.post("/reassort/commander", status_code=201)
def commander_reassort(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                       session: Session = Depends(session_db)):
    bons = achats.bons_depuis_reassort(session, acteur, corps(donnees).get("quantites") or {})
    return [achats.bon_dict(b) for b in bons]


@router.get("/commandes")
def commandes(statut: Optional[str] = None, fournisseur_id: Optional[str] = None,
              acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return [achats.bon_dict(b) for b in achats.lister_bons(session, statut, fournisseur_id)]


@router.post("/commandes", status_code=201)
def creer_commande(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    d = corps(donnees)
    return achats.bon_dict(achats.creer_bon(session, acteur, d.get("fournisseur_id"), d.get("lignes") or [], d.get("note")))


@router.get("/commandes/{bid}")
def lire_commande(bid: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return achats.bon_dict(achats.obtenir_bon(session, bid))


@router.patch("/commandes/{bid}")
def modifier_commande(bid: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                      session: Session = Depends(session_db)):
    d = corps(donnees)
    version = d.pop("version", None)
    return achats.bon_dict(achats.modifier_bon(session, acteur, bid, d, version))


@router.post("/commandes/{bid}/statut")
def statut_commande(bid: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                    session: Session = Depends(session_db)):
    achats.changer_statut(session, acteur, bid, corps(donnees).get("statut"))
    return achats.bon_dict(achats.obtenir_bon(session, bid))


@router.get("/commandes/{bid}/pdf")
def pdf_commande(bid: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    bon = achats.bon_dict(achats.obtenir_bon(session, bid))
    return reponse_pdf(pdf_bon_commande(bon, lire_parametres(session)), nom_fichier("commande", bon["numero"], bon["fournisseur"]))


@router.get("/commandes/{bid}/csv")
def csv_commande(bid: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    bon = achats.obtenir_bon(session, bid)
    return Response("﻿" + achats.csv_bon(bon), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="commande_{bon.numero}.csv"'})
