from typing import List, Union, Callable
from fastapi import Depends, HTTPException, status
from backend.app.models.auth import OrganizationMembership
from backend.app.auth.dependencies import get_current_org_context

# Role privilege hierarchy: ADMIN > ENGINEER > VIEWER
ROLE_HIERARCHY = {
    "ADMIN": 3,
    "ENGINEER": 2,
    "VIEWER": 1,
}


def require_role(min_role: str) -> Callable:
    """
    Dependency factory that verifies the authenticated user possesses
    at least the specified `min_role` within the active organization context.
    """
    min_role_upper = min_role.upper()
    min_level = ROLE_HIERARCHY.get(min_role_upper, 0)

    def role_checker(
        membership: OrganizationMembership = Depends(get_current_org_context)
    ) -> OrganizationMembership:
        user_role = membership.role.upper()
        user_level = ROLE_HIERARCHY.get(user_role, 0)

        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires '{min_role_upper}' role or higher. Your role: '{membership.role}'."
            )
        return membership

    return role_checker


def require_exact_roles(allowed_roles: List[str]) -> Callable:
    """
    Dependency factory requiring user role to match one of the specified allowed roles.
    """
    allowed_upper = [r.upper() for r in allowed_roles]

    def exact_checker(
        membership: OrganizationMembership = Depends(get_current_org_context)
    ) -> OrganizationMembership:
        if membership.role.upper() not in allowed_upper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles: {', '.join(allowed_upper)}. Your role: '{membership.role}'."
            )
        return membership

    return exact_checker


# Convenient pre-configured dependencies for route signatures
require_admin = require_role("ADMIN")
require_engineer = require_role("ENGINEER")
require_viewer = require_role("VIEWER")
