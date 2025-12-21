from __future__ import annotations
import uuid
from datetime import date, time, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint, CheckConstraint, Index


class ReservationStatus(str, Enum):
    draft = "draft"
    confirmed = "confirmed"
    printed = "printed"


class MenuItemBase(SQLModel):
    name: str
    type: str  # entrée / plat / dessert
    active: bool = True


class MenuItem(MenuItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    type: str
    active: bool = True


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemRead(MenuItemBase):
    id: uuid.UUID


class MenuItemUpdate(SQLModel):
    name: Optional[str] = None
    type: Optional[str] = None
    active: Optional[bool] = None


class DrinkBase(SQLModel):
    name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    active: bool = True


class Drink(DrinkBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    active: bool = True
    __table_args__ = (
        UniqueConstraint('name', name='uq_drink_name'),
        Index('ix_drink_name', 'name'),
    )


class DrinkCreate(DrinkBase):
    pass


class DrinkRead(DrinkBase):
    id: uuid.UUID


class DrinkUpdate(SQLModel):
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    active: Optional[bool] = None


class ReservationItemBase(SQLModel):
    type: str  # entrée / plat / dessert
    name: str
    quantity: int = 1
    comment: Optional[str] = None


class ReservationItem(ReservationItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    reservation_id: uuid.UUID | None = Field(default=None, foreign_key="reservation.id")
    type: str
    name: str
    quantity: int = 0
    comment: Optional[str] = None


class ReservationItemCreate(ReservationItemBase):
    pass


class ReservationItemRead(ReservationItemBase):
    id: uuid.UUID


class ReservationBase(SQLModel):
    client_name: str
    pax: int
    service_date: date
    arrival_time: time
    drink_formula: str
    notes: Optional[str] = None
    status: ReservationStatus = ReservationStatus.draft
    final_version: bool = False
    on_invoice: bool = False
    allergens: Optional[str] = ""  # CSV: e.g. "gluten,arachides,soja"


class Reservation(ReservationBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_pdf_exported_at: Optional[datetime] = None
    __table_args__ = (
        UniqueConstraint('service_date','arrival_time','client_name','pax', name='uq_reservation_slot'),
        CheckConstraint('pax >= 1', name='ck_reservation_pax_min'),
        Index('ix_reservation_date_time', 'service_date', 'arrival_time'),
    )


class ReservationCreate(ReservationBase):
    items: List[ReservationItemCreate] = Field(default_factory=list)


# Input model variant that accepts strings for date/time (used by create endpoint)
class ReservationCreateIn(SQLModel):
    client_name: str
    pax: int
    service_date: str
    arrival_time: str
    drink_formula: str
    notes: Optional[str] = None
    status: ReservationStatus = ReservationStatus.draft
    final_version: bool = False
    on_invoice: bool = False
    allergens: Optional[str] = ""
    items: List[ReservationItemCreate] = Field(default_factory=list)


class ReservationUpdate(SQLModel):
    client_name: Optional[str] = None
    pax: Optional[int] = None
    service_date: Optional[str] = None
    arrival_time: Optional[str] = None
    drink_formula: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[ReservationStatus] = None
    final_version: Optional[bool] = None
    on_invoice: Optional[bool] = None
    allergens: Optional[str] = None
    items: Optional[List[ReservationItemCreate]] = None


class ReservationRead(ReservationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    last_pdf_exported_at: Optional[datetime] = None
    items: List[ReservationItemRead] = Field(default_factory=list)


# Key/Value settings storage (e.g., Zenchef token and restaurant id)
class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


# Store processed idempotency keys
class ProcessedRequest(SQLModel, table=True):
    key: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Store allergens metadata and icon bytes in DB (in addition to file assets for compatibility)
class Allergen(SQLModel, table=True):
    key: str = Field(primary_key=True)
    label: str
    icon_bytes: Optional[bytes] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Note(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NoteCreate(SQLModel):
    name: str
    content: str


class NoteUpdate(SQLModel):
    name: Optional[str] = None
    content: Optional[str] = None


class NoteRead(SQLModel):
    id: uuid.UUID
    name: str
    content: str
    created_at: datetime
    updated_at: datetime


# Billing information for invoicing linked to a reservation
class BillingInfo(SQLModel, table=True):
    # Use reservation_id as primary key to enforce 1:1 relation
    reservation_id: uuid.UUID = Field(primary_key=True, foreign_key="reservation.id")
    company_name: str
    address_line1: str
    address_line2: Optional[str] = None
    zip_code: str
    city: str
    country: str = "Belgique"
    vat_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BillingInfoCreate(SQLModel):
    company_name: str
    address_line1: str
    address_line2: Optional[str] = None
    zip_code: str
    city: str
    country: Optional[str] = None
    vat_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


class BillingInfoUpdate(SQLModel):
    company_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    vat_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


class BillingInfoRead(SQLModel):
    reservation_id: uuid.UUID
    company_name: str
    address_line1: str
    address_line2: Optional[str] = None
    zip_code: str
    city: str
    country: str
    vat_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
