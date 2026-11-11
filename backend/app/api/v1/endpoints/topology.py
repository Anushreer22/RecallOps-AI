from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.auth import ServiceDependency, OrganizationMembership
from backend.app.auth.permissions import require_engineer, require_viewer
from backend.app.auth.schemas import DependencyCreate, DependencyResponse
from backend.app.schemas.incident import BlastRadiusSummary
from backend.app.services.audit_service import audit_service
from backend.app.services.topology_service import topology_service

router = APIRouter(prefix="/topology", tags=["Topology"])


@router.post("/dependencies", response_model=DependencyResponse, status_code=status.HTTP_201_CREATED)
def create_dependency(
    payload: DependencyCreate,
    membership: OrganizationMembership = Depends(require_engineer),
    db: Session = Depends(get_db)
):
    """Registers a persistent dependency between two services. Requires ENGINEER or higher."""
    if membership.role.upper() not in ["ADMIN", "ENGINEER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires 'ENGINEER' role or higher. Your role: '{membership.role}'."
        )

    dep_record = topology_service.register_dependency(
        source_service=payload.source_service,
        target_service=payload.target_service,
        tier=payload.tier or "TIER_1",
        owner=payload.owner or "Engineering",
        organization_id=membership.organization_id,
        project_id=payload.project_id,
        dependency_type=payload.dependency_type,
        db=db
    )

    audit_service.log(
        db=db,
        action="DEPENDENCY_ADD",
        resource_type="service_dependency",
        actor_user_id=membership.user_id,
        organization_id=membership.organization_id,
        resource_id=str(dep_record.id),
        metadata={
            "source": payload.source_service,
            "target": payload.target_service,
            "type": payload.dependency_type
        }
    )

    return dep_record


@router.delete("/dependencies/{dependency_id}")
def delete_dependency(
    dependency_id: int,
    membership: OrganizationMembership = Depends(require_engineer),
    db: Session = Depends(get_db)
):
    """Deletes a service dependency. Requires ENGINEER or higher."""
    if membership.role.upper() not in ["ADMIN", "ENGINEER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires 'ENGINEER' role or higher. Your role: '{membership.role}'."
        )

    dep = db.query(ServiceDependency).filter(
        ServiceDependency.id == dependency_id,
        ServiceDependency.organization_id == membership.organization_id
    ).first()

    if not dep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dependency with ID {dependency_id} not found in this organization."
        )

    src = dep.source_service
    tgt = dep.target_service

    success = topology_service.remove_dependency(
        dependency_id=dependency_id,
        organization_id=membership.organization_id,
        db=db
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to delete dependency.")

    audit_service.log(
        db=db,
        action="DEPENDENCY_DELETE",
        resource_type="service_dependency",
        actor_user_id=membership.user_id,
        organization_id=membership.organization_id,
        resource_id=str(dependency_id),
        metadata={"source": src, "target": tgt}
    )

    return {"status": "deleted", "id": dependency_id}


@router.get("/dependencies", response_model=List[DependencyResponse])
def list_dependencies(
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Lists all registered service dependencies for the organization. Requires VIEWER or higher."""
    return db.query(ServiceDependency).filter(
        ServiceDependency.organization_id == membership.organization_id
    ).all()


@router.get("/blast-radius", response_model=BlastRadiusSummary)
def get_topology_blast_radius(
    service: str = Query(..., description="Target service to evaluate downstream impact for"),
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Computes downstream blast radius for a service in the organization."""
    data = topology_service.get_blast_radius(
        service,
        organization_id=membership.organization_id,
        db=db
    )
    return BlastRadiusSummary(**data)


@router.get("/cycles")
def detect_topology_cycles(
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Detects cyclic dependencies in the organization's microservice architecture graph."""
    cycles = topology_service.check_for_cycles(
        organization_id=membership.organization_id,
        db=db
    )
    return {
        "organization_id": membership.organization_id,
        "has_cycles": len(cycles) > 0,
        "cycle_count": len(cycles),
        "cycles": cycles
    }
