from __future__ import annotations
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    Supplier, SupplierCreate, SupplierRead, SupplierUpdate,
    DrinkVendor, DrinkVendorRead, DrinkVendorUpsert, Drink, DrinkRead
)

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=List[SupplierRead])
def list_suppliers(session: Session = Depends(get_session)):
    return session.exec(select(Supplier).order_by(Supplier.name.asc())).all()


@router.post("", response_model=SupplierRead)
def create_supplier(payload: SupplierCreate, session: Session = Depends(get_session)):
    row = Supplier(**payload.model_dump(exclude_none=True))
    if row.active is None:
        row.active = True
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(Supplier, supplier_id)
    if not row:
        raise HTTPException(404, "Supplier not found")
    return row


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier(supplier_id: uuid.UUID, payload: SupplierUpdate, session: Session = Depends(get_session)):
    row = session.get(Supplier, supplier_id)
    if not row:
        raise HTTPException(404, "Supplier not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(Supplier, supplier_id)
    if not row:
        raise HTTPException(404, "Supplier not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


# ---- Vendor mapping (which supplier sells which drink and at what price/pack) ----
@router.get("/{supplier_id}/drinks", response_model=List[DrinkVendorRead])
def list_supplier_drinks(supplier_id: uuid.UUID, session: Session = Depends(get_session)):
    # verify supplier
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    rows = session.exec(select(DrinkVendor).where(DrinkVendor.supplier_id == supplier_id)).all()
    return [DrinkVendorRead(**r.model_dump()) for r in rows]


@router.put("/{supplier_id}/drinks", response_model=List[DrinkVendorRead])
def upsert_supplier_drinks(
    supplier_id: uuid.UUID,
    payload: List[DrinkVendorUpsert],
    session: Session = Depends(get_session),
):
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    out: list[DrinkVendorRead] = []
    for item in payload:
        if item.supplier_id and item.supplier_id != supplier_id:
            raise HTTPException(400, "supplier_id mismatch")
        if not item.drink_id:
            raise HTTPException(400, "Missing drink_id")
        d = session.get(Drink, item.drink_id)
        if not d:
            raise HTTPException(400, f"Drink not found: {item.drink_id}")
        pk = {"drink_id": item.drink_id, "supplier_id": supplier_id}
        existing = session.get(DrinkVendor, (item.drink_id, supplier_id))
        if not existing:
            existing = DrinkVendor(**pk)
        data = item.model_dump(exclude_unset=True)
        data.pop("supplier_id", None)
        for k, v in data.items():
            setattr(existing, k, v)
        session.add(existing)
        out.append(DrinkVendorRead(**existing.model_dump()))
    session.commit()
    return out


@router.get("/drinks/{drink_id}", response_model=List[DrinkVendorRead])
def list_drink_suppliers(drink_id: uuid.UUID, session: Session = Depends(get_session)):
    d = session.get(Drink, drink_id)
    if not d:
        raise HTTPException(404, "Drink not found")
    rows = session.exec(select(DrinkVendor).where(DrinkVendor.drink_id == drink_id)).all()
    return [DrinkVendorRead(**r.model_dump()) for r in rows]
