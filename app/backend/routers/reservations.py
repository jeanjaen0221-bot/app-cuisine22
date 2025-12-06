from __future__ import annotations
import os
import uuid
import os
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import delete
from sqlmodel import Session, select
from sqlalchemy import or_, and_

from ..database import get_session
from ..models import (
    Reservation,
    ReservationCreate,
    ReservationCreateIn,
    ReservationItem,
    ReservationRead,
    ReservationUpdate,
    BillingInfo,
    BillingInfoCreate,
    BillingInfoRead,
    BillingInfoUpdate,
)
from ..pdf_service import (
    generate_reservation_pdf,
    generate_reservation_pdf_cuisine,
    generate_reservation_pdf_salle,
    generate_day_pdf,
    generate_invoice_pdf,
)

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


@router.get("", response_model=List[ReservationRead])
def list_reservations(
    q: Optional[str] = None,
    service_date: Optional[date] = None,
    session: Session = Depends(get_session),
):
    stmt = select(Reservation).order_by(Reservation.service_date.desc(), Reservation.arrival_time.asc())
    results = session.exec(stmt).all()
    rows: List[Reservation] = results
    if q:
        rows = [r for r in rows if q.lower() in r.client_name.lower()]
    if service_date:
        rows = [r for r in rows if r.service_date == service_date]

    # Attach items for read model
    out: List[ReservationRead] = []
    for r in rows:
        items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == r.id)).all()
        rr = ReservationRead(**r.model_dump(), items=items)
        out.append(rr)
    return out


@router.get("/upcoming", response_model=List[ReservationRead])
def list_upcoming_reservations(
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    session: Session = Depends(get_session),
):
    tz_name = os.getenv("TZ", "Europe/Paris")
    now_local = datetime.now(ZoneInfo(tz_name))
    today = now_local.date()
    now_time = now_local.time()

    condition = or_(
        Reservation.service_date > today,
        and_(Reservation.service_date == today, Reservation.arrival_time >= now_time),
    )

    stmt = (
        select(Reservation)
        .where(condition)
        .order_by(Reservation.service_date.asc(), Reservation.arrival_time.asc())
    )
    if q:
        stmt = stmt.where(Reservation.client_name.ilike(f"%{q}%"))
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    rows = session.exec(stmt).all()
    out: List[ReservationRead] = []
    for r in rows:
        items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == r.id)).all()
        out.append(ReservationRead(**r.model_dump(), items=items))
    return out

@router.get("/past", response_model=List[ReservationRead])
def list_past_reservations(
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    session: Session = Depends(get_session),
):
    tz_name = os.getenv("TZ", "Europe/Paris")
    now_local = datetime.now(ZoneInfo(tz_name))
    today = now_local.date()
    now_time = now_local.time()

    condition = or_(
        Reservation.service_date < today,
        and_(Reservation.service_date == today, Reservation.arrival_time < now_time),
    )

    stmt = (
        select(Reservation)
        .where(condition)
        .order_by(Reservation.service_date.desc(), Reservation.arrival_time.desc())
    )
    if q:
        stmt = stmt.where(Reservation.client_name.ilike(f"%{q}%"))
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    rows = session.exec(stmt).all()
    out: List[ReservationRead] = []
    for r in rows:
        items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == r.id)).all()
        out.append(ReservationRead(**r.model_dump(), items=items))
    return out


@router.post("", response_model=ReservationRead)
def create_reservation(payload: ReservationCreateIn, session: Session = Depends(get_session)):
    # Accept strings for date/time and normalize for safety
    data = payload.model_dump(exclude={"items"})
    raw_service_date = data.get("service_date")
    raw_arrival_time = data.get("arrival_time")
    # Debug (lightweight): log incoming raw fields
    try:
        print(f"CREATE payload service_date={raw_service_date} arrival_time={raw_arrival_time}")
    except Exception:
        pass

    # Default service_date if empty
    if not raw_service_date or not str(raw_service_date).strip():
        raw_service_date = date.today().isoformat()
    # Default arrival_time if empty
    if not raw_arrival_time or not str(raw_arrival_time).strip():
        raw_arrival_time = "00:00:00"

    # Parse service_date
    if isinstance(raw_service_date, str):
        try:
            data["service_date"] = date.fromisoformat(raw_service_date[:10])
        except Exception:
            raise HTTPException(422, "Invalid service_date")
    # Parse arrival_time
    if isinstance(raw_arrival_time, str):
        try:
            t = raw_arrival_time
            if len(t) == 5:
                t = f"{t}:00"
            data["arrival_time"] = dtime.fromisoformat(t)
        except Exception:
            raise HTTPException(422, "Invalid arrival_time")
    # Sanitize/validate remaining fields
    client_name = str(data.get("client_name", "")).strip() or "Client"
    drink_formula = str(data.get("drink_formula", "")).strip() or ""
    notes = str(data.get("notes", "")).strip()
    if len(client_name) > 200:
        client_name = client_name[:200]
    if len(drink_formula) > 200:
        drink_formula = drink_formula[:200]
    if len(notes) > 4000:
        notes = notes[:4000]
    pax = int(data.get("pax") or 1)
    if pax < 1:
        pax = 1
    if pax > 500:
        pax = 500

    data.update({
        "client_name": client_name,
        "drink_formula": drink_formula,
        "notes": notes,
        "pax": pax,
    })
    # Allergens sanitize
    allergens = str(data.get("allergens", "") or "").strip()
    if len(allergens) > 1024:
        allergens = allergens[:1024]
    data["allergens"] = allergens

    # Server-side guard: per-type totals must not exceed pax
    try:
        totals = { 'entrée': 0, 'plat': 0, 'dessert': 0 }
        for it in payload.items:
            if it.type in totals:
                totals[it.type] += int(it.quantity or 0)
        offenders = [
            f"{k}={v}" for k, v in totals.items() if v > pax
        ]
        if offenders:
            raise HTTPException(422, f"Le total par type dépasse le nombre de couverts ({pax}): " + ", ".join(offenders))
    except AttributeError:
        pass

    res = Reservation(**data)
    session.add(res)
    session.commit()
    session.refresh(res)

    for it in payload.items:
        # sanitize items
        nm = (it.name or "").strip()
        qty = int(it.quantity or 0)
        if not nm or qty <= 0:
            continue
        rit = ReservationItem(type=it.type, name=nm, quantity=qty, comment=(it.comment or None), reservation_id=res.id)
        session.add(rit)
    session.commit()

    items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == res.id)).all()
    return ReservationRead(**res.model_dump(), items=items)


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == res.id)).all()
    return ReservationRead(**res.model_dump(), items=items)


@router.put("/{reservation_id}", response_model=ReservationRead)
def update_reservation(reservation_id: uuid.UUID, payload: ReservationUpdate, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")

    update_data = payload.model_dump(exclude_unset=True, exclude={"items"})
    # Normalize string date/time to proper types
    if isinstance(update_data.get("service_date"), str):
        try:
            update_data["service_date"] = date.fromisoformat(update_data["service_date"][:10])
        except Exception:
            del update_data["service_date"]
    if isinstance(update_data.get("arrival_time"), str):
        try:
            t = update_data["arrival_time"]
            if len(t) == 5:
                t = f"{t}:00"
            update_data["arrival_time"] = dtime.fromisoformat(t)
        except Exception:
            del update_data["arrival_time"]
    # Sanitize/validate updates
    if "client_name" in update_data:
        update_data["client_name"] = (str(update_data["client_name"]) or "").strip() or res.client_name
        if len(update_data["client_name"]) > 200:
            update_data["client_name"] = update_data["client_name"][:200]
    if "drink_formula" in update_data:
        update_data["drink_formula"] = (str(update_data["drink_formula"]) or "").strip()
        if len(update_data["drink_formula"]) > 200:
            update_data["drink_formula"] = update_data["drink_formula"][:200]
    if "notes" in update_data:
        update_data["notes"] = (str(update_data["notes"]) or "").strip()
        if len(update_data["notes"]) > 4000:
            update_data["notes"] = update_data["notes"][:4000]
    if "allergens" in update_data:
        update_data["allergens"] = (str(update_data["allergens"]) or "").strip()
        if len(update_data["allergens"]) > 1024:
            update_data["allergens"] = update_data["allergens"][:1024]
    if "pax" in update_data and update_data["pax"] is not None:
        p = int(update_data["pax"])
        if p < 1:
            p = 1
        if p > 500:
            p = 500
        update_data["pax"] = p

    for k, v in update_data.items():
        setattr(res, k, v)
    # touch updated_at
    try:
        setattr(res, 'updated_at', datetime.utcnow())
    except Exception:
        pass
    # Any change invalidates last exported PDF state
    try:
        res.last_pdf_exported_at = None
    except Exception:
        pass
    # Server-side guard: per-type totals must not exceed pax (using incoming items or existing ones)
    try:
        check_pax = update_data.get('pax', res.pax)
        totals = { 'entrée': 0, 'plat': 0, 'dessert': 0 }
        if payload.items is not None:
            for it in payload.items:
                if it.type in totals:
                    totals[it.type] += int(it.quantity or 0)
        else:
            existing_items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == res.id)).all()
            for it in existing_items:
                if it.type in totals:
                    totals[it.type] += int(it.quantity or 0)
        offenders = [
            f"{k}={v}" for k, v in totals.items() if v > (check_pax or 0)
        ]
        if offenders:
            raise HTTPException(422, f"Le total par type dépasse le nombre de couverts ({check_pax}): " + ", ".join(offenders))
    except Exception:
        # if any unexpected error during guard, fail safe to proceed
        pass

    # Atomic update with items replacement (stay on the same session)
    session.add(res)
    if payload.items is not None:
        session.exec(delete(ReservationItem).where(ReservationItem.reservation_id == res.id))
        for it in payload.items:
            nm = (it.name or "").strip()
            qty = int(it.quantity or 0)
            if not nm or qty <= 0:
                continue
            session.add(ReservationItem(type=it.type, name=nm, quantity=qty, comment=(it.comment or None), reservation_id=res.id))
    session.commit()

    session.refresh(res)
    items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == res.id)).all()
    return ReservationRead(**res.model_dump(), items=items)


@router.delete("/{reservation_id}")
def delete_reservation(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    session.delete(res)
    session.exec(delete(ReservationItem).where(ReservationItem.reservation_id == res.id))
    session.commit()
    return {"ok": True}


@router.post("/{reservation_id}/duplicate", response_model=ReservationRead)
def duplicate_reservation(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == res.id)).all()

    new_res = Reservation(**{k: getattr(res, k) for k in [
        'client_name','pax','service_date','arrival_time','drink_formula','notes','status','final_version','allergens'
    ]})
    session.add(new_res)
    session.commit()
    session.refresh(new_res)

    for it in items:
        session.add(ReservationItem(type=it.type, name=it.name, quantity=it.quantity, comment=(it.comment or None), reservation_id=new_res.id))
    session.commit()

    new_items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == new_res.id)).all()
    return ReservationRead(**new_res.model_dump(), items=new_items)


@router.get("/{reservation_id}/pdf")
def export_reservation_pdf(
    reservation_id: uuid.UUID,
    variant: str | None = None,
    session: Session = Depends(get_session),
):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == res.id)).all()
    v = (variant or "").lower().strip()
    if v == "salle":
        path = generate_reservation_pdf_salle(res, items)
    elif v == "cuisine":
        path = generate_reservation_pdf_cuisine(res, items)
    else:
        # Backward compatibility: default to cuisine-style if not specified
        path = generate_reservation_pdf_cuisine(res, items)
    # Mark as exported now
    try:
        res.last_pdf_exported_at = datetime.utcnow()
        session.add(res)
        session.commit()
    except Exception:
        pass
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")


@router.get("/day/{d}/pdf")
def export_day_pdf(d: date, session: Session = Depends(get_session)):
    rows = session.exec(select(Reservation).where(Reservation.service_date == d).order_by(Reservation.arrival_time.asc())).all()
    items_by_res = {}
    for r in rows:
        items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == r.id)).all()
        items_by_res[str(r.id)] = items
    path = generate_day_pdf(d, rows, items_by_res)
    # Mark all as exported now
    try:
        now = datetime.utcnow()
        for r in rows:
            r.last_pdf_exported_at = now
            session.add(r)
        session.commit()
    except Exception:
        pass
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")


# ===== Billing endpoints =====
@router.get("/{reservation_id}/billing", response_model=BillingInfoRead)
def get_billing(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    row = session.get(BillingInfo, reservation_id)
    if not row:
        raise HTTPException(404, "Billing not found")
    return BillingInfoRead(**row.model_dump())


@router.post("/{reservation_id}/billing", response_model=BillingInfoRead)
def create_billing(reservation_id: uuid.UUID, payload: BillingInfoCreate, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    existing = session.get(BillingInfo, reservation_id)
    if existing:
        raise HTTPException(409, "Billing already exists, use PUT to update")
    data = payload.model_dump()
    data.setdefault('country', 'Belgique')
    row = BillingInfo(reservation_id=reservation_id, **data)
    session.add(row)
    session.commit()
    session.refresh(row)
    return BillingInfoRead(**row.model_dump())


@router.put("/{reservation_id}/billing", response_model=BillingInfoRead)
def update_billing(reservation_id: uuid.UUID, payload: BillingInfoUpdate, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    row = session.get(BillingInfo, reservation_id)
    if not row:
        # upsert behavior: create when absent
        data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
        required = ['company_name', 'address_line1', 'zip_code', 'city']
        missing = [k for k in required if not data.get(k)]
        if missing:
            raise HTTPException(400, "Champs requis manquants pour la création (company_name, address_line1, zip_code, city)")
        data.setdefault('country', 'Belgique')
        row = BillingInfo(reservation_id=reservation_id, **data)
        session.add(row)
        session.commit()
        session.refresh(row)
        return BillingInfoRead(**row.model_dump())
    upd = payload.model_dump(exclude_unset=True)
    for k, v in upd.items():
        setattr(row, k, v)
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return BillingInfoRead(**row.model_dump())


@router.get("/{reservation_id}/invoice-pdf")
def export_invoice_pdf(reservation_id: uuid.UUID, session: Session = Depends(get_session)):
    res = session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    items = session.exec(select(ReservationItem).where(ReservationItem.reservation_id == res.id)).all()
    billing = session.get(BillingInfo, reservation_id)
    if not billing:
        raise HTTPException(404, "Billing not found")
    path = generate_invoice_pdf(res, items, billing)
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")
