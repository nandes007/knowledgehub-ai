import uuid
from datetime import date

from sqlmodel import Session

from app.models.document import Document
from app.models.message import Message
from app.models.user import User


def _make_admin(db_engine, user_id: uuid.UUID) -> None:
    with Session(db_engine) as session:
        user = session.get(User, user_id)
        user.role = "admin"
        session.add(user)
        session.commit()


def test_stats_requires_admin_role(client):
    response = client.get("/stats")

    assert response.status_code == 403


def test_stats_returns_message_counts_doc_count_and_estimated_cost(client, db_engine, test_user_id):
    _make_admin(db_engine, test_user_id)

    conversation_id = uuid.UUID(client.post("/conversations").json()["id"])

    with Session(db_engine) as session:
        user = session.get(User, test_user_id)
        session.add(Message(conversation_id=conversation_id, role="user", content="hi"))
        session.add(
            Message(conversation_id=conversation_id, role="assistant", content="hello", token_count=1000)
        )
        session.add(
            Document(
                user_id=test_user_id,
                company_id=user.company_id,
                filename="a.md",
                content_type="text/markdown",
                file_path="/tmp/a.md",
                file_hash="hash1",
            )
        )
        session.commit()

    response = client.get("/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["document_count"] == 1
    assert sum(day["count"] for day in body["messages_per_day"]) == 2
    assert body["estimated_cost_usd"] == 0.0003


def test_stats_returns_documents_per_user(client, other_client, db_engine, test_user_id, other_user_id):
    _make_admin(db_engine, test_user_id)

    with Session(db_engine) as session:
        for index, owner in enumerate([test_user_id, other_user_id, other_user_id]):
            user = session.get(User, owner)
            session.add(
                Document(
                    user_id=owner,
                    company_id=user.company_id,
                    filename=f"{index}.md",
                    content_type="text/markdown",
                    file_path=f"/tmp/{index}.md",
                    file_hash=f"hash{index}",
                )
            )
        session.commit()

    body = client.get("/stats").json()

    assert body["documents_per_user"] == [
        {"email": "other-user@example.com", "count": 2},
        {"email": "test-user@example.com", "count": 1},
    ]


def test_stats_returns_cost_per_day(client, db_engine, test_user_id):
    _make_admin(db_engine, test_user_id)

    conversation_id = uuid.UUID(client.post("/conversations").json()["id"])

    with Session(db_engine) as session:
        session.add(
            Message(conversation_id=conversation_id, role="assistant", content="a", token_count=1000)
        )
        session.add(
            Message(conversation_id=conversation_id, role="assistant", content="b", token_count=2000)
        )
        # User messages aren't billed by this estimate, so they must not add cost.
        session.add(Message(conversation_id=conversation_id, role="user", content="hi", token_count=5000))
        session.commit()

    body = client.get("/stats").json()

    assert body["cost_per_day"] == [
        {"date": str(date.today()), "cost_usd": 0.0009},
    ]
