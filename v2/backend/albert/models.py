"""Tables de la base.

Montants : toujours en centimes entiers, TVA comprise. Un prix à None veut dire
« prix manquant » (à compléter dans le menu Prix), 0 veut dire « gratuit ».
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _cree() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=maintenant)


def _modifie() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=maintenant, onupdate=maintenant)


# ---------------------------------------------------------------- comptes

class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    nom: Mapped[str] = mapped_column(String(200), default="")
    mot_de_passe: Mapped[str] = mapped_column(String(300))
    # admin : tout ; equipe : clients, fiches, devis, bons ; compta : espace compta.
    role: Mapped[str] = mapped_column(String(20), default="equipe")
    # Droits en plus du rôle, ex. "prix" (menus Prix et Formules), "chatgpt".
    droits: Mapped[list[str]] = mapped_column(JSON, default=list)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    cree_le: Mapped[datetime] = _cree()
    derniere_connexion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Parametre(Base):
    __tablename__ = "parametre"

    cle: Mapped[str] = mapped_column(String(100), primary_key=True)
    valeur: Mapped[Any] = mapped_column(JSON)


class Compteur(Base):
    __tablename__ = "compteur"

    cle: Mapped[str] = mapped_column(String(50), primary_key=True)  # ex. "devis-2026"
    valeur: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------- catalogue

class Produit(Base):
    """Tout ce qui se vend (menu « Prix »)."""

    __tablename__ = "produit"

    id: Mapped[uuid.UUID] = _id()
    nom: Mapped[str] = mapped_column(String(200))
    # formule_repas, formule_boissons, coupe, entree, plat, dessert, supplement, privatisation
    categorie: Mapped[str] = mapped_column(String(30), index=True)
    # par_personne, piece, forfait, bouteille
    unite: Mapped[str] = mapped_column(String(20), default="piece")
    prix_centimes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allergenes: Mapped[list[str]] = mapped_column(JSON, default=list)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    cree_le: Mapped[datetime] = _cree()
    modifie_le: Mapped[datetime] = _modifie()

    __table_args__ = (UniqueConstraint("categorie", "nom", name="uq_produit_categorie_nom"),)


class FormuleRepas(Base):
    """Une formule repas proposée sur la fiche (menu « Formules »)."""

    __tablename__ = "formule_repas"

    id: Mapped[uuid.UUID] = _id()
    nom: Mapped[str] = mapped_column(String(100), unique=True)
    # services : plats facultatifs, la formule est déduite des plats s'il y en a ;
    # carte : chaque plat compté à son prix ; sans_plats : aucun plat (Brunch, Sharing).
    comportement: Mapped[str] = mapped_column(String(20))
    nb_services: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    produit_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("produit.id"), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)

    produit: Mapped[Optional[Produit]] = relationship()


class FormuleBoissons(Base):
    __tablename__ = "formule_boissons"

    id: Mapped[uuid.UUID] = _id()
    nom: Mapped[str] = mapped_column(String(100), unique=True)
    # formule : lignes au devis ; consommation : rien au devis, au bon pour facturation ;
    # aucune : rien.
    mode: Mapped[str] = mapped_column(String(20), default="formule")
    base_produit_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("produit.id"), nullable=True)
    coupe_produit_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("produit.id"), nullable=True)
    couleur: Mapped[str] = mapped_column(String(20), default="gris")
    par_defaut: Mapped[bool] = mapped_column(Boolean, default=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)

    base_produit: Mapped[Optional[Produit]] = relationship(foreign_keys=[base_produit_id])
    coupe_produit: Mapped[Optional[Produit]] = relationship(foreign_keys=[coupe_produit_id])


# ---------------------------------------------------------------- clients

class Client(Base):
    __tablename__ = "client"

    id: Mapped[uuid.UUID] = _id()
    type: Mapped[str] = mapped_column(String(20), default="particulier")  # particulier | entreprise
    nom: Mapped[str] = mapped_column(String(200), index=True)
    nom_cle: Mapped[str] = mapped_column(String(200), index=True)  # pour repérer les doublons
    contact_prenom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_nom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    langue: Mapped[str] = mapped_column(String(5), default="fr")
    rue: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    boite: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    code_postal: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ville: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pays: Mapped[str] = mapped_column(String(100), default="Belgique")
    tva: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    reference_po: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    conditions_paiement: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archive: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cree_le: Mapped[datetime] = _cree()
    modifie_le: Mapped[datetime] = _modifie()


# ---------------------------------------------------------------- fiches

class Fiche(Base):
    __tablename__ = "fiche"

    id: Mapped[uuid.UUID] = _id()
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    heure: Mapped[time] = mapped_column(Time)
    couverts: Mapped[int] = mapped_column(Integer)
    espace: Mapped[str] = mapped_column(String(30), default="salle")
    privatisation_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("produit.id"), nullable=True)
    formule_repas_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("formule_repas.id"), nullable=True)
    formule_boissons_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("formule_boissons.id"), nullable=True)
    allergenes: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes_salle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_cuisine: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_sur_place: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    telephone_sur_place: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # brouillon, confirmee, finale, realisee, annulee
    statut: Mapped[str] = mapped_column(String(20), default="brouillon", index=True)
    motif_annulation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    dernier_pdf_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cle_idempotence: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    cree_le: Mapped[datetime] = _cree()
    modifie_le: Mapped[datetime] = _modifie()

    client: Mapped[Client] = relationship()
    privatisation: Mapped[Optional[Produit]] = relationship()
    formule_repas: Mapped[Optional[FormuleRepas]] = relationship()
    formule_boissons: Mapped[Optional[FormuleBoissons]] = relationship()
    lignes: Mapped[list["FicheLigne"]] = relationship(
        back_populates="fiche", cascade="all, delete-orphan", order_by="FicheLigne.ordre"
    )


class FicheLigne(Base):
    __tablename__ = "fiche_ligne"

    id: Mapped[uuid.UUID] = _id()
    fiche_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiche.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))  # entree, plat, dessert, supplement
    produit_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("produit.id"), nullable=True)
    libelle: Mapped[str] = mapped_column(String(200))
    quantite: Mapped[int] = mapped_column(Integer)
    commentaire: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)

    fiche: Mapped[Fiche] = relationship(back_populates="lignes")
    produit: Mapped[Optional[Produit]] = relationship()


# ---------------------------------------------------------------- devis

class Devis(Base):
    __tablename__ = "devis"

    id: Mapped[uuid.UUID] = _id()
    numero: Mapped[str] = mapped_column(String(30), index=True)  # D-2026-0001, commun aux versions
    version: Mapped[int] = mapped_column(Integer, default=1)
    fiche_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiche.id"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client.id"), index=True)
    # brouillon, valide, transmis, envoye, accepte, refuse, remplace
    statut: Mapped[str] = mapped_column(String(20), default="brouillon", index=True)
    date_validite: Mapped[date] = mapped_column(Date)
    couverts: Mapped[int] = mapped_column(Integer)
    total_centimes: Mapped[int] = mapped_column(Integer, default=0)
    remarques_client: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remarques_compta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signature_fiche: Mapped[str] = mapped_column(String(64), default="")
    instantane: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # client + fiche figés
    pdf: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    transmis_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    transmis_par: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    envoye_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reponse_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version_suivante_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    cree_le: Mapped[datetime] = _cree()
    modifie_le: Mapped[datetime] = _modifie()

    fiche: Mapped[Fiche] = relationship()
    client: Mapped[Client] = relationship()
    lignes: Mapped[list["DevisLigne"]] = relationship(
        back_populates="devis", cascade="all, delete-orphan", order_by="DevisLigne.ordre"
    )

    __table_args__ = (UniqueConstraint("numero", "version", name="uq_devis_numero_version"),)


class DevisLigne(Base):
    __tablename__ = "devis_ligne"

    id: Mapped[uuid.UUID] = _id()
    devis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devis.id"), index=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    categorie: Mapped[str] = mapped_column(String(30))
    produit_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("produit.id"), nullable=True)
    libelle: Mapped[str] = mapped_column(String(200))
    quantite: Mapped[int] = mapped_column(Integer)
    unite: Mapped[str] = mapped_column(String(20))
    prix_unitaire_centimes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_centimes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    devis: Mapped[Devis] = relationship(back_populates="lignes")


# ---------------------------------------------------------------- bons pour facturation

class BonFacturation(Base):
    __tablename__ = "bon_facturation"

    id: Mapped[uuid.UUID] = _id()
    numero: Mapped[str] = mapped_column(String(30), unique=True)  # B-2026-0001
    devis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devis.id"), index=True)
    fiche_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiche.id"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client.id"), index=True)
    # brouillon, valide, transmis, facture
    statut: Mapped[str] = mapped_column(String(20), default="brouillon", index=True)
    couverts_reels: Mapped[int] = mapped_column(Integer)
    total_centimes: Mapped[int] = mapped_column(Integer, default=0)
    remarques_compta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instantane: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pdf: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    transmis_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    transmis_par: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    facture_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    numero_facture_compta: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cree_le: Mapped[datetime] = _cree()
    modifie_le: Mapped[datetime] = _modifie()

    devis: Mapped[Devis] = relationship()
    fiche: Mapped[Fiche] = relationship()
    client: Mapped[Client] = relationship()
    lignes: Mapped[list["BonLigne"]] = relationship(
        back_populates="bon", cascade="all, delete-orphan", order_by="BonLigne.ordre"
    )


class BonLigne(Base):
    __tablename__ = "bon_ligne"

    id: Mapped[uuid.UUID] = _id()
    bon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bon_facturation.id"), index=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    categorie: Mapped[str] = mapped_column(String(30))
    produit_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("produit.id"), nullable=True)
    libelle: Mapped[str] = mapped_column(String(200))
    quantite_devis: Mapped[int] = mapped_column(Integer, default=0)  # 0 = extra hors devis
    quantite: Mapped[int] = mapped_column(Integer)
    unite: Mapped[str] = mapped_column(String(20))
    prix_unitaire_centimes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_centimes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    bon: Mapped[BonFacturation] = relationship(back_populates="lignes")


# ---------------------------------------------------------------- journal

class Audit(Base):
    __tablename__ = "audit"

    id: Mapped[uuid.UUID] = _id()
    le: Mapped[datetime] = _cree()
    utilisateur_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    utilisateur_email: Mapped[str] = mapped_column(String(320), default="")
    canal: Mapped[str] = mapped_column(String(20), default="site")  # site | chatgpt | systeme
    action: Mapped[str] = mapped_column(String(60), index=True)
    objet_type: Mapped[str] = mapped_column(String(40), index=True)
    objet_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    resume: Mapped[str] = mapped_column(String(500), default="")
    avant: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    apres: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
