import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Index, SQLModel

from app.models.timestamps import utc_timestamp_field


class Document(SQLModel, table=True):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN ('processing', 'ready', 'failed')", name="ck_documents_status"),
        Index("idx_documents_user", "user_id", "created_at"),
        Index("idx_documents_status", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, ondelete="CASCADE")
    filename: str
    content_type: str
    file_path: str
    file_hash: str
    status: str = Field(default="processing", nullable=False)
    error_message: str | None = None
    doc_type: str = Field(default="general", nullable=False)
    department: str | None = None
    chunk_count: int | None = None
    created_at: datetime = utc_timestamp_field()
    updated_at: datetime = utc_timestamp_field()
