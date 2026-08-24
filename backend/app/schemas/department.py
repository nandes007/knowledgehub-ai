from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1)


class DepartmentRead(BaseModel):
    id: uuid.UUID
    name: str
    company_id: uuid.UUID
    created_at: datetime
