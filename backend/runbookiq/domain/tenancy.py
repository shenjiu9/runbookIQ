from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TenantRole = Literal["owner", "admin", "editor", "viewer"]


class TenantUser(BaseModel):
    id: str
    email: str


class OrganizationBranding(BaseModel):
    display_name: str
    logo_url: str | None = None
    primary_color: str = "#0F766E"
    welcome_title: str = "欢迎使用企业知识空间"
    welcome_message: str = "从企业资料中检索答案，并通过原文证据核验每一项结论。"


class Organization(BaseModel):
    id: str
    name: str
    slug: str
    url: str
    branding: OrganizationBranding = Field(
        default_factory=lambda: OrganizationBranding(display_name="企业知识空间")
    )


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
