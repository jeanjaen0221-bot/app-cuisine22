from __future__ import annotations
import datetime as dt
from typing import Optional, Dict, Any, List

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..database import get_session
from ..models import Setting, Reservation, ReservationItem, ProcessedRequest

router = APIRouter(prefix="/api/zenchef", tags=["zenchef"])


def get_setting(session: Session, key: str) -> Optional[str]:
    row = session.get(Setting, key)
    return row.value if row else None


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row:
        row.value = value
        session.add(row)
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


@router.get("/settings")
def read_settings(session: Session = Depends(get_session)) -> Dict[str, Optional[str]]:
    return {
        "api_token": get_setting(session, "zenchef_api_token"),
        "restaurant_id": get_setting(session, "zenchef_restaurant_id"),
    }


@router.put("/settings")
def update_settings(payload: Dict[str, Optional[str]], session: Session = Depends(get_session)):
    token = payload.get("api_token")
    restaurant_id = payload.get("restaurant_id")
    if token is not None:
        set_setting(session, "zenchef_api_token", token)
    if restaurant_id is not None:
        set_setting(session, "zenchef_restaurant_id", restaurant_id)
    return {"ok": True}


def parse_start_time(iso: str) -> tuple[str, str]:
    # Expect ISO like 2025-10-15T19:30:00Z or with offset
    try:
        # Remove Z for fromisoformat if present
        clean = iso.replace("Z", "+00:00") if iso.endswith("Z") else iso
        dt_obj = dt.datetime.fromisoformat(clean)
        return dt_obj.date().isoformat(), dt_obj.time().strftime("%H:%M")
    except Exception:
        # fallback: split on 'T'
        if "T" in iso:
            d, t = iso.split("T", 1)
            return d[:10], t[:5]
        return iso[:10], "00:00"


@router.post("/sync")
@router.post("/sync/")
def sync_reservations(body: Dict[str, Any], request: Request, session: Session = Depends(get_session)):
    # Idempotency: if Idempotency-Key header is present and already processed, exit early
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        try:
            session.add(ProcessedRequest(key=idem_key))
            session.commit()
        except Exception:
            session.rollback()
            # Already processed; no-op
            return {"created": [], "count": 0, "fromDate": body.get("fromDate"), "toDate": body.get("toDate"), "idempotent": True}
    token = get_setting(session, "zenchef_api_token")
    restaurant_id = get_setting(session, "zenchef_restaurant_id")
    if not token or not restaurant_id:
        raise HTTPException(400, "Zenchef settings missing: api_token and restaurant_id are required")

    from_date: str = body.get("fromDate") or dt.date.today().isoformat()
    to_date: str = body.get("toDate") or from_date

    url = "https://api.zenchef.com/v1/reservations"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    created: List[Dict[str, Any]] = []
    page = 1
    per_page = int(body.get("perPage") or 250)
    while True:
        params = {
            "restaurantId": restaurant_id,
            "fromDate": from_date,
            "toDate": to_date,
            "perPage": per_page,
            "page": page,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, f"Zenchef API error: {resp.text}")
        data = resp.json() or {}
        reservations = data.get("reservations", [])

        # Filter > 10 people
        big = [r for r in reservations if (r.get("numberOfPeople") or 0) > 10]
        for r in big:
            d_str, t_str = parse_start_time(r.get("startTime", ""))
            pax = int(r.get("numberOfPeople") or 0)
            if pax < 1:
                pax = 1
            if pax > 500:
                pax = 500
            customer = r.get("customer") or {}
            client_name = (customer.get("firstname") or "").strip() + " " + (customer.get("lastname") or "").strip()
            client_name = client_name.strip() or "Groupe"
            if len(client_name) > 200:
                client_name = client_name[:200]

            # De-dup criterion: same date, time, name, pax
            exists = session.exec(
                select(Reservation).where(
                    (Reservation.service_date == d_str)
                    & (Reservation.arrival_time == t_str)
                    & (Reservation.client_name == client_name)
                    & (Reservation.pax == pax)
                )
            ).first()
            if exists:
                continue

            res = Reservation(
                client_name=client_name,
                pax=pax,
                service_date=d_str,
                arrival_time=t_str,
                drink_formula="Sans alcool",
                notes="Import Zenchef",
                status="confirmed",
            )
            session.add(res)
            try:
                session.commit()
                session.refresh(res)
                created.append({"id": str(res.id), "client_name": client_name, "service_date": d_str, "arrival_time": t_str, "pax": pax})
            except IntegrityError:
                session.rollback()
                # Duplicate (based on unique constraint if present); skip silently
                continue

        # pagination end condition
        if not reservations or len(reservations) < per_page:
            break
        page += 1

    return {"created": created, "count": len(created), "fromDate": from_date, "toDate": to_date}
