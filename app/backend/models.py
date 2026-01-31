from __future__ import annotations
import uuid
from datetime import date, time, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint, CheckConstraint, Index, Column, JSON


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


# Per-drink stock settings for replenishment
class DrinkStock(SQLModel, table=True):
    drink_id: uuid.UUID = Field(primary_key=True, foreign_key="drink.id")
    min_qty: int = 0
    max_qty: int = 0
    pack_size: Optional[int] = None
    reorder_enabled: bool = True


class DrinkStockRead(SQLModel):
    drink_id: uuid.UUID
    min_qty: int
    max_qty: int
    pack_size: Optional[int] = None
    reorder_enabled: bool


class DrinkStockUpdate(SQLModel):
    min_qty: Optional[int] = None
    max_qty: Optional[int] = None
    pack_size: Optional[int] = None
    reorder_enabled: Optional[bool] = None


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


# --- Suppliers & Purchasing ---
class Supplier(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    active: bool = True


class SupplierCreate(SQLModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class SupplierUpdate(SQLModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class SupplierRead(SQLModel):
    id: uuid.UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    active: bool


class DrinkVendor(SQLModel, table=True):
    drink_id: uuid.UUID = Field(foreign_key="drink.id", primary_key=True)
    supplier_id: uuid.UUID = Field(foreign_key="supplier.id", primary_key=True)
    vendor_sku: Optional[str] = None
    price_cents: Optional[int] = None
    pack_size: Optional[int] = None
    preferred: bool = False


class DrinkVendorRead(SQLModel):
    drink_id: uuid.UUID
    supplier_id: uuid.UUID
    vendor_sku: Optional[str] = None
    price_cents: Optional[int] = None
    pack_size: Optional[int] = None
    preferred: bool = False


class DrinkVendorUpsert(SQLModel):
    drink_id: uuid.UUID
    supplier_id: uuid.UUID
    vendor_sku: Optional[str] = None
    price_cents: Optional[int] = None
    pack_size: Optional[int] = None
    preferred: Optional[bool] = None


class PurchaseOrderStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    received = "received"
    cancelled = "cancelled"


class PurchaseOrder(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    supplier_id: Optional[uuid.UUID] = Field(default=None, foreign_key="supplier.id")
    status: PurchaseOrderStatus = PurchaseOrderStatus.draft
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseOrderItem(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="purchaseorder.id")
    drink_id: Optional[uuid.UUID] = Field(default=None, foreign_key="drink.id")
    name: str
    unit: Optional[str] = None
    quantity: int = 0
    price_cents: Optional[int] = None


class PurchaseOrderItemCreate(SQLModel):
    drink_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    quantity: int
    price_cents: Optional[int] = None


class PurchaseOrderCreate(SQLModel):
    supplier_id: Optional[uuid.UUID] = None
    note: Optional[str] = None
    items: List[PurchaseOrderItemCreate] = Field(default_factory=list)


class PurchaseOrderItemRead(SQLModel):
    id: uuid.UUID
    order_id: uuid.UUID
    drink_id: Optional[uuid.UUID] = None
    name: str
    unit: Optional[str] = None
    quantity: int
    price_cents: Optional[int] = None


class PurchaseOrderUpdate(SQLModel):
    supplier_id: Optional[uuid.UUID] = None
    status: Optional[PurchaseOrderStatus] = None
    note: Optional[str] = None


class PurchaseOrderRead(SQLModel):
    id: uuid.UUID
    supplier_id: Optional[uuid.UUID] = None
    status: PurchaseOrderStatus
    note: Optional[str] = None
    created_at: datetime
    items: List[PurchaseOrderItemRead] = Field(default_factory=list)


class FloorPlanBase(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str = "base"
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FloorPlanBaseRead(SQLModel):
    id: uuid.UUID
    name: str
    data: dict
    created_at: datetime
    updated_at: datetime


class FloorPlanBaseUpdate(SQLModel):
    name: Optional[str] = None
    data: Optional[dict] = None


class FloorPlanInstance(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    service_date: date
    service_label: Optional[str] = None
    template_id: uuid.UUID = Field(foreign_key="floorplanbase.id")
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    assignments: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint('service_date', 'service_label', name='uq_floorplan_instance'),
    )


class FloorPlanInstanceRead(SQLModel):
    id: uuid.UUID
    service_date: date
    service_label: Optional[str] = None
    template_id: uuid.UUID
    data: dict
    assignments: dict
    created_at: datetime
    updated_at: datetime


class FloorPlanInstanceCreate(SQLModel):
    service_date: date
    service_label: Optional[str] = None


class FloorPlanInstanceUpdate(SQLModel):
    data: Optional[dict] = None
    assignments: Optional[dict] = None
