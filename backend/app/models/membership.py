import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, UniqueConstraint, text
from sqlmodel import Field, Index, SQLModel

from app.models.timestamps import utc_timestamp_field

ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}


class Membership(SQLModel, table=True):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_memberships_role"),
        UniqueConstraint("user_id", "company_id", name="uq_memberships_user_company"),
        Index("idx_memberships_company", "company_id"),
        # Exactly one owner per company; ownership only moves by transfer.
        Index(
            "uq_memberships_company_owner",
            "company_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
            sqlite_where=text("role = 'owner'"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, ondelete="CASCADE")
    company_id: uuid.UUID = Field(foreign_key="companies.id", nullable=False, ondelete="CASCADE")
    role: str = Field(default="member", nullable=False)
    department_id: uuid.UUID | None = Field(
        default=None, foreign_key="departments.id", ondelete="SET NULL", nullable=True
    )
    created_at: datetime = utc_timestamp_field()

    def at_least(self, role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]
