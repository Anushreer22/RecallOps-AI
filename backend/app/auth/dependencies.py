from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.auth import User, OrganizationMembership
from backend.app.auth.jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts, validates, and decodes the JWT bearer token,
    returning the authenticated User from the database.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token: missing subject claim.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated."
        )

    return user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional authentication: returns the User if a valid token is provided,
    otherwise returns None without raising an exception if no token is present.
    """
    if not token:
        return None
    return get_current_user(token=token, db=db)


def get_current_org_context(
    user: User = Depends(get_current_user),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    db: Session = Depends(get_db)
) -> OrganizationMembership:
    """
    Resolves the caller's active OrganizationMembership:
    1. If X-Organization-Id header is provided, verifies user membership in that org.
    2. If no header is provided, defaults to the user's first/primary organization.
    Raises 403 if the user is not a member of the requested organization or has no orgs.
    """
    if x_organization_id:
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == x_organization_id
        ).first()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: you are not a member of organization '{x_organization_id}'."
            )
        return membership

    # Default to user's first organization
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any organization. Please join or create an organization."
        )

    return membership


def get_optional_org_context(
    user: Optional[User] = Depends(get_optional_current_user),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    db: Session = Depends(get_db)
) -> Optional[OrganizationMembership]:
    """
    Optional organization context for backward-compatible routes.
    """
    if not user:
        return None
    return get_current_org_context(user=user, x_organization_id=x_organization_id, db=db)
