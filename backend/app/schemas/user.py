from datetime import datetime
import uuid

from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    department_id: uuid.UUID
    role: str = "member"


class UserUpdate(BaseModel):
    display_name: str | None = None
    department_id: uuid.UUID | None = None
    role: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    role: str
    approval_status: str
    company_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    created_at: datetime
