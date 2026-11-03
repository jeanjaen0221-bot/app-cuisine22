"""Reprise des données de l'ancienne version (base ancienne simulée en SQLite)."""
import json

from sqlalchemy import create_engine, select, text

from albert.models import Boisson, BonCommande, Client, Fiche, Note, PlanSalle, Plainte, Produit, Utilisateur
from albert.reprise import Rapport, reprendre
from albert.services import comptes

ANCIEN_SCHEMA = """
CREATE TABLE "user" (id CHAR(32), email TEXT, password_hash TEXT, role TEXT, permissions TEXT);
CREATE TABLE menuitem (id CHAR(32), name TEXT, type TEXT, active BOOLEAN);
CREATE TABLE supplementpreset (id CHAR(32), name TEXT, default_quantity INT);
CREATE TABLE reservation (id CHAR(32), client_name TEXT, pax INT, service_date DATE, arrival_time TIME,
  drink_formula TEXT, menu_formula TEXT, notes TEXT, status TEXT, final_version BOOLEAN, on_invoice BOOLEAN,
  allergens TEXT, is_rooftop BOOLEAN, company TEXT, contact TEXT, payment_method TEXT, special_requests TEXT, occasion TEXT);
CREATE TABLE reservationitem (id CHAR(32), reservation_id CHAR(32), type TEXT, name TEXT, quantity INT, comment TEXT);
CREATE TABLE billinginfo (reservation_id CHAR(32), company_name TEXT, address_line1 TEXT, address_line2 TEXT,
  zip_code TEXT, city TEXT, country TEXT, vat_number TEXT, po_reference TEXT, email TEXT, phone TEXT, payment_terms TEXT);
CREATE TABLE incidentreport (id CHAR(32), date DATE, heure TIME, lieu TEXT, employes TEXT, client TEXT, recit_brut TEXT,
  contexte TEXT, description_incident TEXT, reaction_personnel TEXT, consequences TEXT, mesures_prises TEXT,
  observations TEXT, gravite TEXT);
CREATE TABLE note (id CHAR(32), name TEXT, content TEXT);
CREATE TABLE supplier (id CHAR(32), name TEXT, email TEXT, phone TEXT, notes TEXT, active BOOLEAN);
CREATE TABLE drink (id CHAR(32), name TEXT, category TEXT, unit TEXT, active BOOLEAN);
CREATE TABLE drinkstock (drink_id CHAR(32), min_qty INT, max_qty INT, pack_size INT, reorder_enabled BOOLEAN);
CREATE TABLE drinkvendor (drink_id CHAR(32), supplier_id CHAR(32), vendor_sku TEXT, price_cents INT, pack_size INT, preferred BOOLEAN);
CREATE TABLE purchaseorder (id CHAR(32), supplier_id CHAR(32), status TEXT, note TEXT, created_at DATETIME);
CREATE TABLE purchaseorderitem (id CHAR(32), order_id CHAR(32), drink_id CHAR(32), name TEXT, unit TEXT, quantity INT, price_cents INT);
CREATE TABLE floorplanbase (id CHAR(32), name TEXT, data TEXT);
"""


def ancienne_base(chemin):
    moteur = create_engine(f"sqlite:///{chemin}")
    with moteur.begin() as c:
        for instruction in ANCIEN_SCHEMA.strip().split(";"):
            if instruction.strip():
                c.execute(text(instruction))
        mdp = comptes.hacher("ancien-mot-de-passe")
        c.execute(text("INSERT INTO 'user' VALUES ('u1','patron@albert.be',:m,'admin',''),"
                       "('u2','compta@albert.be',:m,'member','billing')"), {"m": mdp})
        c.execute(text("INSERT INTO menuitem VALUES ('m1','Carpaccio de bœuf','entrée',1),('m2','Steak frites','plat',1)"))
        c.execute(text("INSERT INTO supplementpreset VALUES ('s1','Planche apéro',1)"))
        c.execute(text("INSERT INTO reservation VALUES "
                       "('r1','Volta',20,'2030-06-12','19:30:00','Avec alcool + Champagne','','**VIP**','confirmed',0,1,'lait,kiwi',0,'Volta SRL','Stan 0470','Facture',NULL,'Anniversaire'),"
                       "('r2','Martin',4,'2020-01-10','12:30:00','sans alcool','3 Services',NULL,'printed',1,0,'',1,NULL,NULL,NULL,NULL,NULL),"
                       "('r3','Sans heure',4,'2030-01-10',NULL,'','',NULL,'draft',0,0,'',0,NULL,NULL,NULL,NULL,NULL)"))
        c.execute(text("INSERT INTO reservationitem VALUES ('i1','r1','entrée','carpaccio de boeuf',20,NULL),"
                       "('i2','r1','plat','Steak frites',20,'saignant'),('i3','r1','supplément','Planche apéro',20,NULL)"))
        c.execute(text("INSERT INTO billinginfo VALUES ('r1','Volta SRL','Rue Haute 12','bte 3','1000','Bruxelles','Belgique',"
                       "'BE0123456749','PO-77','events@volta.be','02 000','Paiement à 30 jours')"))
        c.execute(text("INSERT INTO incidentreport VALUES ('p1','2025-03-03','21:00:00','Terrasse','Paul','Dupont',"
                       "'Plat froid',NULL,NULL,NULL,NULL,NULL,NULL,'Moyen')"))
        c.execute(text("INSERT INTO note VALUES ('n1','Julie','Livraison lundi')"))
        c.execute(text("INSERT INTO supplier VALUES ('f1','Brasserie','b@b.be',NULL,NULL,1)"))
        c.execute(text("INSERT INTO drink VALUES ('d1','Orval','bière','bouteille',1)"))
        c.execute(text("INSERT INTO drinkstock VALUES ('d1',24,48,24,1)"))
        c.execute(text("INSERT INTO drinkvendor VALUES ('d1','f1','ORV',110,24,1)"))
        c.execute(text("INSERT INTO purchaseorder VALUES ('o1','f1','sent',NULL,'2025-04-01 10:00:00')"))
        c.execute(text("INSERT INTO purchaseorderitem VALUES ('oi1','o1','d1','Orval','bouteille',48,110)"))
        plan = {"room": {"width": 1200, "height": 800}, "tables": [{"id": "t1", "kind": "fixed", "x": 10, "y": 10, "w": 80, "h": 80}]}
        c.execute(text("INSERT INTO floorplanbase VALUES ('b1','base',:d)"), {"d": json.dumps(plan)})
    return moteur


def test_reprise_complete_et_relancable(session, tmp_path):
    source = ancienne_base(tmp_path / "ancienne.db")
    rapport = Rapport()
    reprendre(source, session, rapport)
    session.commit()

    patron = session.scalars(select(Utilisateur).where(Utilisateur.email == "patron@albert.be")).one()
    assert patron.role == "admin" and comptes.verifier("ancien-mot-de-passe", patron.mot_de_passe)
    assert session.scalars(select(Utilisateur).where(Utilisateur.email == "compta@albert.be")).one().role == "compta"

    volta = session.scalars(select(Client).where(Client.nom == "Volta SRL")).one()
    assert (volta.type, volta.tva, volta.code_postal, volta.reference_po) == ("entreprise", "BE0123456749", "1000", "PO-77")
    fiche = session.scalars(select(Fiche).where(Fiche.client_id == volta.id)).one()
    assert fiche.formule_boissons.nom == "avec alcool + champ" and fiche.allergenes == ["lait"]
    assert "kiwi" in fiche.notes_cuisine and "Anniversaire" in fiche.notes_salle
    assert [(l.type, l.libelle, l.produit_id is not None) for l in fiche.lignes] == [
        ("entree", "carpaccio de boeuf", True), ("plat", "Steak frites", True), ("supplement", "Planche apéro", True)]
    passee = session.scalars(select(Fiche).where(Fiche.espace == "Rooftop")).one()
    assert passee.statut == "realisee" and passee.formule_repas.nom == "3 services"
    assert any("Sans heure" in r for r in rapport.remarques)
    assert session.scalars(select(Produit).where(Produit.nom == "Steak frites")).one().prix_centimes is None
    assert session.scalars(select(Plainte)).one().gravite == "moyen"
    assert session.scalars(select(Note)).one().auteur == "Julie"
    orval = session.scalars(select(Boisson)).one()
    assert (orval.stock_max, orval.colisage) == (48, 24)
    bon = session.scalars(select(BonCommande)).one()
    assert bon.statut == "envoye" and bon.lignes[0].prix_achat_centimes == 110
    assert session.scalars(select(PlanSalle)).one().donnees["room"]["width"] == 1200

    # Relancer ne crée rien de plus.
    rapport2 = Rapport()
    reprendre(source, session, rapport2)
    session.commit()
    assert len(session.scalars(select(Fiche)).all()) == 2 and len(session.scalars(select(BonCommande)).all()) == 1
    assert "fiches" not in rapport2.compteurs
