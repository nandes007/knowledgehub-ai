import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.conversation import Conversation
from app.models.message import Message


def test_create_conversation_returns_default_title(client):
    response = client.post("/conversations")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New chat"
    assert uuid.UUID(body["id"])


def test_list_conversations_returns_newest_first(client, db_engine):
    older = client.post("/conversations").json()
    newer = client.post("/conversations").json()

    with Session(db_engine) as session:
        conversation = session.get(Conversation, uuid.UUID(older["id"]))
        conversation.updated_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        session.add(conversation)
        session.commit()

    response = client.get("/conversations")

    ids = [c["id"] for c in response.json()]
    assert ids[0] == newer["id"]
    assert ids[1] == older["id"]


def test_list_messages_for_unknown_conversation_returns_404(client):
    response = client.get(f"/conversations/{uuid.uuid4()}/messages")

    assert response.status_code == 404


def test_list_messages_returns_chronological_order_with_sources(client, db_engine):
    conversation = client.post("/conversations").json()
    conversation_id = uuid.UUID(conversation["id"])

    with Session(db_engine) as session:
        session.add(Message(conversation_id=conversation_id, role="user", content="Hi"))
        session.add(
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content="Hello!",
                sources=[{"document_id": "d1", "filename": "a.md", "chunk_preview": "..."}],
            )
        )
        session.commit()

    response = client.get(f"/conversations/{conversation_id}/messages")

    assert response.status_code == 200
    messages = response.json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["sources"][0]["filename"] == "a.md"
