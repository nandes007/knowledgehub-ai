import uuid
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import select

from app.deps import CurrentUserDep, SessionDep
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationRead, ConversationUpdate, MessageRead
from app.services import attachments, storage
from ingestion.pipeline import delete_files

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
    conditions = [Conversation.user_id == current_user.id]
    if current_user.company_id:
        conditions.append(Conversation.company_id == current_user.company_id)

    statement = (
        select(Conversation)
        .where(*conditions)
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
            if first_msg and (first_msg.content or first_msg.attachments):
                conv.title = _derive_title(first_msg.content or first_msg.attachments[0]["filename"])
                session.add(conv)
                updated = True
    if updated:
        session.commit()
    return conversations


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation_id: uuid.UUID, session: SessionDep, current_user: CurrentUserDep) -> list[Message]:
    conversation = session.get(Conversation, conversation_id)
    if (
        conversation is None
        or conversation.user_id != current_user.id
        or (current_user.company_id and conversation.company_id != current_user.company_id)
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")

    statement = (
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return list(session.exec(statement))


@router.get("/conversations/{conversation_id}/messages/{message_id}/attachments/{index}")
def get_attachment(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    index: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Response:
    conversation = session.get(Conversation, conversation_id)
    message = session.get(Message, message_id)
    if (
        conversation is None
        or conversation.user_id != current_user.id
        or (current_user.company_id and conversation.company_id != current_user.company_id)
        or message is None
        or message.conversation_id != conversation_id
        or not 0 <= index < len(message.attachments or [])
    ):
        raise HTTPException(status_code=404, detail="Attachment not found")

    attachment = message.attachments[index]
    disposition = "inline" if attachments.is_image(attachment) else "attachment"
    return Response(
        storage.read(attachment["uri"]),
        media_type=attachment["mime"],
        # RFC 5987 form: filenames may be non-ASCII, headers may not.
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(attachment['filename'])}"},
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if (
        conversation is None
        or conversation.user_id != current_user.id
        or (current_user.company_id and conversation.company_id != current_user.company_id)
    ):
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
    if (
        conversation is None
        or conversation.user_id != current_user.id
        or (current_user.company_id and conversation.company_id != current_user.company_id)
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")

    files = attachments.locations(
        list(session.exec(select(Message.attachments).where(Message.conversation_id == conversation_id)))
    )
    session.delete(conversation)
    session.commit()
    delete_files(files)  # after the commit: a storage hiccup must not resurrect the chat
