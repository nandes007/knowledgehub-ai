from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: str
    company_id: uuid.UUID
    uploaded_by: uuid.UUID
    department_id: uuid.UUID | None = None
    visibility: str


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: str
    company_id: uuid.UUID
    uploaded_by: uuid.UUID
    department_id: uuid.UUID | None = None
    visibility: str
    chunk_count: int | None = None
    progress: int = 0
    error_message: str | None = None
    created_at: datetime
