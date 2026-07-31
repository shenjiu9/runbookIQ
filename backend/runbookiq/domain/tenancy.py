from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TenantRole = Literal["owner", "admin", "editor", "viewer"]


class TenantUser(BaseModel):
    id: str
    email: str


class Organization(BaseModel):
    id: str
    name: str
    slug: str
    url: str


class TenantContext(BaseModel):
    user: TenantUser
    organization: Organization
    role: TenantRole


class TenantSession(BaseModel):
    context: TenantContext
    token: str
    csrf_token: str


class OrganizationMember(BaseModel):
    user_id: str
    email: str
    role: TenantRole
    joined_at: datetime


class TenantInvitation(BaseModel):
    id: str
    email: str
    role: TenantRole
    expires_at: datetime
    created_at: datetime


class CreatedTenantInvitation(TenantInvitation):
    token: str
    accept_url: str


class TenantInvitationPreview(BaseModel):
    email: str
    role: TenantRole
    organization_name: str
    organization_url: str
    expires_at: datetime
