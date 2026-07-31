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
