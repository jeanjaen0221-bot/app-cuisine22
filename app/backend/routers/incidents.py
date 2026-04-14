from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date as ddate, datetime, time as dtime
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..database import get_session
from ..models import (
    IncidentReport,
    IncidentReportCreateIn,
    IncidentReportRead,
    IncidentReportUpdate,
    IncidentSeverity,
)
from ..pdf_service import generate_incident_report_pdf

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _parse_date(s: str) -> ddate:
    try:
        return ddate.fromisoformat(s[:10])
    except Exception:
        raise HTTPException(400, "Date invalide (attendu YYYY-MM-DD)")


def _parse_time(s: str) -> dtime:
    try:
        t = s.strip()
        if len(t) == 5:
            return dtime.fromisoformat(t)
        if len(t) >= 8:
            return dtime.fromisoformat(t[:8])
        return dtime.fromisoformat(t)
    except Exception:
        raise HTTPException(400, "Heure invalide (attendu HH:MM)")


def _now_utc() -> datetime:
    return datetime.utcnow()


@router.get("", response_model=List[IncidentReportRead])
def list_incidents(
    q: Optional[str] = None,
    date: Optional[ddate] = None,
    session: Session = Depends(get_session),
):
    stmt = select(IncidentReport).order_by(IncidentReport.date.desc(), IncidentReport.heure.desc())
    rows = session.exec(stmt).all()
    out: List[IncidentReport] = rows
    if q:
        ql = q.lower()
        out = [
            r
            for r in out
            if (r.client and ql in r.client.lower())
            or (r.lieu and ql in r.lieu.lower())
            or (r.recit_brut and ql in r.recit_brut.lower())
        ]
    if date:
        out = [r for r in out if r.date == date]
    return [IncidentReportRead(**r.model_dump()) for r in out]


@router.post("", response_model=IncidentReportRead)
def create_incident(payload: IncidentReportCreateIn, session: Session = Depends(get_session)):
    row = IncidentReport(
        date=_parse_date(payload.date),
        heure=_parse_time(payload.heure),
        lieu=(payload.lieu or None),
        employes=(payload.employes or None),
        client=(payload.client or None),
        recit_brut=(payload.recit_brut or None),
        contexte=(payload.contexte or None),
        description_incident=(payload.description_incident or None),
        reaction_personnel=(payload.reaction_personnel or None),
        consequences=(payload.consequences or None),
        mesures_prises=(payload.mesures_prises or None),
        observations=(payload.observations or None),
        gravite=payload.gravite or IncidentSeverity.faible,
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return IncidentReportRead(**row.model_dump())


@router.get("/{incident_id}", response_model=IncidentReportRead)
def get_incident(incident_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(IncidentReport, incident_id)
    if not row:
        raise HTTPException(404, "Rapport introuvable")
    return IncidentReportRead(**row.model_dump())


@router.put("/{incident_id}", response_model=IncidentReportRead)
def update_incident(incident_id: uuid.UUID, payload: IncidentReportUpdate, session: Session = Depends(get_session)):
    row = session.get(IncidentReport, incident_id)
    if not row:
        raise HTTPException(404, "Rapport introuvable")

    data = payload.model_dump(exclude_unset=True)
    if "date" in data and data["date"] is not None:
        row.date = _parse_date(str(data["date"]))
    if "heure" in data and data["heure"] is not None:
        row.heure = _parse_time(str(data["heure"]))

    for k in (
        "lieu",
        "employes",
        "client",
        "recit_brut",
        "contexte",
        "description_incident",
        "reaction_personnel",
        "consequences",
        "mesures_prises",
        "observations",
    ):
        if k in data:
            setattr(row, k, data[k] or None)

    if "gravite" in data and data["gravite"] is not None:
        row.gravite = data["gravite"]

    row.updated_at = _now_utc()
    session.add(row)
    session.commit()
    session.refresh(row)
    return IncidentReportRead(**row.model_dump())


@router.delete("/{incident_id}")
def delete_incident(incident_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(IncidentReport, incident_id)
    if not row:
        raise HTTPException(404, "Rapport introuvable")
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.get("/{incident_id}/pdf")
def incident_pdf(incident_id: uuid.UUID, session: Session = Depends(get_session)):
    row = session.get(IncidentReport, incident_id)
    if not row:
        raise HTTPException(404, "Rapport introuvable")
    filename = generate_incident_report_pdf(row)
    return FileResponse(filename, media_type="application/pdf", filename=os.path.basename(filename))


def _extract_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise HTTPException(500, "Réponse IA invalide")
    try:
        return json.loads(m.group(0))
    except Exception:
        raise HTTPException(500, "Réponse IA invalide")


@router.post("/ai-fill")
def ai_fill(payload: Dict[str, Any]):
    provider = (os.getenv("AI_PROVIDER") or "openai").strip().lower()
    if provider not in ("openai", "groq"):
        provider = "openai"

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(400, "GROQ_API_KEY manquant côté serveur")
        model = os.getenv("GROQ_MODEL") or "llama-3.1-70b-versatile"
        url = os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1/chat/completions"
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(400, "OPENAI_API_KEY manquant côté serveur")
        model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/chat/completions"

    recit = str(payload.get("recit_brut") or "").strip()
    if not recit:
        raise HTTPException(400, "recit_brut est requis")

    system = (
        "Tu es un assistant qui transforme un récit libre d'incident client en fiche structurée. "
        "Réponds en français, ton neutre, style factuel et professionnel. "
        "Corrige les fautes et reformule proprement, respecte l'ordre chronologique. "
        "N'invente rien. Si une donnée manque, écris exactement 'Non précisé'. "
        "Classe la gravité uniquement parmi: Faible, Moyen, Élevé. "
        "Réponds uniquement en JSON valide, sans texte autour, avec les clés exactes: "
        "date, heure, lieu, employes, client, recit_brut, contexte, description_incident, reaction_personnel, consequences, mesures_prises, observations, gravite. "
        "Pour date utilise 'YYYY-MM-DD' si la date est explicitement présente, sinon 'Non précisé'. "
        "Pour heure utilise 'HH:MM' si l'heure est explicitement présente, sinon 'Non précisé'."
    )

    user = f"Récit brut:\n{recit}"

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
    except Exception as e:
        raise HTTPException(502, f"Erreur appel IA ({provider}): {e}")

    if resp.status_code >= 400:
        msg = resp.text
        try:
            body = resp.json() or {}
            err = body.get("error") or {}
            code = err.get("code")
            etype = err.get("type")
            emsg = err.get("message")
            if code or etype or emsg:
                msg = f"{code or etype or 'error'}: {emsg or resp.text}"
        except Exception:
            pass

        if provider == "openai" and ("insufficient_quota" in msg or "exceeded your current quota" in msg.lower()):
            raise HTTPException(resp.status_code, "Quota OpenAI dépassé. Configure Groq (AI_PROVIDER=groq + GROQ_API_KEY) ou vérifie ton plan OpenAI.")
        raise HTTPException(resp.status_code, f"IA API error ({provider}): {msg}")

    data = resp.json() or {}
    content = (
        (((data.get("choices") or [{}])[0] or {}).get("message") or {}).get("content")
        if isinstance(data, dict)
        else None
    )
    if not content:
        raise HTTPException(500, "Réponse IA vide")

    obj = _extract_json(str(content))

    allowed = {
        "date",
        "heure",
        "lieu",
        "employes",
        "client",
        "recit_brut",
        "contexte",
        "description_incident",
        "reaction_personnel",
        "consequences",
        "mesures_prises",
        "observations",
        "gravite",
    }
    cleaned: Dict[str, Any] = {k: obj.get(k) for k in allowed}

    if cleaned.get("recit_brut") in (None, "", "Non précisé"):
        cleaned["recit_brut"] = recit

    g = str(cleaned.get("gravite") or "").strip()
    if g not in ("Faible", "Moyen", "Élevé"):
        cleaned["gravite"] = "Faible"

    return cleaned
