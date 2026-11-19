import uuid

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str | None = None
    # From an invite link: joins that company and works even when signup is closed.
    invite_token: str | None = None


class RegisterResponse(BaseModel):
    message: str
    approval_status: str
    company_slug: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MyCompany(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    role: str
    department_id: uuid.UUID | None = None
    department_name: str | None = None


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    is_instance_admin: bool
    approval_status: str
    companies: list[MyCompany]
