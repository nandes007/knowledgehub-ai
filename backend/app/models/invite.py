import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime
from sqlmodel import Field, Index, SQLModel

from app.models.timestamps import utc_timestamp_field


class Invite(SQLModel, table=True):
    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_invites_role"),
        Index("idx_invites_company", "company_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = Field(foreign_key="companies.id", nullable=False, ondelete="CASCADE")
    email: str = Field(nullable=False, index=True)
    role: str = Field(default="member", nullable=False)
    department_id: uuid.UUID | None = Field(
        default=None, foreign_key="departments.id", ondelete="SET NULL", nullable=True
    )
    invited_by: uuid.UUID = Field(foreign_key="users.id", nullable=False, ondelete="CASCADE")
    # Only the hash is stored: the link is shown once, to the inviter.
    token_hash: str = Field(unique=True, index=True, nullable=False)
    expires_at: datetime = Field(nullable=False, sa_type=DateTime(timezone=True))
    accepted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = utc_timestamp_field()
