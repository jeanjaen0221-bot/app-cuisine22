"""Devis, bons pour facturation et espace compta."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ..pdf.documents import nom_fichier
from ..services import bons as bons_service, devis as devis_service
from ..services.contexte import Acteur
from .deps import acteur_connecte, corps, reponse_pdf, session_db

router = APIRouter(prefix="/api")

STATUTS_VISIBLES_COMPTA = ("transmis", "envoye", "accepte", "refuse", "remplace", "facture")


def _lecture_document(acteur: Acteur, statut: str) -> None:
    """L'équipe voit tout ; la compta voit ce qui lui a été transmis."""
    if acteur.peut("fiches"):
        return
    if acteur.peut("compta") and statut in STATUTS_VISIBLES_COMPTA:
        return
    acteur.exiger("fiches")


def _devis(session: Session, d: Any, alertes: Optional[list[str]] = None) -> dict[str, Any]:
    sortie = devis_service.devis_dict(session, d)
    sortie["alertes"] = alertes or []
    return sortie


# --------------------------------------------------------------- devis

@router.get("/devis")
def lister_devis(statut: Optional[str] = None, client_id: Optional[str] = None, fiche_id: Optional[str] = None,
                 tous: bool = False, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return [devis_service.devis_dict(session, d)
            for d in devis_service.lister(session, statut, client_id, fiche_id, inclure_remplaces=tous)]


@router.post("/fiches/{fiche_id}/devis", status_code=201)
def preparer_devis(fiche_id: str, donnees: dict = Body(default={}), acteur: Acteur = Depends(acteur_connecte),
                   session: Session = Depends(session_db)):
    d, alertes = devis_service.preparer(session, acteur, fiche_id, corps(donnees or {}))
    return _devis(session, d, alertes)


@router.get("/devis/{devis_id}")
def lire_devis(devis_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    d = devis_service.obtenir(session, devis_id)
    _lecture_document(acteur, d.statut)
    return _devis(session, d)


@router.patch("/devis/{devis_id}")
def modifier_devis(devis_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                   session: Session = Depends(session_db)):
    return _devis(session, devis_service.modifier(session, acteur, devis_id, corps(donnees)))


@router.post("/devis/{devis_id}/{action}")
def action_devis(devis_id: str, action: str, donnees: dict = Body(default={}),
                 acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    donnees = corps(donnees or {})
    alertes: list[str] = []
    if action == "actualiser":
        d, alertes = devis_service.actualiser(session, acteur, devis_id, donnees)
    elif action == "valider":
        d = devis_service.valider(session, acteur, devis_id)
    elif action == "devalider":
        d = devis_service.devalider(session, acteur, devis_id)
    elif action == "transmettre":
        d = devis_service.transmettre(session, acteur, devis_id)
    elif action == "envoye":
        d = devis_service.marquer_envoye(session, acteur, devis_id)
    elif action == "accepte":
        d = devis_service.repondre(session, acteur, devis_id, True)
    elif action == "refuse":
        d = devis_service.repondre(session, acteur, devis_id, False)
    elif action == "nouvelle-version":
        d, alertes = devis_service.nouvelle_version(session, acteur, devis_id)
    elif action == "bon":
        b, alertes = bons_service.preparer(session, acteur, devis_id, donnees.get("couverts_reels"),
                                           donnees.get("extras"), donnees.get("remarques_compta"))
        return {**bons_service.bon_dict(session, b), "alertes": alertes}
    else:
        from ..domain.erreurs import ErreurMetier
        raise ErreurMetier("valeur_non_permise", f"Action inconnue : {action}.",
                           valeurs_permises=["actualiser", "valider", "devalider", "transmettre", "envoye",
                                             "accepte", "refuse", "nouvelle-version", "bon"])
    return _devis(session, devis_service.obtenir(session, d.id), alertes)


@router.get("/devis/{devis_id}/pdf")
def pdf_devis(devis_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    d = devis_service.obtenir(session, devis_id)
    _lecture_document(acteur, d.statut)
    return reponse_pdf(devis_service.generer_pdf(session, d),
                       nom_fichier("devis", d.numero, f"v{d.version}", d.client.nom))


# --------------------------------------------------------------- bons pour facturation

@router.get("/bons")
def lister_bons(statut: Optional[str] = None, client_id: Optional[str] = None,
                acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return [bons_service.bon_dict(session, b) for b in bons_service.lister(session, statut, client_id)]


@router.get("/bons/{bon_id}")
def lire_bon(bon_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    b = bons_service.obtenir(session, bon_id)
    _lecture_document(acteur, b.statut)
    return bons_service.bon_dict(session, b)


@router.patch("/bons/{bon_id}")
def modifier_bon(bon_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                 session: Session = Depends(session_db)):
    donnees = corps(donnees)
    version = donnees.pop("version", None)
    return bons_service.bon_dict(session, bons_service.modifier(session, acteur, bon_id, donnees, version))


@router.post("/bons/{bon_id}/{action}")
def action_bon(bon_id: str, action: str, donnees: dict = Body(default={}),
               acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    donnees = corps(donnees or {})
    if action == "valider":
        b = bons_service.valider(session, acteur, bon_id)
    elif action == "devalider":
        b = bons_service.devalider(session, acteur, bon_id)
    elif action == "transmettre":
        b = bons_service.transmettre(session, acteur, bon_id)
    elif action == "facture":
        b = bons_service.marquer_facture(session, acteur, bon_id, donnees.get("numero_facture"))
    else:
        from ..domain.erreurs import ErreurMetier
        raise ErreurMetier("valeur_non_permise", f"Action inconnue : {action}.",
                           valeurs_permises=["valider", "devalider", "transmettre", "facture"])
    return bons_service.bon_dict(session, bons_service.obtenir(session, b.id))


@router.get("/bons/{bon_id}/pdf")
def pdf_bon(bon_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    b = bons_service.obtenir(session, bon_id)
    _lecture_document(acteur, b.statut)
    return reponse_pdf(bons_service.generer_pdf(session, b), nom_fichier("bon", b.numero, b.client.nom))


# --------------------------------------------------------------- espace compta

@router.get("/compta")
def espace_compta(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("compta")
    return {
        "a_envoyer": [devis_service.devis_dict(session, d) for d in devis_service.lister(session, "transmis")],
        "attente_reponse": [devis_service.devis_dict(session, d) for d in devis_service.lister(session, "envoye")],
        "a_facturer": [bons_service.bon_dict(session, b) for b in bons_service.lister(session, "transmis")],
        "historique_devis": [devis_service.devis_dict(session, d)
                             for d in devis_service.lister(session, "accepte,refuse")][:100],
        "historique_bons": [bons_service.bon_dict(session, b) for b in bons_service.lister(session, "facture")][:100],
    }


# --------------------------------------------------------------- liens PDF temporaires (ChatGPT)

@router.get("/pdf/{jeton}")
def pdf_par_lien(jeton: str, session: Session = Depends(session_db)):
    from ..mcp.liens import lire_lien
    from ..pdf.documents import pdf_fiches
    from ..services import fiches
    from .routes_metier import _pour_pdf

    genre, identifiant = lire_lien(jeton)
    if genre.startswith("fiche_"):
        fiche = fiches.obtenir(session, identifiant)
        variante = genre.removeprefix("fiche_")
        return reponse_pdf(pdf_fiches([_pour_pdf(session, fiche)], variante),
                           nom_fichier("fiche", variante, fiche.date, fiche.client.nom))
    if genre == "devis":
        d = devis_service.obtenir(session, identifiant)
        return reponse_pdf(devis_service.generer_pdf(session, d), nom_fichier("devis", d.numero, f"v{d.version}"))
    b = bons_service.obtenir(session, identifiant)
    return reponse_pdf(bons_service.generer_pdf(session, b), nom_fichier("bon", b.numero))
