import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Index, SQLModel

from app.models.timestamps import utc_timestamp_field


class Department(SQLModel, table=True):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_departments_company_name"),
        Index("idx_departments_company", "company_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = Field(foreign_key="companies.id", nullable=False, ondelete="CASCADE")
    name: str = Field(nullable=False)
    created_at: datetime = utc_timestamp_field()
    updated_at: datetime = utc_timestamp_field()
