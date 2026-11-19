import uuid
from datetime import datetime

from pydantic import BaseModel


class InstanceUserCompany(BaseModel):
    name: str
    slug: str
    role: str


class InstanceUserRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    is_instance_admin: bool
    approval_status: str
    companies: list[InstanceUserCompany]
    created_at: datetime


class InstanceCompanyRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    member_count: int
    created_at: datetime
    updated_at: datetime
