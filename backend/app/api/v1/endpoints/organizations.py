import uuid
import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.auth import User, Organization, OrganizationMembership
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.schemas import (
    OrganizationCreate,
    OrganizationResponse,
    MemberAddRequest,
    MemberUpdateRequest,
    MemberDetailResponse
)
from backend.app.services.audit_service import audit_service
from backend.app.services.topology_service import topology_service

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _generate_slug(name: str) -> str:
    base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not base_slug:
        base_slug = "org"
    return f"{base_slug}-{uuid.uuid4().hex[:6]}"


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new organization and grants the creator ADMIN privileges."""
    org_id = f"ORG-{uuid.uuid4().hex[:12]}"
    slug = payload.slug.strip().lower() if payload.slug else _generate_slug(payload.name)

    existing = db.query(Organization).filter(Organization.slug == slug).first()
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"

    org = Organization(
        id=org_id,
        name=payload.name.strip(),
        slug=slug
    )
    db.add(org)
    db.commit()

    # Assign Admin membership
    membership = OrganizationMembership(
        id=f"MEM-{uuid.uuid4().hex[:12]}",
        organization_id=org.id,
        user_id=user.id,
        role="ADMIN"
    )
    db.add(membership)
    db.commit()
    db.refresh(org)

    # Seed default microservice topology
    topology_service.seed_default_topology_for_org(db, org.id)

    audit_service.log(
        db=db,
        action="ORGANIZATION_CREATE",
        resource_type="organization",
        actor_user_id=user.id,
        organization_id=org.id,
        resource_id=org.id,
        metadata={"name": org.name, "slug": org.slug}
    )

    return org


@router.get("", response_model=List[OrganizationResponse])
def list_user_organizations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all organizations where the authenticated user holds membership."""
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id
    ).all()
    org_ids = [m.organization_id for m in memberships]
    return db.query(Organization).filter(Organization.id.in_(org_ids)).all()


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves organization details if the user is a member."""
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found or access denied."
        )

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org


@router.get("/{org_id}/members", response_model=List[MemberDetailResponse])
def list_organization_members(
    org_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists members of the organization. Requires caller to be a member."""
    caller_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not caller_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found or access denied."
        )

    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id
    ).all()

    return [
        MemberDetailResponse(
            id=m.id,
            user_id=m.user.id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
            created_at=m.created_at
        )
        for m in memberships
    ]


@router.post("/{org_id}/members", response_model=MemberDetailResponse, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    org_id: str,
    payload: MemberAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Adds a new member to the organization. Requires ADMIN role."""
    caller_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user.id
    ).first()

    if not caller_membership or caller_membership.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Organization Admins can add members."
        )

    target_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{payload.email}' does not exist."
        )

    existing_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == target_user.id
    ).first()
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization."
        )

    membership = OrganizationMembership(
        id=f"MEM-{uuid.uuid4().hex[:12]}",
        organization_id=org_id,
        user_id=target_user.id,
        role=payload.role.upper()
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    audit_service.log(
        db=db,
        action="MEMBER_ADD",
        resource_type="organization_membership",
        actor_user_id=user.id,
        organization_id=org_id,
        resource_id=membership.id,
        metadata={"added_user_id": target_user.id, "email": target_user.email, "role": membership.role}
    )

    return MemberDetailResponse(
        id=membership.id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=membership.role,
        created_at=membership.created_at
    )


@router.put("/{org_id}/members/{target_user_id}", response_model=MemberDetailResponse)
def update_member_role(
    org_id: str,
    target_user_id: str,
    payload: MemberUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates an organization member's role. Requires ADMIN role."""
    caller_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user.id
    ).first()

    if not caller_membership or caller_membership.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Organization Admins can modify member roles."
        )

    target_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == target_user_id
    ).first()

    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user membership not found in this organization."
        )

    old_role = target_membership.role
    target_membership.role = payload.role.upper()
    db.commit()
    db.refresh(target_membership)

    audit_service.log(
        db=db,
        action="MEMBER_ROLE_UPDATE",
        resource_type="organization_membership",
        actor_user_id=user.id,
        organization_id=org_id,
        resource_id=target_membership.id,
        metadata={"target_user_id": target_user_id, "old_role": old_role, "new_role": target_membership.role}
    )

    return MemberDetailResponse(
        id=target_membership.id,
        user_id=target_membership.user.id,
        email=target_membership.user.email,
        full_name=target_membership.user.full_name,
        role=target_membership.role,
        created_at=target_membership.created_at
    )
