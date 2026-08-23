import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from app.models.timestamps import utc_timestamp_field


class Company(SQLModel, table=True):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="ck_companies_status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, nullable=False)
    status: str = Field(default="active", nullable=False)
    created_at: datetime = utc_timestamp_field()
    updated_at: datetime = utc_timestamp_field()
