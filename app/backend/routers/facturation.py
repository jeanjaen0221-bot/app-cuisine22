import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    InvoiceSupplementCreate,
    InvoiceSupplementRead,
    InvoiceSupplementUpdate,
    Reservation,
    ReservationItem,
    SupplementPreset,
    SupplementPresetCreate,
    SupplementPresetRead,
    SupplementPresetUpdate,
)

router = APIRouter(prefix="/api", tags=["facturation"])


# ===== Supplement Presets =====

@router.get("/supplement-presets", response_model=List[SupplementPresetRead])
def list_presets(session: Session = Depends(get_session)):
    return session.exec(select(SupplementPreset).order_by(SupplementPreset.created_at)).all()


@router.post("/supplement-presets", response_model=SupplementPresetRead, status_code=201)
def create_preset(payload: SupplementPresetCreate, session: Session = Depends(get_session)):
    preset = SupplementPreset(**payload.model_dump())
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


@router.put("/supplement-presets/{preset_id}", response_model=SupplementPresetRead)
def update_preset(preset_id: uuid.UUID, payload: SupplementPresetUpdate, session: Session = Depends(get_session)):
    preset = session.get(SupplementPreset, preset_id)
    if not preset:
        raise HTTPException(404, "Preset not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(preset, k, v)
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


@router.delete("/supplement-presets/{preset_id}", status_code=204)
def delete_preset(preset_id: uuid.UUID, session: Session = Depends(get_session)):
    preset = session.get(SupplementPreset, preset_id)
    if not preset:
        raise HTTPException(404, "Preset not found")
    session.delete(preset)
    session.commit()


# ===== Invoice Supplements (per reservation) =====
# Backed by ReservationItem(type='supplément') so supplements appear
# on the fiche and in all PDFs without duplication.

_SUPP_TYPE = "supplément"


def _item_to_sup(item: ReservationItem) -> Dict[str, Any]:
    """Convert a ReservationItem supplement to InvoiceSupplementRead shape."""
    return {
        "id": item.id,
        "reservation_id": item.reservation_id,
        "description": item.name,
        "quantity": item.quantity,
        "sort_order": 0,
        "created_at": datetime.utcnow(),
    }


@router.get("/reservations/{reservation_id}/supplements", response_model=List[InvoiceSupplementRead])
def list_supplements(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    if not session.get(Reservation, reservation_id):
        raise HTTPException(404, "Reservation not found")
    items = session.exec(
        select(ReservationItem)
        .where(ReservationItem.reservation_id == reservation_id)
        .where(ReservationItem.type == _SUPP_TYPE)
    ).all()
    return [_item_to_sup(i) for i in items]


@router.post("/reservations/{reservation_id}/supplements", response_model=InvoiceSupplementRead, status_code=201)
def add_supplement(reservation_id: uuid.UUID, payload: InvoiceSupplementCreate, session: Session = Depends(get_session)):
    if not session.get(Reservation, reservation_id):
        raise HTTPException(404, "Reservation not found")
    item = ReservationItem(
        reservation_id=reservation_id,
        type=_SUPP_TYPE,
        name=payload.description,
        quantity=payload.quantity,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_to_sup(item)


@router.put("/reservations/{reservation_id}/supplements/{sup_id}", response_model=InvoiceSupplementRead)
def update_supplement(reservation_id: uuid.UUID, sup_id: uuid.UUID, payload: InvoiceSupplementUpdate, session: Session = Depends(get_session)):
    item = session.get(ReservationItem, sup_id)
    if not item or item.reservation_id != reservation_id or item.type != _SUPP_TYPE:
        raise HTTPException(404, "Supplement not found")
    if payload.description is not None:
        item.name = payload.description
    if payload.quantity is not None:
        item.quantity = payload.quantity
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_to_sup(item)


@router.delete("/reservations/{reservation_id}/supplements/{sup_id}", status_code=204)
def delete_supplement(reservation_id: uuid.UUID, sup_id: uuid.UUID, session: Session = Depends(get_session)):
    item = session.get(ReservationItem, sup_id)
    if not item or item.reservation_id != reservation_id or item.type != _SUPP_TYPE:
        raise HTTPException(404, "Supplement not found")
    session.delete(item)
    session.commit()
