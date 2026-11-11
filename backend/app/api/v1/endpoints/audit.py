from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.auth import OrganizationMembership
from backend.app.auth.permissions import require_viewer
from backend.app.auth.schemas import AuditLogResponse
from backend.app.services.audit_service import audit_service

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by audit action (e.g. AUTH_LOGIN, DEPENDENCY_ADD)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type (e.g. user, service)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """
    Retrieves security and operational audit logs scoped to the caller's organization.
    Requires VIEWER or higher role.
    """
    action_str = action if isinstance(action, str) else None
    res_str = resource_type if isinstance(resource_type, str) else None
    limit_int = limit if isinstance(limit, int) else 50
    offset_int = offset if isinstance(offset, int) else 0

    logs = audit_service.list_logs(
        db=db,
        organization_id=membership.organization_id,
        action=action_str,
        resource_type=res_str,
        limit=limit_int,
        offset=offset_int
    )
    return logs
