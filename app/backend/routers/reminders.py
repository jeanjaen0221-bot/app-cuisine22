import uuid
from datetime import datetime, timedelta, date as date_type
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    Reservation,
    ReservationItem,
    ReservationReminder,
    ReminderSnoozeIn,
    ReminderRead,
)

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def _has_effective_dishes(items: List[ReservationItem]) -> bool:
    """Return True if there is at least one dish (entrée/plat/dessert) with quantity > 0."""
    for it in items:
        t = (it.type or "").lower().replace("é", "e").replace("è", "e")
        is_dish = t.startswith("entree") or t == "plat" or t == "dessert"
        if is_dish and (it.quantity or 0) > 0 and (it.name or "").strip():
            return True
    return False


@router.get("/pending", response_model=List[ReminderRead])
def get_pending_reminders(
    days: int = Query(default=5, ge=1, le=30),
    session: Session = Depends(get_session),
):
    """
    Return reservations that:
    - are within the next `days` days (today included)
    - have no effective dishes (entrée/plat/dessert)
    - have no provisional menu_formula set
    - are not muted
    - are not snoozed (or snooze has expired)
    """
    now = datetime.utcnow()
    today = now.date()
    cutoff = today + timedelta(days=days)

    # Load all upcoming reservations in window
    stmt = select(Reservation).where(
        Reservation.service_date >= today,
        Reservation.service_date <= cutoff,
    )
    reservations = session.exec(stmt).all()

    # Load existing reminders indexed by reservation_id
    res_ids = [r.id for r in reservations]
    reminders: dict[uuid.UUID, ReservationReminder] = {}
    if res_ids:
        rem_stmt = select(ReservationReminder).where(
            ReservationReminder.reservation_id.in_(res_ids)  # type: ignore[attr-defined]
        )
        for rem in session.exec(rem_stmt).all():
            reminders[rem.reservation_id] = rem

    result: List[ReminderRead] = []
    for res in reservations:
        # Skip if menu_formula already set (provisional formula covers it)
        if (res.menu_formula or "").strip():
            continue

        # Load items for this reservation
        items = session.exec(
            select(ReservationItem).where(ReservationItem.reservation_id == res.id)
        ).all()

        if _has_effective_dishes(list(items)):
            continue

        # Check reminder state
        rem = reminders.get(res.id)
        if rem:
            if rem.muted:
                continue
            if rem.snoozed_until and rem.snoozed_until > now:
                continue

        result.append(ReminderRead(
            reservation_id=res.id,
            client_name=res.client_name,
            service_date=res.service_date,
            pax=res.pax,
            menu_formula=res.menu_formula or None,
            snoozed_until=rem.snoozed_until if rem else None,
            muted=rem.muted if rem else False,
        ))

    # Sort by nearest date first
    result.sort(key=lambda r: r.service_date)
    return result


def _get_or_create_reminder(
    reservation_id: uuid.UUID, session: Session
) -> ReservationReminder:
    rem = session.exec(
        select(ReservationReminder).where(
            ReservationReminder.reservation_id == reservation_id
        )
    ).first()
    if not rem:
        rem = ReservationReminder(
            id=uuid.uuid4(),
            reservation_id=reservation_id,
        )
        session.add(rem)
    return rem


@router.post("/{reservation_id}/snooze")
def snooze_reminder(
    reservation_id: uuid.UUID,
    payload: ReminderSnoozeIn,
    session: Session = Depends(get_session),
):
    hours = max(1, min(payload.hours, 24 * 30))
    rem = _get_or_create_reminder(reservation_id, session)
    rem.snoozed_until = datetime.utcnow() + timedelta(hours=hours)
    rem.updated_at = datetime.utcnow()
    session.add(rem)
    session.commit()
    return {"ok": True, "snoozed_until": rem.snoozed_until}


@router.post("/{reservation_id}/mute")
def mute_reminder(
    reservation_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    rem = _get_or_create_reminder(reservation_id, session)
    rem.muted = True
    rem.updated_at = datetime.utcnow()
    session.add(rem)
    session.commit()
    return {"ok": True}


@router.post("/{reservation_id}/unmute")
def unmute_reminder(
    reservation_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    rem = _get_or_create_reminder(reservation_id, session)
    rem.muted = False
    rem.snoozed_until = None
    rem.updated_at = datetime.utcnow()
    session.add(rem)
    session.commit()
    return {"ok": True}
