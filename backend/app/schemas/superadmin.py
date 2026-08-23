from datetime import datetime
import uuid

from pydantic import BaseModel


class SuperadminUserRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    role: str
    approval_status: str
    company_id: uuid.UUID | None = None
    company_name: str | None = None
    department_id: uuid.UUID | None = None
    created_at: datetime


class SuperadminCompanyRead(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
