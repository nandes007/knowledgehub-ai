import uuid
from datetime import date

from sqlmodel import Session

from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from tests.conftest import _user_id_from, account, company_id_of


def test_stats_requires_admin_role(member_client):
    response = member_client.get("/stats")
    assert response.status_code == 403


def test_instance_stats_require_instance_admin(admin_client):
    assert account(admin_client).get("/instance/stats").status_code == 403


def test_stats_returns_message_counts_doc_count_and_estimated_cost(admin_client, db_engine):
    conversation_id = uuid.UUID(admin_client.post("/conversations").json()["id"])

    with Session(db_engine) as session:
        session.add(Message(conversation_id=conversation_id, role="user", content="hi"))
        session.add(
            Message(conversation_id=conversation_id, role="assistant", content="hello", token_count=1000)
        )
        session.add(
            Document(
                uploaded_by=_user_id_from(admin_client),
                company_id=company_id_of(db_engine),
                filename="a.md",
                content_type="text/markdown",
                file_path="/tmp/a.md",
                file_hash="hash1",
            )
        )
        session.commit()

    response = admin_client.get("/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["document_count"] == 1
    assert sum(day["count"] for day in body["messages_per_day"]) == 2
    assert body["estimated_cost_usd"] == 0.0003


def test_stats_scoped_by_company_for_admin_isolation(
    admin_client, other_company_client, instance_admin_client, db_engine
):
    conv_a = uuid.UUID(admin_client.post("/conversations").json()["id"])
    conv_b = uuid.UUID(other_company_client.post("/conversations").json()["id"])

    with Session(db_engine) as session:
        user_a, company_a = _user_id_from(admin_client), company_id_of(db_engine)
        user_b, company_b = _user_id_from(other_company_client), company_id_of(db_engine, "Other Company")

        # Company A: 1 doc, 1 message with 1000 tokens
        session.add(Message(conversation_id=conv_a, role="assistant", content="a", token_count=1000))
        session.add(
            Document(
                uploaded_by=user_a,
                company_id=company_a,
                filename="a.md",
                content_type="text/markdown",
                file_path="/tmp/a.md",
                file_hash="hash_a",
            )
        )

        # Company B: 2 docs, 1 message with 2000 tokens
        session.add(Message(conversation_id=conv_b, role="assistant", content="b", token_count=2000))
        session.add(
            Document(
                uploaded_by=user_b,
                company_id=company_b,
                filename="b1.md",
                content_type="text/markdown",
                file_path="/tmp/b1.md",
                file_hash="hash_b1",
            )
        )
        session.add(
            Document(
                uploaded_by=user_b,
                company_id=company_b,
                filename="b2.md",
                content_type="text/markdown",
                file_path="/tmp/b2.md",
                file_hash="hash_b2",
            )
        )
        session.commit()

    # Admin A sees only Company A's stats
    body_a = admin_client.get("/stats").json()
    assert body_a["document_count"] == 1
    assert sum(day["count"] for day in body_a["messages_per_day"]) == 1
    assert body_a["estimated_cost_usd"] == 0.0003

    # The instance admin sees instance-wide totals (both companies), but not a company's own page.
    assert instance_admin_client.get("/companies/test-company/stats").status_code == 404
    body_sa = instance_admin_client.get("/instance/stats").json()
    assert body_sa["document_count"] == 3
    assert sum(day["count"] for day in body_sa["messages_per_day"]) == 2
    assert body_sa["estimated_cost_usd"] == 0.0009


def test_stats_returns_documents_per_user(admin_client, other_client, db_engine, other_user_id):
    with Session(db_engine) as session:
        admin_id = _user_id_from(admin_client)
        for index, owner in enumerate([admin_id, other_user_id, other_user_id]):
            session.add(
                Document(
                    uploaded_by=owner,
                    company_id=company_id_of(db_engine),
                    filename=f"{index}.md",
                    content_type="text/markdown",
                    file_path=f"/tmp/{index}.md",
                    file_hash=f"hash{index}",
                )
            )
        session.commit()

    body = admin_client.get("/stats").json()

    assert body["documents_per_user"] == [
        {"email": "other-user@example.com", "count": 2},
        {"email": "admin-user@example.com", "count": 1},
    ]


def test_stats_returns_cost_per_day(admin_client, db_engine):
    conversation_id = uuid.UUID(admin_client.post("/conversations").json()["id"])

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

    body = admin_client.get("/stats").json()

    assert body["cost_per_day"] == [
        {"date": str(date.today()), "cost_usd": 0.0009},
    ]
