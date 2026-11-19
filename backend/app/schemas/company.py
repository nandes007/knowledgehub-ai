import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CompanyUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CompanyRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    role: str


class MemberRead(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str | None = None
    role: str
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    joined_at: datetime


class MemberUpdate(BaseModel):
    # Fields left out are unchanged; department_id: null clears the department.
    role: str | None = None
    department_id: uuid.UUID | None = None


class OwnershipTransfer(BaseModel):
    user_id: uuid.UUID


class InviteCreate(BaseModel):
    email: str = Field(min_length=3)
    role: str = "member"
    department_id: uuid.UUID | None = None


class InviteRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    department_id: uuid.UUID | None = None
    expires_at: datetime
    created_at: datetime


class InviteCreated(InviteRead):
    # Shown once: only its hash is stored.
    token: str


class InvitePreview(BaseModel):
    company_name: str
    email: str
    role: str


class InviteAccepted(BaseModel):
    company_slug: str
