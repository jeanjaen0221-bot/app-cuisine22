"""Reprise des données de l'ancienne version (app/) dans la v2.

Usage (la base v2 doit être migrée : `alembic upgrade head`) :

    python -m albert.reprise --source postgresql://…/ancienne_base            # essai, rien n'est écrit
    python -m albert.reprise --source postgresql://…/ancienne_base --ecrire   # reprise réelle

Relançable sans risque : chaque élément repris porte une clé (« reprise:<id> ») ou est
reconnu par son nom, et n'est jamais créé deux fois. L'ancienne base n'est que lue.

Ce qui est repris : comptes (mêmes mots de passe), plats → menu Prix (prix à compléter),
suppléments → menu Prix, clients (depuis la facturation et les réservations), réservations →
fiches (lignes, allergènes, formules, notes), plaintes, notes, boissons, fournisseurs, prix
d'achat, bons de commande, plan de salle de base. Les feuilles de facturation ne deviennent
pas des devis (elles n'avaient pas de montants).
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time
from typing import Any, Iterable, Optional

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .db import FabriqueSession
from .domain.erreurs import ErreurMetier
from .domain.normalisation import choisir, cle, cle_nom_client, lire_allergenes, lire_tva
from .models import (
    Boisson,
    BoissonFournisseur,
    BonCommande,
    BonCommandeLigne,
    Client,
    Fiche,
    FicheLigne,
    Fournisseur,
    Note,
    PlanSalle,
    Plainte,
    Produit,
    Utilisateur,
)
from .services import catalogue, fiches
from .services.contexte import SYSTEME, journaliser, prochain_numero
from .services.initialisation import initialiser_catalogue

TYPES = {"entree": "entree", "entrees": "entree", "plat": "plat", "plats": "plat", "dessert": "dessert",
         "desserts": "dessert", "supplement": "supplement", "supplements": "supplement"}


class Rapport:
    def __init__(self) -> None:
        self.compteurs: dict[str, int] = {}
        self.remarques: list[str] = []

    def compter(self, quoi: str, n: int = 1) -> None:
        self.compteurs[quoi] = self.compteurs.get(quoi, 0) + n

    def noter(self, remarque: str) -> None:
        if len(self.remarques) < 500:
            self.remarques.append(remarque)

    def texte(self) -> str:
        lignes = ["Reprise de l'ancienne version :"] + [f"  {k} : {v}" for k, v in sorted(self.compteurs.items())]
        if self.remarques:
            lignes += ["", f"À vérifier ({len(self.remarques)}) :"] + [f"  - {r}" for r in self.remarques]
        return "\n".join(lignes)


def _lignes(source: Engine, table: str) -> list[dict[str, Any]]:
    if not inspect(source).has_table(table):
        return []
    with source.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(f'SELECT * FROM "{table}"'))]


def _uuid(v: Any) -> str:
    return str(v).replace("-", "") if v is not None else ""


def _date(v: Any) -> Optional[date]:
    if v is None or isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _heure(v: Any) -> Optional[time]:
    if v is None or isinstance(v, time):
        return v
    try:
        return time.fromisoformat(str(v)[:8])
    except ValueError:
        return None


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else (v or {})


# --------------------------------------------------------------- reprise

def reprendre(source: Engine, session: Session, rapport: Rapport) -> None:
    initialiser_catalogue(session)
    _comptes(source, session, rapport)
    _produits(source, session, rapport)
    _fiches(source, session, rapport)
    _plaintes_notes(source, session, rapport)
    _achats(source, session, rapport)
    _plan(source, session, rapport)
    journaliser(session, SYSTEME, "reprise", "reprise", None,
                "Reprise de l'ancienne version : " + ", ".join(f"{k} {v}" for k, v in sorted(rapport.compteurs.items())))


def _comptes(source: Engine, session: Session, rapport: Rapport) -> None:
    existants = set(session.scalars(select(Utilisateur.email)))
    for u in _lignes(source, "user"):
        email = (u.get("email") or "").strip().lower()
        if not email or email in existants:
            continue
        droits = {d for d in (u.get("permissions") or "").split(",") if d}
        role = "admin" if (u.get("role") or "admin") == "admin" else (
            "equipe" if droits & {"reservations", "floorplan", "menu", "orders", "incidents"} else
            "compta" if "billing" in droits else "equipe")
        session.add(Utilisateur(email=email, mot_de_passe=u["password_hash"], role=role,
                                droits=["prix"] if role == "admin" or "menu" in droits else []))
        existants.add(email)
        rapport.compter("comptes")


def _produit(session: Session, categorie: str, nom: str, unite: str, actif: bool = True) -> Produit:
    for p in session.scalars(select(Produit).where(Produit.categorie == categorie)):
        if cle(p.nom) == cle(nom):
            return p
    p = Produit(categorie=categorie, nom=nom.strip()[:200], unite=unite, prix_centimes=None, actif=actif)
    session.add(p)
    session.flush()
    return p


def _produits(source: Engine, session: Session, rapport: Rapport) -> None:
    avant = len(list(session.scalars(select(Produit.id))))
    for m in _lignes(source, "menuitem"):
        t = TYPES.get(cle(m.get("type")))
        if t in ("entree", "plat", "dessert") and (m.get("name") or "").strip():
            _produit(session, t, m["name"], "piece", bool(m.get("active", True)))
    for s in _lignes(source, "supplementpreset"):
        if (s.get("name") or "").strip():
            _produit(session, "supplement", s["name"], "piece")
    rapport.compter("produits du menu Prix (prix à compléter)", len(list(session.scalars(select(Produit.id)))) - avant)


def _client(session: Session, nom: str, type_: str = "particulier", **extra: Any) -> Client:
    nom = (nom or "Client").strip()[:200]
    trouve = session.scalars(select(Client).where(Client.nom_cle == cle_nom_client(nom))).first()
    if trouve:
        for k, v in extra.items():
            if v and not getattr(trouve, k):
                setattr(trouve, k, v)
        return trouve
    c = Client(type=type_, nom=nom, nom_cle=cle_nom_client(nom), **{k: v for k, v in extra.items() if v})
    session.add(c)
    session.flush()
    return c


def _fiches(source: Engine, session: Session, rapport: Rapport) -> None:
    facturation = {_uuid(b["reservation_id"]): b for b in _lignes(source, "billinginfo")}
    lignes_par_resa: dict[str, list[dict]] = {}
    for it in _lignes(source, "reservationitem"):
        lignes_par_resa.setdefault(_uuid(it.get("reservation_id")), []).append(it)
    formules_repas = [(f.nom, f) for f in catalogue.lister_formules_repas(session)]
    formules_boissons = [(f.nom, f) for f in catalogue.lister_formules_boissons(session)]
    deja = set(session.scalars(select(Fiche.cle_idempotence).where(Fiche.cle_idempotence.like("reprise:%"))))
    aujourd_hui = fiches.aujourd_hui()

    for r in _lignes(source, "reservation"):
        rid = _uuid(r["id"])
        cle_reprise = f"reprise:{rid}"
        if cle_reprise in deja:
            continue
        jour, heure = _date(r.get("service_date")), _heure(r.get("arrival_time"))
        if jour is None or heure is None:
            rapport.noter(f"Réservation « {r.get('client_name')} » sans date ou heure lisible : non reprise.")
            continue
        b = facturation.get(rid)
        if b:
            try:
                tva = lire_tva(b.get("vat_number"))
            except ErreurMetier:
                tva = None
                rapport.noter(f"N° TVA illisible pour {b.get('company_name')} : {b.get('vat_number')!r}.")
            client = _client(session, b.get("company_name") or r.get("client_name"), "entreprise",
                             rue=b.get("address_line1"), ville=b.get("city"), code_postal=b.get("zip_code"),
                             pays=b.get("country") or "Belgique", tva=tva, reference_po=b.get("po_reference"),
                             email=(b.get("email") or "").lower() or None, telephone=b.get("phone"),
                             conditions_paiement=b.get("payment_terms"))
            if b.get("address_line2"):
                client.notes = ((client.notes or "") + f"\nAdresse (suite) : {b['address_line2']}").strip()
        else:
            client = _client(session, r.get("company") or r.get("client_name"),
                             "entreprise" if r.get("company") else "particulier")

        notes_cuisine: list[str] = []
        try:
            allergenes = lire_allergenes(r.get("allergens") or "")
        except ErreurMetier:
            allergenes = []
            for brut in (r.get("allergens") or "").split(","):
                try:
                    allergenes += [a for a in lire_allergenes([brut]) if a not in allergenes]
                except ErreurMetier:
                    if brut.strip():
                        notes_cuisine.append(f"Allergie : {brut.strip()}")
        formule_repas = None
        if (r.get("menu_formula") or "").strip():
            try:
                formule_repas = choisir(r["menu_formula"], formules_repas, "formule_repas")
            except ErreurMetier:
                rapport.noter(f"Formule repas inconnue « {r['menu_formula']} » ({client.nom}, {jour}).")
        formule_boissons = None
        if (r.get("drink_formula") or "").strip():
            try:
                formule_boissons = choisir(r["drink_formula"], formules_boissons, "formule_boissons")
            except ErreurMetier:
                notes_cuisine.append(f"Boissons : {r['drink_formula']}")
        statut = {"draft": "brouillon", "confirmed": "confirmee", "printed": "confirmee"}.get(r.get("status") or "", "brouillon")
        if r.get("final_version"):
            statut = "finale"
        if jour < aujourd_hui and statut in ("confirmee", "finale"):
            statut = "realisee"
        complements = [f"{t} : {r[k]}" for k, t in (("company", "Société"), ("contact", "Contact"),
                                                   ("occasion", "Occasion"), ("special_requests", "Demandes"),
                                                   ("payment_method", "Paiement")) if r.get(k)]
        notes_salle = "\n".join(filter(None, [r.get("notes") or "", *complements])) or None
        fiche = Fiche(client_id=client.id, date=jour, heure=heure, couverts=max(1, min(int(r.get("pax") or 1), 500)),
                      espace="Rooftop" if r.get("is_rooftop") else "salle", formule_repas=formule_repas,
                      formule_boissons=formule_boissons, allergenes=allergenes, notes_salle=notes_salle,
                      notes_cuisine="\n".join(notes_cuisine) or None, statut=statut, cle_idempotence=cle_reprise)
        for i, it in enumerate(sorted(lignes_par_resa.get(rid, []), key=lambda x: str(x.get("type")))):
            t = TYPES.get(cle(it.get("type")))
            if t is None or not (it.get("name") or "").strip() or int(it.get("quantity") or 0) <= 0:
                continue
            categories = (t,) if t != "supplement" else ("supplement", "coupe")
            produit = next((p for p in session.scalars(select(Produit).where(Produit.categorie.in_(categories)))
                            if cle(p.nom) == cle(it["name"])), None)
            fiche.lignes.append(FicheLigne(type=t, libelle=it["name"].strip()[:200], quantite=int(it["quantity"]),
                                           commentaire=it.get("comment"), produit_id=produit.id if produit else None, ordre=i))
        session.add(fiche)
        session.flush()
        rapport.compter("fiches")
    rapport.compter("clients (au total)", len(list(session.scalars(select(Client.id)))))


def _plaintes_notes(source: Engine, session: Session, rapport: Rapport) -> None:
    deja = {(p.date, cle(p.recit_brut or p.description or "")) for p in session.scalars(select(Plainte))}
    for i in _lignes(source, "incidentreport"):
        jour = _date(i.get("date"))
        recit = i.get("recit_brut") or i.get("description_incident") or "Non précisé"
        if jour is None or (jour, cle(recit)) in deja:
            continue
        gravite = {"faible": "faible", "moyen": "moyen", "eleve": "eleve"}.get(cle(i.get("gravite")), "faible")
        session.add(Plainte(date=jour, heure=_heure(i.get("heure")), lieu=i.get("lieu"), employes=i.get("employes"),
                            client_nom=i.get("client"), recit_brut=recit, contexte=i.get("contexte"),
                            description=i.get("description_incident"), reaction_personnel=i.get("reaction_personnel"),
                            consequences=i.get("consequences"), mesures_prises=i.get("mesures_prises"),
                            observations=i.get("observations"), gravite=gravite, statut="traitee"))
        rapport.compter("plaintes")
    notes = {cle(n.contenu) for n in session.scalars(select(Note))}
    for n in _lignes(source, "note"):
        if (n.get("content") or "").strip() and cle(n["content"]) not in notes:
            session.add(Note(auteur=n.get("name") or "ancienne version", contenu=n["content"].strip()))
            rapport.compter("notes")


def _achats(source: Engine, session: Session, rapport: Rapport) -> None:
    fournisseurs: dict[str, Fournisseur] = {}
    par_nom = {cle(f.nom): f for f in session.scalars(select(Fournisseur))}
    for f in _lignes(source, "supplier"):
        nouveau = par_nom.get(cle(f.get("name")))
        if nouveau is None:
            nouveau = Fournisseur(nom=(f.get("name") or "Fournisseur")[:200], email=f.get("email"),
                                  telephone=f.get("phone"), notes=f.get("notes"), actif=bool(f.get("active", True)))
            session.add(nouveau)
            session.flush()
            par_nom[cle(nouveau.nom)] = nouveau
            rapport.compter("fournisseurs")
        fournisseurs[_uuid(f["id"])] = nouveau
    stocks = {_uuid(s["drink_id"]): s for s in _lignes(source, "drinkstock")}
    boissons: dict[str, Boisson] = {}
    existantes = {cle(b.nom): b for b in session.scalars(select(Boisson))}
    for d in _lignes(source, "drink"):
        b = existantes.get(cle(d.get("name")))
        if b is None:
            s = stocks.get(_uuid(d["id"]), {})
            b = Boisson(nom=d["name"][:200], categorie=d.get("category"), unite=d.get("unit"),
                        actif=bool(d.get("active", True)), stock_min=int(s.get("min_qty") or 0),
                        stock_max=int(s.get("max_qty") or 0), colisage=s.get("pack_size"),
                        reassort=bool(s.get("reorder_enabled", True)))
            session.add(b)
            session.flush()
            existantes[cle(b.nom)] = b
            rapport.compter("boissons")
        boissons[_uuid(d["id"])] = b
    for o in _lignes(source, "drinkvendor"):
        b, f = boissons.get(_uuid(o["drink_id"])), fournisseurs.get(_uuid(o["supplier_id"]))
        if b and f and session.get(BoissonFournisseur, (b.id, f.id)) is None:
            session.add(BoissonFournisseur(boisson_id=b.id, fournisseur_id=f.id, reference=o.get("vendor_sku"),
                                           prix_achat_centimes=o.get("price_cents"), colisage=o.get("pack_size"),
                                           prefere=bool(o.get("preferred"))))
    lignes_par_bon: dict[str, list[dict]] = {}
    for it in _lignes(source, "purchaseorderitem"):
        lignes_par_bon.setdefault(_uuid(it["order_id"]), []).append(it)
    deja = set(session.scalars(select(BonCommande.cle_idempotence).where(BonCommande.cle_idempotence.like("reprise:%"))))
    for po in _lignes(source, "purchaseorder"):
        cle_reprise = f"reprise:{_uuid(po['id'])}"
        if cle_reprise in deja:
            continue
        cree = po.get("created_at") if isinstance(po.get("created_at"), datetime) else datetime.now()
        bon = BonCommande(numero=prochain_numero(session, "C", cree.year), cle_idempotence=cle_reprise,
                          fournisseur_id=fournisseurs[_uuid(po["supplier_id"])].id if _uuid(po.get("supplier_id")) in fournisseurs else None,
                          statut={"draft": "brouillon", "sent": "envoye", "received": "recu", "cancelled": "annule"}.get(po.get("status") or "", "brouillon"),
                          note=po.get("note"))
        for i, it in enumerate(lignes_par_bon.get(_uuid(po["id"]), [])):
            b = boissons.get(_uuid(it.get("drink_id")))
            bon.lignes.append(BonCommandeLigne(ordre=i, boisson_id=b.id if b else None, libelle=(it.get("name") or "?")[:200],
                                               unite=it.get("unit"), quantite=max(1, int(it.get("quantity") or 1)),
                                               prix_achat_centimes=it.get("price_cents")))
        session.add(bon)
        session.flush()
        rapport.compter("bons de commande")


def _plan(source: Engine, session: Session, rapport: Rapport) -> None:
    anciens = _lignes(source, "floorplanbase")
    if not anciens:
        return
    plan = session.scalars(select(PlanSalle)).first()
    donnees = _json(anciens[0].get("data"))
    if plan is None or not (plan.donnees or {}).get("tables"):
        if plan is None:
            plan = PlanSalle(donnees=donnees)
            session.add(plan)
        else:
            plan.donnees = donnees
        rapport.compter("plan de salle")


def principal(argv: Optional[Iterable[str]] = None) -> int:
    parseur = argparse.ArgumentParser(description="Reprise des données de l'ancienne version.")
    parseur.add_argument("--source", required=True, help="Adresse de l'ancienne base (postgresql://… ou sqlite:///…)")
    parseur.add_argument("--ecrire", action="store_true", help="Écrire pour de bon (sans cette option : simple essai)")
    args = parseur.parse_args(list(argv) if argv is not None else None)
    url = args.source.replace("postgres://", "postgresql://", 1)
    source = create_engine(url)
    rapport = Rapport()
    with FabriqueSession() as session:
        reprendre(source, session, rapport)
        if args.ecrire:
            session.commit()
        else:
            session.rollback()
    print(rapport.texte())
    print("\n" + ("Données écrites." if args.ecrire else "Essai seulement : rien n'a été écrit (ajouter --ecrire)."))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(principal())

