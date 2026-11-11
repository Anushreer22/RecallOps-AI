import uuid
import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.auth import Project, OrganizationMembership
from backend.app.auth.permissions import require_engineer, require_viewer
from backend.app.auth.schemas import ProjectCreate, ProjectResponse
from backend.app.services.audit_service import audit_service

router = APIRouter(prefix="/projects", tags=["Projects"])


def _generate_slug(name: str) -> str:
    base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not base_slug:
        base_slug = "proj"
    return f"{base_slug}-{uuid.uuid4().hex[:6]}"


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    membership: OrganizationMembership = Depends(require_engineer),
    db: Session = Depends(get_db)
):
    """Creates a new project scoped to the caller's organization. Requires ENGINEER or ADMIN role."""
    if membership.role.upper() not in ["ADMIN", "ENGINEER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires 'ENGINEER' role or higher. Your role: '{membership.role}'."
        )

    slug = payload.slug.strip().lower() if payload.slug else _generate_slug(payload.name)

    existing = db.query(Project).filter(
        Project.organization_id == membership.organization_id,
        Project.slug == slug
    ).first()
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"

    project = Project(
        id=f"PRJ-{uuid.uuid4().hex[:12]}",
        organization_id=membership.organization_id,
        name=payload.name.strip(),
        slug=slug,
        description=payload.description
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    audit_service.log(
        db=db,
        action="PROJECT_CREATE",
        resource_type="project",
        actor_user_id=membership.user_id,
        organization_id=membership.organization_id,
        resource_id=project.id,
        metadata={"name": project.name, "slug": project.slug}
    )

    return project


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Lists all projects belonging to the caller's organization. Requires VIEWER or higher."""
    return db.query(Project).filter(
        Project.organization_id == membership.organization_id
    ).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    membership: OrganizationMembership = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Retrieves project details scoped to the caller's organization."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.organization_id == membership.organization_id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found or access denied."
        )

    return project
