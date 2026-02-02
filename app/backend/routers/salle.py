"""
Salle (Floor Plan) Router
Handles PDF import and reservation management for table planning
"""

import logging
import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlmodel import Session, select

from ..database import get_session
from ..models import SalleService, SalleServiceRead, SalleServiceCreate
from ..pdf_parser import ReservationParser
from ..table_manager import create_base_plan, auto_assign_tables

router = APIRouter(prefix="/api/salle", tags=["salle"])
logger = logging.getLogger("app.salle")
logger.propagate = True
logger.setLevel(logging.DEBUG)


# ---- Service Management ----

@router.get("/services", response_model=list[SalleServiceRead])
def list_services(session: Session = Depends(get_session)):
    """List all services."""
    services = session.exec(select(SalleService).order_by(SalleService.service_date.desc())).all()
    return services


@router.post("/services", response_model=SalleServiceRead)
def create_service(payload: SalleServiceCreate, session: Session = Depends(get_session)):
    """Create a new service."""
    # Check if service already exists
    existing = session.exec(
        select(SalleService).where(
            SalleService.service_date == payload.service_date,
            SalleService.service_label == payload.service_label
        )
    ).first()
    
    if existing:
        raise HTTPException(409, "Service already exists for this date and label")
    
    service = SalleService(
        service_date=payload.service_date,
        service_label=payload.service_label,
        reservations={"items": []}
    )
    
    session.add(service)
    session.commit()
    session.refresh(service)
    
    logger.info(f"Created service: {service.service_date} {service.service_label}")
    return SalleServiceRead(**service.model_dump())


@router.get("/services/{service_id}", response_model=SalleServiceRead)
def get_service(service_id: uuid.UUID, session: Session = Depends(get_session)):
    """Get a specific service."""
    service = session.get(SalleService, service_id)
    if not service:
        raise HTTPException(404, "Service not found")
    return SalleServiceRead(**service.model_dump())


@router.delete("/services/{service_id}")
def delete_service(service_id: uuid.UUID, session: Session = Depends(get_session)):
    """Delete a service."""
    service = session.get(SalleService, service_id)
    if not service:
        raise HTTPException(404, "Service not found")
    
    session.delete(service)
    session.commit()
    
    logger.info(f"Deleted service: {service_id}")
    return {"ok": True}


# ---- PDF Import ----

@router.post("/import-pdf")
async def import_pdf(
    file: UploadFile = File(...),
    service_date: Optional[date] = None,
    service_label: str = "brunch",
    session: Session = Depends(get_session)
):
    """
    Import reservations from PDF.
    Creates or updates a service with parsed reservation data.
    """
    logger.info(f"POST /import-pdf -> file={file.filename} date={service_date} label={service_label}")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "File must be a PDF")
    
    # Read PDF
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    blob = await file.read(MAX_FILE_SIZE + 1)
    if len(blob) > MAX_FILE_SIZE:
        raise HTTPException(413, "File size exceeds 10MB limit")
    
    # Use service_date from parameter or extract from PDF filename
    if not service_date:
        # Try to extract date from filename (e.g., "reservations_2026-01-31.pdf")
        import re
        match = re.search(r'(\d{4}-\d{2}-\d{2})', file.filename)
        if match:
            try:
                service_date = date.fromisoformat(match.group(1))
            except ValueError:
                pass
        
        if not service_date:
            raise HTTPException(400, "service_date is required")
    
    # Parse PDF
    try:
        parser = ReservationParser(service_date=service_date, service_label=service_label, debug=True)
        reservations_list = parser.parse_pdf(blob)
        
        logger.info(f"Parsed {len(reservations_list)} reservations, {sum(r['pax'] for r in reservations_list)} covers")
        
    except Exception as e:
        logger.error(f"PDF parsing failed: {str(e)}")
        raise HTTPException(500, f"PDF parsing failed: {str(e)}")
    
    # Find or create service
    service = session.exec(
        select(SalleService).where(
            SalleService.service_date == service_date,
            SalleService.service_label == service_label
        )
    ).first()
    
    if not service:
        service = SalleService(
            service_date=service_date,
            service_label=service_label,
            reservations={"items": reservations_list}
        )
        session.add(service)
        logger.info(f"Created new service: {service_date} {service_label}")
    else:
        service.reservations = {"items": reservations_list}
        logger.info(f"Updated existing service: {service_date} {service_label}")
    
    session.commit()
    session.refresh(service)
    
    return {
        "service_id": str(service.id),
        "service_date": str(service.service_date),
        "service_label": service.service_label,
        "reservations": len(reservations_list),
        "total_covers": sum(r['pax'] for r in reservations_list),
        "items": reservations_list
    }


# ---- Auto-Assign ----

@router.post("/services/{service_id}/auto-assign", response_model=SalleServiceRead)
def auto_assign(service_id: uuid.UUID, session: Session = Depends(get_session)):
    """
    Auto-assign reservations to tables.
    Creates a base plan with fixed tables and generates rect6 tables dynamically.
    """
    logger.info(f"POST /services/{service_id}/auto-assign")
    
    service = session.get(SalleService, service_id)
    if not service:
        raise HTTPException(404, "Service not found")
    
    reservations = service.reservations.get("items", [])
    if not reservations:
        raise HTTPException(400, "No reservations to assign")
    
    # Create base plan if not exists
    if not service.plan_data or not service.plan_data.get("tables"):
        service.plan_data = create_base_plan()
        logger.info("Created base plan with 11 fixed tables")
    
    # Auto-assign
    try:
        updated_plan, assignments = auto_assign_tables(service.plan_data, reservations)
        service.plan_data = updated_plan
        service.assignments = assignments
        
        session.add(service)
        session.commit()
        session.refresh(service)
        
        num_tables = len(updated_plan.get("tables", []))
        num_assigned = len(assignments.get("tables", {}))
        logger.info(f"Auto-assign complete: {num_tables} tables total, {num_assigned} assigned")
        
        return SalleServiceRead(**service.model_dump())
    
    except Exception as e:
        logger.error(f"Auto-assign failed: {str(e)}")
        raise HTTPException(500, f"Auto-assign failed: {str(e)}")
