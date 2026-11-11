from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# ============================================================================
# Auth & User Schemas
# ============================================================================

class UserRegisterRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, description="User valid email address")
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1)
    organization_name: Optional[str] = Field(None, description="Optional organization name. Defaults to '{full_name}'s Org'.")


class UserLoginRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN)
    password: str


class MembershipResponse(BaseModel):
    id: str
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    memberships: List[MembershipResponse] = []

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


# ============================================================================
# Organization Schemas
# ============================================================================

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    slug: Optional[str] = Field(None, max_length=128)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_at: datetime

    class Config:
        from_attributes = True


class MemberAddRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN)
    role: str = Field("ENGINEER", pattern="^(ADMIN|ENGINEER|VIEWER)$")


class MemberUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(ADMIN|ENGINEER|VIEWER)$")


class MemberDetailResponse(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Project Schemas
# ============================================================================

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    slug: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Service & Topology Schemas
# ============================================================================

class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    tier: str = Field("TIER_1", pattern="^(TIER_0|TIER_1|TIER_2|TIER_3)$")
    owner: str = Field("Engineering", max_length=128)
    project_id: Optional[str] = None
    description: Optional[str] = None


class ServiceResponse(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    name: str
    tier: str
    owner: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DependencyCreate(BaseModel):
    source_service: str = Field(..., min_length=1, max_length=128)
    target_service: str = Field(..., min_length=1, max_length=128)
    dependency_type: str = Field("DIRECT", pattern="^(DIRECT|HARD|SOFT|ASYNC)$")
    tier: Optional[str] = "TIER_1"
    owner: Optional[str] = "Engineering"
    project_id: Optional[str] = None


class DependencyResponse(BaseModel):
    id: int
    organization_id: Optional[str] = None
    project_id: Optional[str] = None
    source_service: str
    target_service: str
    dependency_type: str
    tier: Optional[str] = "TIER_1"
    owner: Optional[str] = "Engineering"
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Audit Log Schemas
# ============================================================================

class AuditLogResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
