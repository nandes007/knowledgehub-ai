import uuid

from pydantic import BaseModel, Field

_MAX_MESSAGE_LENGTH = 4000


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE_LENGTH)
    conversation_id: uuid.UUID | None = None
