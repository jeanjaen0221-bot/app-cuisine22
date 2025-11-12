from __future__ import annotations
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Note as NoteModel, NoteCreate, NoteUpdate, NoteRead

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=List[NoteRead])
def list_notes(session: Session = Depends(get_session)):
    rows = session.exec(select(NoteModel).order_by(NoteModel.updated_at.desc())).all()
    return [NoteRead(**r.model_dump()) for r in rows]


@router.post("", response_model=NoteRead)
def create_note(payload: NoteCreate, session: Session = Depends(get_session)):
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(400, "Content is required")
    row = NoteModel(content=content)
    session.add(row)
    session.commit()
    session.refresh(row)
    return NoteRead(**row.model_dump())


@router.put("/{note_id}", response_model=NoteRead)
def update_note(note_id: uuid.UUID, payload: NoteUpdate, session: Session = Depends(get_session)):
    row = session.get(NoteModel, note_id)
    if not row:
        raise HTTPException(404, "Note not found")
    if payload.content is not None:
        row.content = (payload.content or "").strip()
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return NoteRead(**row.model_dump())


@router.delete("/{note_id}")
def delete_note(note_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(NoteModel, note_id)
    if not row:
        raise HTTPException(404, "Note not found")
    session.delete(row)
    session.commit()
    return {"ok": True}
