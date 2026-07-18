import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Index, SQLModel


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        Index("idx_messages_conversation", "conversation_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id", nullable=False, ondelete="CASCADE")
    role: str
    content: str
    sources: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONB))
    token_count: int | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
