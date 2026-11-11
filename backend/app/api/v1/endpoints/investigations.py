from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.ai.schemas import (
    InvestigationResponse,
    InvestigationFeedbackCreate,
    InvestigationFeedbackResponse,
)
from backend.app.services.investigation_service import investigation_service

router = APIRouter(tags=["AI Investigation Engine"])


@router.post(
    "/incidents/{incident_id}/investigate",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK
)
def run_incident_investigation(
    incident_id: str,
    provider: Optional[str] = Query(None, description="Optional LLM provider override (e.g. openai, mock)"),
    db: Session = Depends(get_db)
):
    """
    Triggers a structured AI incident investigation using the configured LLM provider.
    Gathers multi-modal evidence, validates grounding against citations, and persists the report.
    """
    return investigation_service.investigate_incident(
        incident_id=incident_id,
        db=db,
        provider_name=provider
    )


@router.get(
    "/incidents/{incident_id}/investigations",
    response_model=List[InvestigationResponse]
)
def list_incident_investigations(
    incident_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Lists historical investigation reports for a specific incident.
    """
    return investigation_service.list_investigations(
        incident_id=incident_id,
        db=db,
        skip=skip,
        limit=limit
    )


@router.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationResponse
)
def get_investigation_details(
    investigation_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetches details of a specific investigation report by ID.
    """
    return investigation_service.get_investigation(
        investigation_id=investigation_id,
        db=db
    )


@router.post(
    "/investigations/{investigation_id}/feedback",
    response_model=InvestigationFeedbackResponse,
    status_code=status.HTTP_200_OK
)
def submit_investigation_feedback(
    investigation_id: str,
    feedback: InvestigationFeedbackCreate,
    db: Session = Depends(get_db)
):
    """
    Allows an on-call SRE to approve or reject an AI investigation.
    Approved resolutions resolve the incident and index verified root causes into episodic memory.
    Rejected resolutions do NOT touch episodic memory.
    """
    return investigation_service.handle_feedback(
        investigation_id=investigation_id,
        feedback=feedback,
        db=db
    )
