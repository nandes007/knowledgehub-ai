import uuid
from datetime import datetime

from sqlmodel import Field, Index, SQLModel

from app.models.timestamps import utc_timestamp_field


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    __table_args__ = (Index("idx_conversations_user", "user_id", "updated_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, ondelete="CASCADE")
    title: str = Field(default="New chat", nullable=False)
    created_at: datetime = utc_timestamp_field()
    updated_at: datetime = utc_timestamp_field()
