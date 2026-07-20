import json
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.db import get_engine
from app.deps import CurrentUserDep
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ChatRequest
from app.services.llm import LLMProvider, get_llm_provider
from app.services.rag import stream_answer
from ingestion.index import VectorStore, get_vector_store

router = APIRouter()

_HISTORY_LIMIT = 10  # last N messages included as context for follow-ups


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _get_or_create_conversation(
    session: Session, conversation_id: uuid.UUID | None, user_id: uuid.UUID
) -> Conversation:
    if conversation_id is None:
        conversation = Conversation(user_id=user_id)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return conversation

    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _recent_history(session: Session, conversation_id: uuid.UUID, limit: int) -> list[dict[str, str]]:
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list(session.exec(statement))
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]


def _event_stream(
    engine: Engine,
    conversation_id: uuid.UUID,
    tokens: Iterator[str],
    sources: list[dict],
) -> Iterator[str]:
    answer_parts: list[str] = []
    try:
        for token in tokens:
            answer_parts.append(token)
            yield _sse("token", {"text": token})
    except Exception as exc:
        # Last-resort boundary: headers are already sent, so a mid-stream LLM
        # failure has to surface as an SSE event rather than an HTTP error.
        yield _sse("error", {"message": str(exc)})
        return

    # A fresh session, not the route's SessionDep - the injected dependency
    # is torn down once the route function returns, before this generator's
    # body (which runs while Starlette streams the response) executes.
    with Session(engine) as session:
        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="".join(answer_parts),
            sources=sources,
        )
        session.add(message)
        session.commit()
        session.refresh(message)
        message_id = message.id

    yield _sse(
        "done",
        {"sources": sources, "message_id": str(message_id), "conversation_id": str(conversation_id)},
    )


@router.post("/chat")
def chat(
    request: ChatRequest,
    current_user: CurrentUserDep,
    llm: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    engine: Engine = Depends(get_engine),
) -> StreamingResponse:
    with Session(engine) as session:
        conversation = _get_or_create_conversation(session, request.conversation_id, current_user.id)
        history = _recent_history(session, conversation.id, _HISTORY_LIMIT)
        session.add(Message(conversation_id=conversation.id, role="user", content=request.message))
        session.commit()
        conversation_id = conversation.id

    tokens, sources = stream_answer(
        request.message,
        user_id=str(current_user.id),
        llm=llm,
        vector_store=vector_store,
        history=history,
    )
    return StreamingResponse(
        _event_stream(engine, conversation_id, tokens, sources),
        media_type="text/event-stream",
    )
