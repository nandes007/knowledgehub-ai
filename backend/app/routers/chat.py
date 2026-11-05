import json
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.db import get_engine
from app.deps import CurrentUserDep
from app.models.company import Company
from app.models.conversation import Conversation
from app.models.message import Message
from app.rate_limit import limiter
from app.services import attachments
from app.services.llm import LLMProvider, get_llm_provider
from app.services.rag import HistoryTurn, stream_answer
from ingestion.index import VectorStore, get_vector_store

router = APIRouter()

_MAX_MESSAGE_LENGTH = 4000
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
    if conversation is None or conversation.user_id != user_id or (company_id and conversation.company_id != company_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _recent_messages(session: Session, conversation_id: uuid.UUID, limit: int) -> list[Message]:
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list(session.exec(statement))
    rows.reverse()
    return rows


def _history_turn(message: Message) -> HistoryTurn:
    content = message.content
    if message.attachments:
        names = ", ".join(a["filename"] for a in message.attachments)
        content = f"{content}\n[attached: {names}]".strip()
    return {"role": message.role, "content": content, "has_sources": bool(message.sources)}


def _event_stream(
    engine: Engine,
    conversation_id: uuid.UUID,
    pending: dict[uuid.UUID, list[dict]],
    answer,
    llm: LLMProvider,
) -> Iterator[str]:
    """pending: attachments to show the model this turn - the new message's and those
    still inside the history window - keyed by the message they belong to."""
    try:
        extracted: set[uuid.UUID] = set()
        for message_id, entries in pending.items():
            for index, entry in enumerate(entries):
                if attachments.needs_extraction(entry):
                    yield _sse("status", {"text": f"Reading {entry['filename']}…"})
                    entries[index] = attachments.extract(
                        entry, llm, conversation_id=conversation_id, message_id=message_id, index=index
                    )
                    extracted.add(message_id)
                    if entries[index]["truncated"]:
                        yield _sse(
                            "status",
                            {"text": f"{entry['filename']} is long - only the first part was read."},
                        )
        if extracted:
            with Session(engine) as session:
                for message_id in extracted:
                    message = session.get(Message, message_id)
                    message.attachments = [dict(e) for e in pending[message_id]]
                    session.add(message)
                session.commit()
        contents = [attachments.for_llm(e) for entries in pending.values() for e in entries]
    except Exception as exc:
        yield _sse("error", {"message": f"Couldn't read the attachment: {exc}"})
        return

    try:
        tokens, sources, usage = answer(contents)
    except Exception as exc:
        yield _sse("error", {"message": str(exc)})
        return

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
    current_user: CurrentUserDep,
    message: str = Form("", max_length=_MAX_MESSAGE_LENGTH),
    conversation_id: uuid.UUID | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    llm: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    engine: Engine = Depends(get_engine),
) -> StreamingResponse:
    question = message.strip()
    uploads = attachments.read_uploads(files)  # validated before anything is stored
    if not question and not uploads:
        raise HTTPException(status_code=422, detail="Type a message or attach a file.")

    company_name = "KnowledgeHub"
    with Session(engine) as session:
        if current_user.company_id:
            company = session.get(Company, current_user.company_id)
            if company:
                company_name = company.name
        conversation = _get_or_create_conversation(
            session, conversation_id, current_user.id, current_user.company_id
        )
        recent = _recent_messages(session, conversation.id, _HISTORY_LIMIT)
        if conversation.title == "New chat":
            conversation.title = _derive_title(question or uploads[0][0])
        conversation.updated_at = datetime.now(timezone.utc)
        session.add(conversation)
        user_message = Message(conversation_id=conversation.id, role="user", content=question)
        user_message.attachments = attachments.save(conversation.id, user_message.id, uploads) or None
        session.add(user_message)
        session.commit()
        conversation_id = conversation.id
        history = [_history_turn(m) for m in recent]
        # Attachments within the history window are shown again, so follow-ups still see them.
        pending = {m.id: list(m.attachments) for m in [*recent, user_message] if m.attachments}

    def answer(contents):
        return stream_answer(
            question,
            llm=llm,
            vector_store=vector_store,
            company_name=company_name,
            company_id=str(current_user.company_id) if current_user.company_id else None,
            department_id=str(current_user.department_id) if current_user.department_id else None,
            department=current_user.department,
            role=current_user.role,
            history=history,
            attachments=contents,
        )

    return StreamingResponse(
        _event_stream(engine, conversation_id, pending, answer, llm),
        media_type="text/event-stream",
    )
