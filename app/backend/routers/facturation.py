import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    InvoiceSupplement,
    InvoiceSupplementCreate,
    InvoiceSupplementRead,
    InvoiceSupplementUpdate,
    Reservation,
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

@router.get("/reservations/{reservation_id}/supplements", response_model=List[InvoiceSupplementRead])
def list_supplements(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    if not session.get(Reservation, reservation_id):
        raise HTTPException(404, "Reservation not found")
    return session.exec(
        select(InvoiceSupplement)
        .where(InvoiceSupplement.reservation_id == reservation_id)
        .order_by(InvoiceSupplement.sort_order, InvoiceSupplement.created_at)
    ).all()


@router.post("/reservations/{reservation_id}/supplements", response_model=InvoiceSupplementRead, status_code=201)
def add_supplement(reservation_id: uuid.UUID, payload: InvoiceSupplementCreate, session: Session = Depends(get_session)):
    if not session.get(Reservation, reservation_id):
        raise HTTPException(404, "Reservation not found")
    sup = InvoiceSupplement(reservation_id=reservation_id, **payload.model_dump())
    session.add(sup)
    session.commit()
    session.refresh(sup)
    return sup


@router.put("/reservations/{reservation_id}/supplements/{sup_id}", response_model=InvoiceSupplementRead)
def update_supplement(reservation_id: uuid.UUID, sup_id: uuid.UUID, payload: InvoiceSupplementUpdate, session: Session = Depends(get_session)):
    sup = session.get(InvoiceSupplement, sup_id)
    if not sup or sup.reservation_id != reservation_id:
        raise HTTPException(404, "Supplement not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sup, k, v)
    session.add(sup)
    session.commit()
    session.refresh(sup)
    return sup


@router.delete("/reservations/{reservation_id}/supplements/{sup_id}", status_code=204)
def delete_supplement(reservation_id: uuid.UUID, sup_id: uuid.UUID, session: Session = Depends(get_session)):
    sup = session.get(InvoiceSupplement, sup_id)
    if not sup or sup.reservation_id != reservation_id:
        raise HTTPException(404, "Supplement not found")
    session.delete(sup)
    session.commit()
