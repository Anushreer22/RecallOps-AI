from typing import List, Optional, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.ai.schemas import (
    InvestigationResponse,
    InvestigationFeedbackCreate,
    InvestigationFeedbackResponse,
)
from backend.app.services.investigation_service import investigation_service
from backend.app.services.audit_service import audit_service
from backend.app.models.auth import OrganizationMembership
from backend.app.auth.dependencies import get_optional_org_context

router = APIRouter(tags=["AI Investigation Engine"])


def _resolve_org(org_context: Any) -> Optional[OrganizationMembership]:
    return org_context if isinstance(org_context, OrganizationMembership) else None


@router.post(
    "/incidents/{incident_id}/investigate",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK
)
def run_incident_investigation(
    incident_id: str,
    provider: Optional[str] = Query(None, description="Optional LLM provider override (e.g. openai, mock)"),
    db: Session = Depends(get_db),
    org_context: Optional[OrganizationMembership] = Depends(get_optional_org_context)
):
    """
    Triggers a structured AI incident investigation using the configured LLM provider.
    Gathers multi-modal evidence, validates grounding against citations, and persists the report.
    """
    org = _resolve_org(org_context)
    if org and org.role == "VIEWER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires 'ENGINEER' role or higher. Your role: 'VIEWER'."
        )

    # Verify incident tenant isolation
    from backend.app.repositories.incident_repository import IncidentRepository
    repo = IncidentRepository(db)
    incident = repo.get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
    if org and incident.organization_id and incident.organization_id != org.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")

    res = investigation_service.investigate_incident(
        incident_id=incident_id,
        db=db,
        provider_name=provider
    )

    if org:
        audit_service.log(
            db=db,
            action="INVESTIGATION_RUN",
            resource_type="investigation",
            actor_user_id=org.user_id,
            organization_id=org.organization_id,
            resource_id=res.id,
            metadata={"incident_id": incident_id, "provider": res.provider}
        )

    return res


@router.get(
    "/incidents/{incident_id}/investigations",
    response_model=List[InvestigationResponse]
)
def list_incident_investigations(
    incident_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    org_context: Optional[OrganizationMembership] = Depends(get_optional_org_context)
):
    """
    Lists historical investigation reports for a specific incident.
    """
    org = _resolve_org(org_context)
    from backend.app.repositories.incident_repository import IncidentRepository
    repo = IncidentRepository(db)
    incident = repo.get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
    if org and incident.organization_id and incident.organization_id != org.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")

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
    db: Session = Depends(get_db),
    org_context: Optional[OrganizationMembership] = Depends(get_optional_org_context)
):
    """
    Fetches details of a specific investigation report by ID.
    """
    org = _resolve_org(org_context)
    res = investigation_service.get_investigation(
        investigation_id=investigation_id,
        db=db
    )
    from backend.app.repositories.investigation_repository import InvestigationRepository
    inv_repo = InvestigationRepository(db)
    inv = inv_repo.get_by_id(investigation_id)
    if org and inv and inv.organization_id and inv.organization_id != org.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")

    return res


@router.post(
    "/investigations/{investigation_id}/feedback",
    response_model=InvestigationFeedbackResponse,
    status_code=status.HTTP_200_OK
)
def submit_investigation_feedback(
    investigation_id: str,
    feedback: InvestigationFeedbackCreate,
    db: Session = Depends(get_db),
    org_context: Optional[OrganizationMembership] = Depends(get_optional_org_context)
):
    """
    Allows an on-call SRE to approve or reject an AI investigation.
    Approved resolutions resolve the incident and index verified root causes into episodic memory.
    Rejected resolutions do NOT touch episodic memory.
    """
    org = _resolve_org(org_context)
    if org and org.role == "VIEWER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires 'ENGINEER' role or higher. Your role: 'VIEWER'."
        )

    from backend.app.repositories.investigation_repository import InvestigationRepository
    inv_repo = InvestigationRepository(db)
    inv = inv_repo.get_by_id(investigation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")
    if org and inv.organization_id and inv.organization_id != org.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")

    res = investigation_service.handle_feedback(
        investigation_id=investigation_id,
        feedback=feedback,
        db=db
    )

    if org:
        audit_service.log(
            db=db,
            action="INVESTIGATION_FEEDBACK",
            resource_type="investigation",
            actor_user_id=org.user_id,
            organization_id=org.organization_id,
            resource_id=investigation_id,
            metadata={"approved": feedback.approved, "feedback": feedback.feedback_notes}
        )

    return res
