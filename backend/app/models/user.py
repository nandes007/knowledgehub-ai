import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.timestamps import utc_timestamp_field


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    password_hash: str
    display_name: str | None = None
    role: str = Field(default="member", nullable=False)
    created_at: datetime = utc_timestamp_field()
