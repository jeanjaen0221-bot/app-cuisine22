"""Clients, fiches, menus Prix et Formules."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import lire_date
from ..models import FormuleBoissons, FormuleRepas
from ..pdf.documents import nom_fichier, pdf_fiches
from ..services import bons as bons_service, catalogue, clients, devis as devis_service, fiches
from ..services.contexte import Acteur, journaliser
from .deps import acteur_connecte, corps, reponse_pdf, session_db

router = APIRouter(prefix="/api")


# --------------------------------------------------------------- clients

@router.get("/clients")
def lister_clients(q: Optional[str] = None, archives: bool = False, limite: int = 50, decalage: int = 0,
                   acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return [clients.client_dict(c) for c in clients.rechercher(session, q, inclure_archives=archives,
                                                                limite=min(limite, 200), decalage=decalage)]


@router.post("/clients", status_code=201)
def creer_client(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                 session: Session = Depends(session_db)):
    return clients.client_dict(clients.creer(session, acteur, corps(donnees)))


@router.get("/clients/{client_id}")
def lire_client(client_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    c = clients.obtenir(session, client_id)
    return {
        **clients.client_dict(c),
        "fiches": [fiches.fiche_dict(session, f, complet=False)
                   for f in fiches.lister(session, client_id=str(c.id), periode="toutes", limite=200)],
        "devis": [devis_service.devis_dict(session, d) for d in devis_service.lister(session, client_id=str(c.id))],
        "bons": [bons_service.bon_dict(session, b) for b in bons_service.lister(session, client_id=str(c.id))],
    }


@router.patch("/clients/{client_id}")
def modifier_client(client_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                    session: Session = Depends(session_db)):
    donnees = corps(donnees)
    version = donnees.pop("version", None)
    return clients.client_dict(clients.modifier(session, acteur, uuid.UUID(client_id), donnees, version))


# --------------------------------------------------------------- fiches

def _fiche_reponse(session: Session, fiche: Any, alertes: Optional[list[str]] = None) -> dict[str, Any]:
    d = fiches.fiche_dict(session, fiche)
    for a in alertes or []:
        if a not in d["alertes"]:
            d["alertes"].append(a)
    return d


@router.get("/fiches")
def lister_fiches(q: Optional[str] = None, client_id: Optional[str] = None, jour: Optional[str] = None,
                  du: Optional[str] = None, au: Optional[str] = None, statut: Optional[str] = None,
                  espace: Optional[str] = None, periode: str = "a_venir", limite: int = 100, decalage: int = 0,
                  acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    liste = fiches.lister(session, q, client_id, jour, du, au, statut, espace, periode, min(limite, 500), decalage)
    return [fiches.fiche_dict(session, f, complet=False) for f in liste]


@router.post("/fiches", status_code=201)
def creer_fiche(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                session: Session = Depends(session_db)):
    fiche, alertes = fiches.creer(session, acteur, corps(donnees))
    return _fiche_reponse(session, fiche, alertes)


@router.get("/fiches/{fiche_id}")
def lire_fiche(fiche_id: str, acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    return _fiche_reponse(session, fiches.obtenir(session, fiche_id))


@router.patch("/fiches/{fiche_id}")
def modifier_fiche(fiche_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                   session: Session = Depends(session_db)):
    donnees = corps(donnees)
    version = donnees.pop("version", None)
    fiche, alertes = fiches.modifier(session, acteur, fiche_id, donnees, version)
    return _fiche_reponse(session, fiche, alertes)


@router.post("/fiches/{fiche_id}/statut")
def statut_fiche(fiche_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                 session: Session = Depends(session_db)):
    donnees = corps(donnees)
    fiche = fiches.changer_statut(session, acteur, fiche_id, donnees.get("statut"), donnees.get("version"),
                                  donnees.get("motif"))
    return _fiche_reponse(session, fiches.obtenir(session, fiche.id))


@router.post("/fiches/{fiche_id}/dupliquer", status_code=201)
def dupliquer_fiche(fiche_id: str, donnees: dict = Body(default={}), acteur: Acteur = Depends(acteur_connecte),
                    session: Session = Depends(session_db)):
    return _fiche_reponse(session, fiches.dupliquer(session, acteur, fiche_id, (donnees or {}).get("date")))


def _pour_pdf(session: Session, fiche: Any) -> dict[str, Any]:
    d = fiches.fiche_dict(session, fiche)
    d["formule_sans_plats"] = bool(fiche.formule_repas and fiche.formule_repas.comportement == "sans_plats")
    return d


@router.get("/fiches/{fiche_id}/pdf")
def pdf_fiche(fiche_id: str, variante: str = "complete", acteur: Acteur = Depends(acteur_connecte),
              session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    if variante not in ("salle", "cuisine", "complete"):
        raise ErreurMetier("valeur_non_permise", "Variante inconnue.", valeurs_permises=["salle", "cuisine", "complete"])
    fiche = fiches.obtenir(session, fiche_id)
    contenu = pdf_fiches([_pour_pdf(session, fiche)], variante)
    fiches.marquer_imprimee(session, fiche)
    return reponse_pdf(contenu, nom_fichier("fiche", variante, fiche.date, fiche.client.nom))


@router.get("/jour/{jour}/pdf")
def pdf_jour(jour: str, variante: str = "complete", acteur: Acteur = Depends(acteur_connecte),
             session: Session = Depends(session_db)):
    acteur.exiger("fiches")
    d = lire_date(jour)
    liste = [f for f in fiches.lister(session, jour=d, limite=500) if f.statut != "annulee"]
    contenu = pdf_fiches([_pour_pdf(session, f) for f in liste], variante)
    for f in liste:
        fiches.marquer_imprimee(session, f)
    return reponse_pdf(contenu, nom_fichier("fiches", d))


# --------------------------------------------------------------- menu Prix

@router.get("/produits")
def lister_produits(categorie: Optional[str] = None, q: Optional[str] = None, manquants: bool = False,
                    acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("lecture")
    return [catalogue.produit_dict(p) for p in catalogue.lister_produits(session, categorie, q, manquants)]


@router.get("/produits/manquants")
def compter_manquants(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("lecture")
    return {"nombre": catalogue.compter_prix_manquants(session)}


@router.post("/produits", status_code=201)
def creer_produit(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                  session: Session = Depends(session_db)):
    return catalogue.produit_dict(catalogue.creer_produit(session, acteur, corps(donnees)))


@router.patch("/produits/{produit_id}")
def modifier_produit(produit_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                     session: Session = Depends(session_db)):
    return catalogue.produit_dict(catalogue.modifier_produit(session, acteur, uuid.UUID(produit_id), corps(donnees)))


# --------------------------------------------------------------- menu Formules

@router.get("/formules")
def lister_formules(acteur: Acteur = Depends(acteur_connecte), session: Session = Depends(session_db)):
    acteur.exiger("lecture")
    return {
        "repas": [{**catalogue.formule_repas_dict(f), "utilisee": catalogue.formule_utilisee(session, f)}
                  for f in catalogue.lister_formules_repas(session)],
        "boissons": [{**catalogue.formule_boissons_dict(f), "utilisee": catalogue.formule_utilisee(session, f)}
                     for f in catalogue.lister_formules_boissons(session)],
    }


@router.post("/formules/repas", status_code=201)
def creer_formule_repas(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                        session: Session = Depends(session_db)):
    return catalogue.formule_repas_dict(catalogue.enregistrer_formule_repas(session, acteur, corps(donnees)))


@router.patch("/formules/repas/{formule_id}")
def modifier_formule_repas(formule_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                           session: Session = Depends(session_db)):
    return catalogue.formule_repas_dict(
        catalogue.enregistrer_formule_repas(session, acteur, corps(donnees), uuid.UUID(formule_id)))


@router.post("/formules/boissons", status_code=201)
def creer_formule_boissons(donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                           session: Session = Depends(session_db)):
    return catalogue.formule_boissons_dict(catalogue.enregistrer_formule_boissons(session, acteur, corps(donnees)))


@router.patch("/formules/boissons/{formule_id}")
def modifier_formule_boissons(formule_id: str, donnees: dict = Body(...), acteur: Acteur = Depends(acteur_connecte),
                              session: Session = Depends(session_db)):
    return catalogue.formule_boissons_dict(
        catalogue.enregistrer_formule_boissons(session, acteur, corps(donnees), uuid.UUID(formule_id)))


@router.delete("/formules/{genre}/{formule_id}")
def supprimer_formule(genre: str, formule_id: str, acteur: Acteur = Depends(acteur_connecte),
                      session: Session = Depends(session_db)):
    """Seulement si aucune fiche ne l'utilise ; sinon la désactiver."""
    acteur.exiger("prix")
    modele = {"repas": FormuleRepas, "boissons": FormuleBoissons}.get(genre)
    if modele is None:
        raise introuvable("Formule")
    formule = session.get(modele, uuid.UUID(formule_id))
    if formule is None:
        raise introuvable("Formule")
    if catalogue.formule_utilisee(session, formule):
        raise ErreurMetier("regle_metier", "Cette formule est utilisée par des fiches : la désactiver plutôt.")
    journaliser(session, acteur, f"formule_{genre}.supprimer", f"formule_{genre}", formule.id, formule.nom)
    session.delete(formule)
    session.commit()
    return {"ok": True}


# --------------------------------------------------------------- Zenchef

@router.get("/zenchef")
def etat_zenchef(acteur: Acteur = Depends(acteur_connecte)):
    from ..services import zenchef

    acteur.exiger("fiches")
    return {"configure": zenchef.configure()}


@router.post("/zenchef/synchroniser")
def synchroniser_zenchef(donnees: dict = Body(default={}), acteur: Acteur = Depends(acteur_connecte),
                         session: Session = Depends(session_db)):
    from ..services import zenchef

    d = corps(donnees or {})
    return zenchef.synchroniser(session, acteur, d.get("du"), d.get("au"))
