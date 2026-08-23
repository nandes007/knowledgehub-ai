import json
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import Engine
from sqlmodel import Session, select

from datetime import datetime, timezone

from app.db import get_engine
from app.deps import CurrentUserDep
from app.models.conversation import Conversation
from app.models.message import Message
from app.rate_limit import limiter
from app.schemas.chat import ChatRequest
from app.services.llm import LLMProvider, TokenUsage, get_llm_provider
from app.services.rag import stream_answer
from ingestion.index import VectorStore, get_vector_store

router = APIRouter()

_HISTORY_LIMIT = 10  # last N messages included as context for follow-ups
_TITLE_MAX_LENGTH = 48


def _derive_title(message: str) -> str:
    cleaned = message.strip()
    return f"{cleaned[:_TITLE_MAX_LENGTH]}…" if len(cleaned) > _TITLE_MAX_LENGTH else cleaned


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _get_or_create_conversation(
    session: Session,
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID,
    company_id: uuid.UUID | None = None,
) -> Conversation:
    if conversation_id is None:
        conversation = Conversation(user_id=user_id, company_id=company_id)
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
    usage: TokenUsage,
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

    token_count = None
    if usage.prompt_tokens is not None and usage.completion_tokens is not None:
        token_count = usage.prompt_tokens + usage.completion_tokens

    # A fresh session, not the route's SessionDep - the injected dependency
    # is torn down once the route function returns, before this generator's
    # body (which runs while Starlette streams the response) executes.
    with Session(engine) as session:
        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="".join(answer_parts),
            sources=sources,
            token_count=token_count,
        )
        session.add(message)
        conversation = session.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.now(timezone.utc)
            session.add(conversation)
        session.commit()
        session.refresh(message)
        message_id = message.id

    yield _sse(
        "done",
        {"sources": sources, "message_id": str(message_id), "conversation_id": str(conversation_id)},
    )


@router.post("/chat")
@limiter.limit("20/minute")
def chat(
    request: Request,
    payload: ChatRequest,
    current_user: CurrentUserDep,
    llm: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    engine: Engine = Depends(get_engine),
) -> StreamingResponse:
    with Session(engine) as session:
        conversation = _get_or_create_conversation(
            session, payload.conversation_id, current_user.id, current_user.company_id
        )
        history = _recent_history(session, conversation.id, _HISTORY_LIMIT)
        if conversation.title == "New chat":
            conversation.title = _derive_title(payload.message)
        conversation.updated_at = datetime.now(timezone.utc)
        session.add(conversation)
        session.add(Message(conversation_id=conversation.id, role="user", content=payload.message))
        session.commit()
        conversation_id = conversation.id

    tokens, sources, usage = stream_answer(
        payload.message,
        llm=llm,
        vector_store=vector_store,
        department=current_user.department,
        role=current_user.role,
        history=history,
    )
    return StreamingResponse(
        _event_stream(engine, conversation_id, tokens, sources, usage),
        media_type="text/event-stream",
    )
