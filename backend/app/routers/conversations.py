import uuid

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.deps import CurrentUserDep, SessionDep
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationRead, ConversationUpdate, MessageRead

router = APIRouter()


@router.post("/conversations", response_model=ConversationRead)
def create_conversation(session: SessionDep, current_user: CurrentUserDep) -> Conversation:
    conversation = Conversation(user_id=current_user.id, company_id=current_user.company_id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


_TITLE_MAX_LENGTH = 48


def _derive_title(message: str) -> str:
    cleaned = message.strip()
    return f"{cleaned[:_TITLE_MAX_LENGTH]}…" if len(cleaned) > _TITLE_MAX_LENGTH else cleaned


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(session: SessionDep, current_user: CurrentUserDep) -> list[Conversation]:
    statement = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = list(session.exec(statement))
    updated = False
    for conv in conversations:
        if conv.title == "New chat":
            first_msg = session.exec(
                select(Message)
                .where(Message.conversation_id == conv.id, Message.role == "user")
                .order_by(Message.created_at.asc())
                .limit(1)
            ).first()
            if first_msg:
                conv.title = _derive_title(first_msg.content)
                session.add(conv)
                updated = True
    if updated:
        session.commit()
    return conversations


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation_id: uuid.UUID, session: SessionDep, current_user: CurrentUserDep) -> list[Message]:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    statement = (
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return list(session.exec(statement))


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    new_title = payload.title.strip()
    if not new_title:
        raise HTTPException(status_code=422, detail="Title cannot be empty")

    conversation.title = new_title
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    session.delete(conversation)
    session.commit()
