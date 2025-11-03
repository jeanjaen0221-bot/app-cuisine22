from __future__ import annotations
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import MenuItem, MenuItemCreate, MenuItemRead, MenuItemUpdate

router = APIRouter(prefix="/api/menu-items", tags=["menu_items"])


@router.get("", response_model=List[MenuItemRead])
def list_items(session: Session = Depends(get_session)):
    return session.exec(select(MenuItem).order_by(MenuItem.name.asc())).all()


@router.post("", response_model=MenuItemRead)
def create_item(payload: MenuItemCreate, session: Session = Depends(get_session)):
    it = MenuItem(**payload.model_dump())
    session.add(it)
    session.commit()
    session.refresh(it)
    return it


@router.get("/search")
def search_items(q: Optional[str] = None, type: Optional[str] = None, session: Session = Depends(get_session)):
    def norm(s: str) -> str:
        return s.lower().replace("é", "e")
    rows = session.exec(select(MenuItem).where(MenuItem.active == True)).all()
    if type:
        t = norm(type)
        rows = [r for r in rows if norm(r.type) == t or (t == "entree" and norm(r.type) in ["entree", "entrees"])]
    if q:
        rows = [r for r in rows if q.lower() in r.name.lower()]
    return rows[:20]


@router.get("/{item_id}", response_model=MenuItemRead)
def get_item(item_id: uuid.UUID, session: Session = Depends(get_session)):
    it = session.get(MenuItem, item_id)
    if not it:
        raise HTTPException(404, "Item not found")
    return it


@router.put("/{item_id}", response_model=MenuItemRead)
def update_item(item_id: uuid.UUID, payload: MenuItemUpdate, session: Session = Depends(get_session)):
    it = session.get(MenuItem, item_id)
    if not it:
        raise HTTPException(404, "Item not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(it, k, v)
    session.add(it)
    session.commit()
    session.refresh(it)
    return it


@router.delete("/{item_id}")
def delete_item(item_id: uuid.UUID, session: Session = Depends(get_session)):
    it = session.get(MenuItem, item_id)
    if not it:
        raise HTTPException(404, "Item not found")
    session.delete(it)
    session.commit()
    return {"ok": True}
