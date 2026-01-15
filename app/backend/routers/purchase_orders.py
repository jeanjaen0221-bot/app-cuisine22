from __future__ import annotations
import csv
import io
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    PurchaseOrder, PurchaseOrderCreate, PurchaseOrderRead, PurchaseOrderUpdate,
    PurchaseOrderItem, PurchaseOrderItemCreate, PurchaseOrderItemRead,
    PurchaseOrderStatus, Drink
)

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


def _read_order(session: Session, oid: uuid.UUID) -> PurchaseOrder:
    row = session.get(PurchaseOrder, oid)
    if not row:
        raise HTTPException(404, "Order not found")
    return row


def _order_to_read(session: Session, row: PurchaseOrder) -> PurchaseOrderRead:
    items = session.exec(select(PurchaseOrderItem).where(PurchaseOrderItem.order_id == row.id)).all()
    return PurchaseOrderRead(
        id=row.id,
        supplier_id=row.supplier_id,
        status=row.status,
        note=row.note,
        created_at=row.created_at,
        items=[PurchaseOrderItemRead(**it.model_dump()) for it in items],
    )


@router.get("", response_model=List[PurchaseOrderRead])
def list_orders(status: Optional[PurchaseOrderStatus] = None, session: Session = Depends(get_session)):
    q = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    if status is not None:
        q = q.where(PurchaseOrder.status == status)
    rows = session.exec(q).all()
    out: list[PurchaseOrderRead] = []
    for r in rows:
        out.append(_order_to_read(session, r))
    return out


@router.post("", response_model=PurchaseOrderRead)
def create_order(payload: PurchaseOrderCreate, session: Session = Depends(get_session)):
    row = PurchaseOrder(supplier_id=payload.supplier_id, note=payload.note or None)
    session.add(row)
    session.commit()
    session.refresh(row)
    # Add items
    for it in payload.items:
        name: Optional[str] = it.name
        unit: Optional[str] = it.unit
        if it.drink_id:
            d = session.get(Drink, it.drink_id)
            if not d:
                raise HTTPException(400, f"Drink not found: {it.drink_id}")
            name = name or d.name
            unit = unit or d.unit
        item = PurchaseOrderItem(
            order_id=row.id,
            drink_id=it.drink_id,
            name=name or "",
            unit=unit,
            quantity=max(0, int(it.quantity or 0)),
            price_cents=it.price_cents,
        )
        session.add(item)
    session.commit()
    return _order_to_read(session, row)


@router.get("/{order_id}", response_model=PurchaseOrderRead)
def get_order(order_id: uuid.UUID, session: Session = Depends(get_session)):
    row = _read_order(session, order_id)
    return _order_to_read(session, row)


@router.put("/{order_id}", response_model=PurchaseOrderRead)
def update_order(order_id: uuid.UUID, payload: PurchaseOrderUpdate, session: Session = Depends(get_session)):
    row = _read_order(session, order_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    return _order_to_read(session, row)


@router.post("/{order_id}/items", response_model=PurchaseOrderRead)
def add_item(order_id: uuid.UUID, item: PurchaseOrderItemCreate, session: Session = Depends(get_session)):
    row = _read_order(session, order_id)
    name: Optional[str] = item.name
    unit: Optional[str] = item.unit
    if item.drink_id:
        d = session.get(Drink, item.drink_id)
        if not d:
            raise HTTPException(400, f"Drink not found: {item.drink_id}")
        name = name or d.name
        unit = unit or d.unit
    it = PurchaseOrderItem(
        order_id=row.id,
        drink_id=item.drink_id,
        name=name or "",
        unit=unit,
        quantity=max(0, int(item.quantity or 0)),
        price_cents=item.price_cents,
    )
    session.add(it)
    session.commit()
    return _order_to_read(session, row)


@router.put("/{order_id}/items/{item_id}", response_model=PurchaseOrderRead)
def update_item(order_id: uuid.UUID, item_id: uuid.UUID, payload: PurchaseOrderItemCreate, session: Session = Depends(get_session)):
    _ = _read_order(session, order_id)
    it = session.get(PurchaseOrderItem, item_id)
    if not it or it.order_id != order_id:
        raise HTTPException(404, "Item not found")
    name: Optional[str] = payload.name
    unit: Optional[str] = payload.unit
    if payload.drink_id:
        d = session.get(Drink, payload.drink_id)
        if not d:
            raise HTTPException(400, f"Drink not found: {payload.drink_id}")
        name = name or d.name
        unit = unit or d.unit
    it.drink_id = payload.drink_id
    it.name = name or it.name
    it.unit = unit
    it.quantity = max(0, int(payload.quantity or it.quantity))
    it.price_cents = payload.price_cents
    session.add(it)
    session.commit()
    return _order_to_read(session, _)


@router.delete("/{order_id}/items/{item_id}")
def delete_item(order_id: uuid.UUID, item_id: uuid.UUID, session: Session = Depends(get_session)):
    _ = _read_order(session, order_id)
    it = session.get(PurchaseOrderItem, item_id)
    if not it or it.order_id != order_id:
        raise HTTPException(404, "Item not found")
    session.delete(it)
    session.commit()
    return {"ok": True}


@router.get("/{order_id}/export.csv")
def export_csv(order_id: uuid.UUID, session: Session = Depends(get_session)):
    row = _read_order(session, order_id)
    items = session.exec(select(PurchaseOrderItem).where(PurchaseOrderItem.order_id == row.id)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "unit", "quantity"])
    for it in items:
        writer.writerow([it.name, it.unit or "", it.quantity])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=order_{row.id}.csv"
    })
