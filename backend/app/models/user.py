import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from app.models.timestamps import utc_timestamp_field


class User(SQLModel, table=True):
    """A global account. What it may do inside a company lives on its Membership."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_users_approval_status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    password_hash: str
    display_name: str | None = None
    # Platform-only: manages companies and users, grants nothing inside a company.
    is_instance_admin: bool = Field(default=False, nullable=False)
    # Only meaningful when SIGNUP_MODE=approval.
    approval_status: str = Field(default="approved", nullable=False)
    created_at: datetime = utc_timestamp_field()
