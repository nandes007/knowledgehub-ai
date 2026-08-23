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


def test_list_conversations_derives_title_from_first_user_message_if_default(client, db_engine):
    conversation = client.post("/conversations").json()
    conversation_id = uuid.UUID(conversation["id"])

    with Session(db_engine) as session:
        session.add(
            Message(conversation_id=conversation_id, role="user", content="What are company holidays?")
        )
        session.commit()

    response = client.get("/conversations")
    assert response.status_code == 200
    convs = response.json()
    matched = next(c for c in convs if c["id"] == conversation["id"])
    assert matched["title"] == "What are company holidays?"


def test_list_conversations_truncates_long_titles_with_ellipsis(client, db_engine):
    conversation = client.post("/conversations").json()
    conversation_id = uuid.UUID(conversation["id"])
    long_msg = "This is a very long user question that exceeds forty-eight characters easily"

    with Session(db_engine) as session:
        session.add(Message(conversation_id=conversation_id, role="user", content=long_msg))
        session.commit()

    response = client.get("/conversations")
    assert response.status_code == 200
    convs = response.json()
    matched = next(c for c in convs if c["id"] == conversation["id"])
    assert matched["title"] == f"{long_msg[:48]}…"


def test_update_conversation_renames_title(client):
    conversation = client.post("/conversations").json()
    conversation_id = conversation["id"]

    response = client.patch(f"/conversations/{conversation_id}", json={"title": "Updated Title"})
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"

    # Verify persisted in list
    list_res = client.get("/conversations")
    matched = next(c for c in list_res.json() if c["id"] == conversation_id)
    assert matched["title"] == "Updated Title"


def test_update_conversation_rejects_empty_title(client):
    conversation = client.post("/conversations").json()
    conversation_id = conversation["id"]

    response = client.patch(f"/conversations/{conversation_id}", json={"title": "   "})
    assert response.status_code == 422


def test_update_conversation_404_for_unknown_or_other_user(client):
    response = client.patch(f"/conversations/{uuid.uuid4()}", json={"title": "New Title"})
    assert response.status_code == 404


def test_delete_conversation_removes_it(client):
    conversation = client.post("/conversations").json()
    conversation_id = conversation["id"]

    response = client.delete(f"/conversations/{conversation_id}")
    assert response.status_code == 204

    # Verify no longer in list
    list_res = client.get("/conversations")
    assert not any(c["id"] == conversation_id for c in list_res.json())

    # Verify 404 on messages
    msg_res = client.get(f"/conversations/{conversation_id}/messages")
    assert msg_res.status_code == 404


def test_delete_conversation_404_for_unknown(client):
    response = client.delete(f"/conversations/{uuid.uuid4()}")
    assert response.status_code == 404


def test_cross_company_conversation_access_returns_404(client, other_company_client):
    conversation = client.post("/conversations").json()
    conversation_id = conversation["id"]

    # Other company user cannot read messages
    res_msg = other_company_client.get(f"/conversations/{conversation_id}/messages")
    assert res_msg.status_code == 404

    # Other company user cannot patch title
    res_patch = other_company_client.patch(
        f"/conversations/{conversation_id}", json={"title": "Hijacked Title"}
    )
    assert res_patch.status_code == 404

    # Other company user cannot delete
    res_del = other_company_client.delete(f"/conversations/{conversation_id}")
    assert res_del.status_code == 404

    # Other company user does not see it in their conversation list
    list_res = other_company_client.get("/conversations")
    assert not any(c["id"] == conversation_id for c in list_res.json())
