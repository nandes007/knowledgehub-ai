import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, Index, SQLModel


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    __table_args__ = (Index("idx_conversations_user", "user_id", "updated_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, ondelete="CASCADE")
    title: str = Field(default="New chat", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
