import uuid
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.core.config import settings
from backend.app.models.auth import User, Organization, OrganizationMembership
from backend.app.auth.security import hash_password, verify_password, validate_password_strength
from backend.app.auth.jwt import create_access_token
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    MembershipResponse
)
from backend.app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Authentication & Accounts"])


def _generate_slug(name: str) -> str:
    """Generates an alphanumeric slug with a short random suffix."""
    base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not base_slug:
        base_slug = "org"
    return f"{base_slug}-{uuid.uuid4().hex[:6]}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    """
    Registers a new user:
    - Validates password strength (Argon2id hashing)
    - Creates default organization and assigns ADMIN role to the new user
    - Returns JWT access token and user profile
    """
    validate_password_strength(payload.password)

    # Check for existing email
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists."
        )

    user_id = f"USR-{uuid.uuid4().hex[:12]}"
    user = User(
        id=user_id,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    db.commit()

    # Create default organization for new user
    org_name = payload.organization_name.strip() if payload.organization_name else f"{payload.full_name}'s Org"
    org_id = f"ORG-{uuid.uuid4().hex[:12]}"
    org_slug = _generate_slug(org_name)

    org = Organization(
        id=org_id,
        name=org_name,
        slug=org_slug
    )
    db.add(org)
    db.commit()

    # Assign Admin role in the created organization
    membership_id = f"MEM-{uuid.uuid4().hex[:12]}"
    membership = OrganizationMembership(
        id=membership_id,
        organization_id=org.id,
        user_id=user.id,
        role="ADMIN"
    )
    db.add(membership)
    db.commit()
    db.refresh(user)

    # Seed default microservice topology for the organization
    from backend.app.services.topology_service import topology_service
    topology_service.seed_default_topology_for_org(db, org.id)

    # Audit log
    audit_service.log(
        db=db,
        action="AUTH_REGISTER",
        resource_type="user",
        actor_user_id=user.id,
        organization_id=org.id,
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
        metadata={"email": user.email, "org_name": org.name}
    )

    # Generate JWT
    token_claims = {
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": "ADMIN"
    }
    access_token = create_access_token(token_claims)

    memberships_resp = [
        MembershipResponse(
            id=membership.id,
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            role=membership.role,
            created_at=membership.created_at
        )
    ]

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        memberships=memberships_resp
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Authenticates a user via email and password, returning a signed JWT access token.
    """
    user = db.query(User).filter(User.email == payload.email.lower()).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        audit_service.log(
            db=db,
            action="AUTH_LOGIN_FAILED",
            resource_type="auth",
            actor_user_id=user.id if user else None,
            ip_address=request.client.host if request.client else None,
            metadata={"email": payload.email.lower(), "reason": "Invalid credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated."
        )

    # Determine default organization and role
    primary_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id
    ).first()

    org_id = primary_membership.organization_id if primary_membership else None
    role = primary_membership.role if primary_membership else "VIEWER"

    audit_service.log(
        db=db,
        action="AUTH_LOGIN",
        resource_type="user",
        actor_user_id=user.id,
        organization_id=org_id,
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
        metadata={"email": user.email}
    )

    token_claims = {
        "sub": user.id,
        "email": user.email,
        "org_id": org_id,
        "role": role
    }
    access_token = create_access_token(token_claims)

    memberships_resp = [
        MembershipResponse(
            id=m.id,
            organization_id=m.organization.id,
            organization_name=m.organization.name,
            organization_slug=m.organization.slug,
            role=m.role,
            created_at=m.created_at
        )
        for m in user.memberships
    ]

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        memberships=memberships_resp
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(user: User = Depends(get_current_user)):
    """Returns the profile and organization memberships of the authenticated user."""
    memberships_resp = [
        MembershipResponse(
            id=m.id,
            organization_id=m.organization.id,
            organization_name=m.organization.name,
            organization_slug=m.organization.slug,
            role=m.role,
            created_at=m.created_at
        )
        for m in user.memberships
    ]

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        memberships=memberships_resp
    )
