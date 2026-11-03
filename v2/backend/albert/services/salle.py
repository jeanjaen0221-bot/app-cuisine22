"""Plan de salle : plan de base, plan de chaque service, placement des fiches du jour.

Différence avec l'ancienne version : le plan d'un service place directement les **fiches**
du jour (espace « salle », midi avant 17 h, soir après). Le PDF de réservations du
service s'ajoute pour les petites tables ; une ligne du PDF qui correspond déjà à une
fiche (même heure, même nombre de couverts, nom proche) n'est pas comptée deux fois.
La table attribuée apparaît ensuite sur la fiche et sur son PDF salle.
"""
from __future__ import annotations

import copy
import hashlib
import io
import re
import uuid
from datetime import date, time
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..domain.erreurs import ErreurMetier, introuvable
from ..domain.normalisation import cle, lire_date
from ..models import Fiche, PlanSalle, ServiceSalle
from ..salle.geometrie import _assign_table_numbers, _capacity_for_table, _label_sort_key, renumeroter
from ..salle.placement import placer
from .contexte import Acteur, journaliser

SERVICES = ("midi", "soir")
LIBELLES_SERVICES = {"midi": "Midi", "soir": "Soir"}
TYPES_TABLES = ("fixed", "rect", "round", "sofa", "standing")
PLAN_VIDE: dict[str, Any] = {
    "room": {"width": 1600, "height": 1000, "grid": 50}, "tables": [], "walls": [], "columns": [], "fixtures": [],
    "no_go": [], "round_only_zones": [], "rect_only_zones": [], "zones": [],
    "max_dynamic_tables": {"rect": 10, "round": 5}, "fixed_chair_stock": 28,
}


def service_de_l_heure(h: time) -> str:
    return "midi" if h.hour < 17 else "soir"


def lire_service(valeur: Any) -> str:
    v = cle(valeur)
    v = {"lunch": "midi", "dejeuner": "midi", "dinner": "soir", "diner": "soir"}.get(v, v)
    if v not in SERVICES:
        raise ErreurMetier("valeur_non_permise", "Service inconnu.", champ="service", valeurs_permises=list(SERVICES))
    return v


# --------------------------------------------------------------- plan de base

def _valider_plan(donnees: Any) -> dict[str, Any]:
    if not isinstance(donnees, dict):
        raise ErreurMetier("valeur_non_permise", "Plan invalide.")
    tables = donnees.get("tables", [])
    if not isinstance(tables, list):
        raise ErreurMetier("valeur_non_permise", "Plan invalide : « tables » doit être une liste.")
    for i, t in enumerate(tables):
        if not isinstance(t, dict) or "id" not in t or "x" not in t or "y" not in t:
            raise ErreurMetier("valeur_non_permise", f"Table n° {i + 1} invalide (id, x et y obligatoires).")
        if t.get("kind") and t["kind"] not in TYPES_TABLES:
            raise ErreurMetier("valeur_non_permise", f"Type de table inconnu : {t['kind']}.", valeurs_permises=list(TYPES_TABLES))
    salle = donnees.get("room")
    if salle is not None:
        if not isinstance(salle, dict) or float(salle.get("width") or 0) < 100 or float(salle.get("height") or 0) < 100:
            raise ErreurMetier("valeur_non_permise", "Dimensions de la salle invalides (100 au minimum).")
    return donnees


def plan_de_base(session: Session) -> PlanSalle:
    plan = session.scalars(select(PlanSalle)).first()
    if plan is None:
        plan = PlanSalle(donnees=copy.deepcopy(PLAN_VIDE))
        session.add(plan)
        session.commit()
    return plan


def enregistrer_plan(session: Session, acteur: Acteur, donnees: Any) -> PlanSalle:
    acteur.exiger("fiches")
    plan = plan_de_base(session)
    plan.donnees = _valider_plan(donnees)
    flag_modified(plan, "donnees")
    journaliser(session, acteur, "salle.plan", "plan_salle", plan.id, f"Plan de base enregistré ({len(plan.donnees.get('tables') or [])} tables)")
    session.commit()
    return plan


def numeroter_plan(session: Session, acteur: Acteur, table_ids: Optional[list[str]] = None,
                   prefixe: str = "", debut: int = 1) -> PlanSalle:
    acteur.exiger("fiches")
    plan = plan_de_base(session)
    donnees = copy.deepcopy(plan.donnees or {})
    if table_ids:
        donnees = renumeroter(donnees, table_ids, prefixe, debut)
    else:
        donnees, _ = _assign_table_numbers(donnees, persist=True)
    plan.donnees = donnees
    flag_modified(plan, "donnees")
    journaliser(session, acteur, "salle.numeroter", "plan_salle", plan.id, "Tables numérotées")
    session.commit()
    return plan


def etiquettes(plan: dict[str, Any]) -> dict[str, str]:
    """Numéro de chaque table : celui enregistré (y compris une numérotation manuelle), sinon calculé."""
    _, calcule = _assign_table_numbers(copy.deepcopy(plan), persist=False)
    return {str(t.get("id")): str(t.get("label") or calcule.get(str(t.get("id")), ""))
            for t in (plan.get("tables") or [])}


# --------------------------------------------------------------- services

def obtenir_service(session: Session, jour: Any, service: Any, creer: bool = True) -> Optional[ServiceSalle]:
    d, s = lire_date(jour), lire_service(service)
    svc = session.scalars(select(ServiceSalle).where(ServiceSalle.date == d, ServiceSalle.service == s)).first()
    if svc is None and creer:
        svc = ServiceSalle(date=d, service=s, donnees=copy.deepcopy(plan_de_base(session).donnees or PLAN_VIDE),
                           affectations={"tables": {}}, reservations_importees=[])
        session.add(svc)
        session.commit()
    return svc


def service_par_id(session: Session, service_id: Any) -> ServiceSalle:
    try:
        svc = session.get(ServiceSalle, uuid.UUID(str(service_id)))
    except ValueError:
        svc = None
    if svc is None:
        raise introuvable("Service")
    return svc


def _fiches_du_service(session: Session, svc: ServiceSalle) -> list[Fiche]:
    fiches = session.scalars(select(Fiche).where(Fiche.date == svc.date, Fiche.statut != "annulee",
                                                 Fiche.espace == "salle").order_by(Fiche.heure))
    return [f for f in fiches if service_de_l_heure(f.heure) == svc.service]


def _mots(nom: str) -> set[str]:
    return {m for m in re.split(r"[^a-z0-9]+", cle(nom)) if len(m) >= 3}


def _doublon(ligne: dict[str, Any], fiches: list[Fiche]) -> Optional[Fiche]:
    for f in fiches:
        if f.couverts == int(ligne.get("pax") or 0) and f.heure.strftime("%H:%M") == str(ligne.get("heure"))[:5]:
            if _mots(f.client.nom) & _mots(ligne.get("nom", "")) or not _mots(ligne.get("nom", "")):
                return f
    return None


def reservations(session: Session, svc: ServiceSalle) -> list[dict[str, Any]]:
    """Fiches du service puis lignes du PDF importé (les doublons sont signalés, pas placés)."""
    fiches = _fiches_du_service(session, svc)
    sortie = [{"id": str(f.id), "source": "fiche", "fiche_id": str(f.id), "nom": f.client.nom, "pax": f.couverts,
               "heure": f.heure.strftime("%H:%M"), "statut": f.statut, "doublon_de": None} for f in fiches]
    for ligne in svc.reservations_importees or []:
        double = _doublon(ligne, fiches)
        sortie.append({"id": ligne["id"], "source": "import", "fiche_id": None, "nom": ligne["nom"],
                       "pax": int(ligne["pax"]), "heure": ligne["heure"], "statut": None,
                       "doublon_de": str(double.id) if double else None})
    sortie.sort(key=lambda r: (r["heure"], cle(r["nom"])))
    return sortie


def _a_placer(liste: list[dict[str, Any]]) -> list[SimpleNamespace]:
    sortie = []
    for r in liste:
        if r["doublon_de"]:
            continue
        hh, mm = (int(x) for x in r["heure"].split(":"))
        sortie.append(SimpleNamespace(id=r["id"], client_name=r["nom"], pax=int(r["pax"]), arrival_time=time(hh, mm)))
    return sortie


def service_dict(session: Session, svc: ServiceSalle) -> dict[str, Any]:
    liste = reservations(session, svc)
    labels = etiquettes(svc.donnees or {})
    par_res: dict[str, list[str]] = {}
    pax_par_res: dict[str, int] = {}
    connues = {r["id"] for r in liste}
    orphelines = []
    for table_id, a in ((svc.affectations or {}).get("tables") or {}).items():
        rid = str(a.get("res_id"))
        if rid in connues:
            par_res.setdefault(rid, []).append(labels.get(table_id, ""))
            pax_par_res[rid] = pax_par_res.get(rid, 0) + int(a.get("pax") or 0)
        else:
            orphelines.append({"table_id": table_id, "table": labels.get(table_id, ""), "nom": a.get("name"), "pax": a.get("pax")})
    for r in liste:
        r["tables"] = sorted([x for x in par_res.get(r["id"], []) if x], key=_label_sort_key)
        r["pax_place"] = pax_par_res.get(r["id"], 0)
        r["place"] = r["pax_place"] >= r["pax"] or bool(r["doublon_de"])
    a_placer = [r for r in liste if not r["doublon_de"]]
    alertes = list((svc.affectations or {}).get("alerts") or [])
    if orphelines:
        alertes.append(f"{len(orphelines)} table(s) attribuée(s) à une réservation qui n'existe plus "
                       "(fiche annulée ou déplacée) : relancer le placement ou libérer ces tables.")
    return {
        "id": str(svc.id), "date": svc.date.isoformat(), "service": svc.service,
        "service_libelle": LIBELLES_SERVICES[svc.service], "donnees": svc.donnees,
        "affectations": {"tables": (svc.affectations or {}).get("tables") or {}}, "etiquettes": labels,
        "reservations": liste, "orphelines": orphelines, "alertes": alertes,
        "totaux": {"reservations": len(a_placer), "couverts": sum(r["pax"] for r in a_placer),
                   "placees": sum(1 for r in a_placer if r["place"]),
                   "doublons": sum(1 for r in liste if r["doublon_de"]),
                   "importees": len(svc.reservations_importees or [])},
    }


def numeroter_service(session: Session, acteur: Acteur, svc: ServiceSalle, table_ids: Optional[list[str]] = None,
                      prefixe: str = "", debut: int = 1) -> ServiceSalle:
    acteur.exiger("fiches")
    donnees = copy.deepcopy(svc.donnees or {})
    if table_ids:
        donnees = renumeroter(donnees, table_ids, prefixe, debut)
    else:
        donnees, _ = _assign_table_numbers(donnees, persist=True)
    svc.donnees = donnees
    flag_modified(svc, "donnees")
    session.commit()
    return svc


def modifier_service(session: Session, acteur: Acteur, svc: ServiceSalle, donnees: Any) -> ServiceSalle:
    acteur.exiger("fiches")
    svc.donnees = _valider_plan(donnees)
    flag_modified(svc, "donnees")
    tables = {str(t.get("id")) for t in svc.donnees.get("tables") or []}
    affect = (svc.affectations or {}).get("tables") or {}
    svc.affectations = {**(svc.affectations or {}), "tables": {k: v for k, v in affect.items() if k in tables}}
    flag_modified(svc, "affectations")
    session.commit()
    return svc


def placement_automatique(session: Session, acteur: Acteur, svc: ServiceSalle) -> ServiceSalle:
    """Repart du plan sans tables ajoutées, puis place toutes les réservations du service."""
    acteur.exiger("fiches")
    a_placer = _a_placer(reservations(session, svc))
    if not a_placer:
        raise ErreurMetier("regle_metier", "Aucune réservation pour ce service : créer des fiches ou importer le PDF.")
    donnees = copy.deepcopy(svc.donnees or {})
    donnees["tables"] = [t for t in donnees.get("tables") or [] if not t.get("dynamic")]
    resultat = placer(donnees, a_placer)
    svc.donnees = donnees
    svc.affectations = resultat
    flag_modified(svc, "donnees")
    flag_modified(svc, "affectations")
    places = len({a["res_id"] for a in resultat["tables"].values()})
    journaliser(session, acteur, "salle.placement", "service_salle", svc.id,
                f"Placement automatique {svc.date:%d/%m/%Y} {svc.service} : {places}/{len(a_placer)} réservations placées")
    session.commit()
    return svc


def affecter(session: Session, acteur: Acteur, svc: ServiceSalle, table_id: str, reservation_id: Optional[str],
             pax: Optional[int] = None) -> ServiceSalle:
    """Placement à la main : attribuer une table à une réservation, ou la libérer (reservation_id vide)."""
    acteur.exiger("fiches")
    tables = {str(t.get("id")): t for t in (svc.donnees or {}).get("tables") or []}
    table = tables.get(str(table_id))
    if table is None:
        raise introuvable("Table")
    affect = dict((svc.affectations or {}).get("tables") or {})
    if not reservation_id:
        affect.pop(str(table_id), None)
    else:
        resa = next((r for r in reservations(session, svc) if r["id"] == str(reservation_id)), None)
        if resa is None:
            raise introuvable("Réservation")
        deja = sum(int(a.get("pax") or 0) for t, a in affect.items() if a.get("res_id") == resa["id"] and t != str(table_id))
        places = int(pax) if pax else max(1, min(_capacity_for_table(table) + (2 if table.get("kind") == "rect" else 0),
                                               resa["pax"] - deja))
        affect[str(table_id)] = {"res_id": resa["id"], "name": resa["nom"].upper(), "pax": places}
    svc.affectations = {**(svc.affectations or {}), "tables": affect}
    flag_modified(svc, "affectations")
    session.commit()
    return svc


def reinitialiser(session: Session, acteur: Acteur, svc: ServiceSalle, depuis_le_plan: bool = False) -> ServiceSalle:
    acteur.exiger("fiches")
    if depuis_le_plan:
        svc.donnees = copy.deepcopy(plan_de_base(session).donnees or PLAN_VIDE)
    else:
        svc.donnees = {**(svc.donnees or {}),
                       "tables": [t for t in (svc.donnees or {}).get("tables") or [] if not t.get("dynamic")]}
    svc.affectations = {"tables": {}}
    flag_modified(svc, "donnees")
    flag_modified(svc, "affectations")
    session.commit()
    return svc


def supprimer_service(session: Session, acteur: Acteur, svc: ServiceSalle) -> None:
    acteur.exiger("fiches")
    journaliser(session, acteur, "salle.supprimer", "service_salle", svc.id, f"Plan du {svc.date:%d/%m/%Y} {svc.service} supprimé")
    session.delete(svc)
    session.commit()


# --------------------------------------------------------------- import du PDF de réservations

def lire_pdf_reservations(contenu: bytes, jour: date) -> list[dict[str, Any]]:
    """Lit le tableau du PDF de réservations (heure, couverts, nom). Repris de l'ancienne version."""
    import pdfplumber

    re_heure = re.compile(r"^\d{1,2}:\d{2}$")
    re_pax = re.compile(r"^\d{1,2}$")
    sortie: list[dict[str, Any]] = []
    try:
        with pdfplumber.open(io.BytesIO(contenu)) as pdf:
            for page in pdf.pages:
                for tableau in page.extract_tables() or []:
                    for ligne in tableau or []:
                        if not ligne or len(ligne) < 3:
                            continue
                        cellules = [str(c).strip() if c else "" for c in ligne]
                        i_heure = i_pax = i_nom = None
                        for i, c in enumerate(cellules[:7]):
                            if c and re_heure.match(c):
                                i_heure = i
                            elif c and re_pax.match(c) and i_heure is not None:
                                i_pax = i
                            elif (c and len(c) >= 2 and any(x.isupper() for x in c) and i_heure is not None
                                  and i_pax is not None and not c.startswith("Commentaire")):
                                i_nom = i
                                break
                        if i_heure is None or i_pax is None or i_nom is None:
                            continue
                        pax = int(cellules[i_pax])
                        nom = cellules[i_nom].split("\n")[0].split("Téléphone")[0].strip()
                        if not (1 <= pax <= 30 and len(nom) >= 2):
                            continue
                        if nom.lower() in ("commentaire", "confirmé", "web", "google", "heure", "pax", "client"):
                            continue
                        hh, mm = cellules[i_heure].split(":")
                        heure = f"{int(hh):02d}:{int(mm):02d}"
                        empreinte = hashlib.md5(f"{jour}_{heure}_{pax}_{nom}".encode()).hexdigest()
                        sortie.append({"id": str(uuid.UUID(empreinte)), "heure": heure, "pax": pax, "nom": nom})
    except Exception as exc:  # PDF illisible
        raise ErreurMetier("valeur_non_permise", f"PDF illisible : {str(exc)[:120]}")
    if not sortie:
        raise ErreurMetier("valeur_non_permise", "Aucune réservation trouvée dans le PDF (format inattendu).")
    return sortie


def importer_pdf(session: Session, acteur: Acteur, svc: ServiceSalle, contenu: bytes) -> ServiceSalle:
    acteur.exiger("fiches")
    lignes = [l for l in lire_pdf_reservations(contenu, svc.date) if service_de_l_heure(time(*map(int, l["heure"].split(":")))) == svc.service]
    if not lignes:
        raise ErreurMetier("regle_metier", f"Le PDF ne contient aucune réservation pour le service du {svc.service}.")
    svc.reservations_importees = lignes
    flag_modified(svc, "reservations_importees")
    journaliser(session, acteur, "salle.import", "service_salle", svc.id,
                f"PDF importé pour le {svc.date:%d/%m/%Y} {svc.service} : {len(lignes)} réservations")
    session.commit()
    return svc


def retirer_import(session: Session, acteur: Acteur, svc: ServiceSalle) -> ServiceSalle:
    acteur.exiger("fiches")
    ids = {l["id"] for l in svc.reservations_importees or []}
    svc.reservations_importees = []
    affect = (svc.affectations or {}).get("tables") or {}
    svc.affectations = {"tables": {k: v for k, v in affect.items() if v.get("res_id") not in ids}}
    flag_modified(svc, "reservations_importees")
    flag_modified(svc, "affectations")
    session.commit()
    return svc


# --------------------------------------------------------------- lien avec les fiches

def tables_de_la_fiche(session: Session, fiche: Fiche) -> list[str]:
    svc = session.scalars(select(ServiceSalle).where(ServiceSalle.date == fiche.date,
                                                     ServiceSalle.service == service_de_l_heure(fiche.heure))).first()
    if svc is None:
        return []
    labels = etiquettes(svc.donnees or {})
    trouvees = [labels.get(t, "") for t, a in ((svc.affectations or {}).get("tables") or {}).items()
                if a.get("res_id") == str(fiche.id)]
    return sorted([x for x in trouvees if x], key=_label_sort_key)
