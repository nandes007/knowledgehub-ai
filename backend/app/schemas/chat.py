from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class Source(BaseModel):
    document_id: str
    filename: str
    chunk_preview: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
