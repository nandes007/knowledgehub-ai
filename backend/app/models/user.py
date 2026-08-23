import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Index, SQLModel

from app.models.timestamps import utc_timestamp_field


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('superadmin', 'admin', 'member')", name="ck_users_role"),
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_users_approval_status",
        ),
        Index("idx_users_company", "company_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID | None = Field(
        default=None, foreign_key="companies.id", ondelete="CASCADE", nullable=True
    )
    department_id: uuid.UUID | None = Field(
        default=None, foreign_key="departments.id", ondelete="SET NULL", nullable=True
    )
    email: str = Field(unique=True, index=True, nullable=False)
    password_hash: str
    display_name: str | None = None
    role: str = Field(default="member", nullable=False)
    approval_status: str = Field(default="pending", nullable=False)
    created_at: datetime = utc_timestamp_field()
