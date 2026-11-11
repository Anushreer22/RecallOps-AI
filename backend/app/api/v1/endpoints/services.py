import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.auth import Service, ServiceDependency, OrganizationMembership
from backend.app.auth.permissions import require_engineer, require_viewer
from backend.app.auth.schemas import (
    ServiceCreate,
    ServiceResponse,
    DependencyCreate,
    DependencyResponse
)
from backend.app.schemas.incident import BlastRadiusSummary
from backend.app.services.audit_service import audit_service
from backend.app.services.topology_service import topology_service

router = APIRouter(prefix="/services", tags=["Services"])


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    membership: OrganizationMembership = Depends(require_engineer),
    db: Session = Depends(get_db)
):
    """Registers a new service in the caller's organization. Requires ENGINEER or ADMIN role."""
    if membership.role.upper() not in ["ADMIN", "ENGINEER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires 'ENGINEER' role or higher. Your role: '{membership.role}'."
        )

    existing = db.query(Service).filter(
        Service.organization_id == membership.organization_id,
        Service.name == payload.name.strip()
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service with name '{payload.name}' already exists in this organization."
        )

    svc_id = f"SVC-{uuid.uuid4().hex[:12]}"
    service = Service(
        id=svc_id,
        organization_id=membership.organization_id,
        project_id=payload.project_id,
        name=payload.name.strip(),
        tier=payload.tier.upper(),
        owner=payload.owner.strip(),
        description=payload.description
    )
    db.add(service)
    db.commit()
    db.refresh(service)

    # Update in-memory graph
    active_graph = topology_service.get_graph(membership.organization_id, db=db)
    active_graph.add_service(service.name, tier=service.tier, owner=service.owner)

    audit_service.log(
        db=db,
        action="SERVICE_CREATE",
        resource_type="service",
        actor_user_id=membership.user_id,
        organization_id=membership.organization_id,
        resource_id=service.id,
        metadata={"name": service.name, "tier": service.tier, "owner": service.owner}
    )

    return service


@router.get("", response_model=List[ServiceResponse])
def list_services(
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Lists all registered services for the caller's organization. Requires VIEWER or higher."""
    return db.query(Service).filter(
        Service.organization_id == membership.organization_id
    ).all()


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: str,
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Retrieves service details scoped to the caller's organization."""
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.organization_id == membership.organization_id
    ).first()

    if not service:
        # Also check by name if service_id matches service name
        service = db.query(Service).filter(
            Service.name == service_id,
            Service.organization_id == membership.organization_id
        ).first()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found in this organization."
        )

    return service


@router.post("/{service_id}/dependencies", response_model=DependencyResponse, status_code=status.HTTP_201_CREATED)
def add_service_dependency(
    service_id: str,
    payload: DependencyCreate,
    membership: OrganizationMembership = Depends(require_engineer),
    db: Session = Depends(get_db)
):
    """Adds a dependency for service_id. Requires ENGINEER or higher."""
    if membership.role.upper() not in ["ADMIN", "ENGINEER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires 'ENGINEER' role or higher. Your role: '{membership.role}'."
        )

    # Find service
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.organization_id == membership.organization_id
    ).first()

    source_name = service.name if service else service_id

    dep_record = topology_service.register_dependency(
        source_service=source_name,
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
        resource_id=str(dep_record.id) if dep_record else None,
        metadata={"source": source_name, "target": payload.target_service}
    )

    return dep_record


@router.get("/{service_id}/dependencies", response_model=List[DependencyResponse])
def get_service_dependencies(
    service_id: str,
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Lists dependencies where service_id is either source or target."""
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.organization_id == membership.organization_id
    ).first()

    svc_name = service.name if service else service_id

    deps = db.query(ServiceDependency).filter(
        ServiceDependency.organization_id == membership.organization_id,
        (ServiceDependency.source_service == svc_name) | (ServiceDependency.target_service == svc_name)
    ).all()

    return deps


@router.get("/{service_id}/blast-radius", response_model=BlastRadiusSummary)
def get_service_blast_radius(
    service_id: str,
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Computes downstream blast radius for service_id in the organization."""
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.organization_id == membership.organization_id
    ).first()

    svc_name = service.name if service else service_id
    data = topology_service.get_blast_radius(svc_name, organization_id=membership.organization_id, db=db)
    return BlastRadiusSummary(**data)
