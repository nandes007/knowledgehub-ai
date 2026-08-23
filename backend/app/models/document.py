import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Index, SQLModel

from app.models.timestamps import utc_timestamp_field


class Document(SQLModel, table=True):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN ('processing', 'ready', 'failed')", name="ck_documents_status"),
        CheckConstraint("visibility IN ('company', 'department')", name="ck_documents_visibility"),
        Index("idx_documents_company", "company_id", "created_at"),
        Index("idx_documents_uploaded_by", "uploaded_by", "created_at"),
        Index("idx_documents_status", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = Field(foreign_key="companies.id", nullable=False, ondelete="CASCADE")
    uploaded_by: uuid.UUID = Field(foreign_key="users.id", nullable=False, ondelete="CASCADE")
    filename: str
    content_type: str
    file_path: str
    file_hash: str
    status: str = Field(default="processing", nullable=False)
    error_message: str | None = None
    doc_type: str = Field(default="general", nullable=False)
    department_id: uuid.UUID | None = Field(
        default=None, foreign_key="departments.id", ondelete="SET NULL", nullable=True
    )
    visibility: str = Field(default="company", nullable=False)
    chunk_count: int | None = None
    created_at: datetime = utc_timestamp_field()
    updated_at: datetime = utc_timestamp_field()

    def __init__(self, **data):
        if "user_id" in data and "uploaded_by" not in data:
            data["uploaded_by"] = data.pop("user_id")
        super().__init__(**data)

    @property
    def user_id(self) -> uuid.UUID:
        return self.uploaded_by

    @user_id.setter
    def user_id(self, val: uuid.UUID) -> None:
        self.uploaded_by = val
