import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.deps import CurrentUserDep, SessionDep
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationRead, MessageRead

router = APIRouter()


@router.post("/conversations", response_model=ConversationRead)
def create_conversation(session: SessionDep, current_user: CurrentUserDep) -> Conversation:
    conversation = Conversation(user_id=current_user.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(session: SessionDep, current_user: CurrentUserDep) -> list[Conversation]:
    statement = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(session.exec(statement))


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation_id: uuid.UUID, session: SessionDep, current_user: CurrentUserDep) -> list[Message]:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    statement = (
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return list(session.exec(statement))
