import uuid

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=1)
    email: str
    password: str = Field(min_length=8)
    display_name: str | None = None


class RegisterResponse(BaseModel):
    message: str = "Registration pending approval"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    email: str
    display_name: str | None
    role: str
    approval_status: str
    company_id: uuid.UUID | None = None
    company_name: str | None = None
    department_id: uuid.UUID | None = None
    department_name: str | None = None
