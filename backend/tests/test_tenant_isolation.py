"""One company can never reach into another. These tests walk every company-scoped
route the app registers, so a new route is covered the moment it is mounted - and
fails here if it takes an id this file does not know how to aim at another company."""

import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import COMPANY_PREFIX, app
from app.models.conversation import Conversation
from app.models.department import Department
from app.models.document import Document
from app.models.invite import Invite
from app.models.message import Message
from app.services import invites
from tests.conftest import _registered_client, _user_id_from, client_for, company_id_of

COMPANY_ROUTES = sorted(
    (method.upper(), path.removeprefix(COMPANY_PREFIX))
    for path, operations in app.openapi()["paths"].items()
    if path.startswith(COMPANY_PREFIX)
    for method in operations
)
ROUTES_TAKING_IDS = [(method, path) for method, path in COMPANY_ROUTES if "{" in path]


def test_company_routes_were_discovered():
    assert ("GET", "/documents") in COMPANY_ROUTES
    assert ("POST", "/chat") in COMPANY_ROUTES
    assert len(COMPANY_ROUTES) > 20


@pytest.fixture
def companies(db_engine):
    """Owner of company A, plus company B with one of everything in it."""
    alice = _registered_client(db_engine, "alice@a.com", company_name="Company A", role="owner")
    bob = _registered_client(db_engine, "bob@b.com", company_name="Company B", role="owner")
    bob_id, company_b = _user_id_from(bob), company_id_of(db_engine, "Company B")

    with Session(db_engine) as session:
        department = Department(name="Finance", company_id=company_b)
        document = Document(
            company_id=company_b,
            uploaded_by=bob_id,
            filename="b.md",
            content_type="text/markdown",
            file_path="/tmp/b.md",
            file_hash="hash-b",
            status="ready",
            images=[{"uri": "/tmp/b.png", "page": 1, "caption": "b"}],
        )
        conversation = Conversation(company_id=company_b, user_id=bob_id)
        session.add_all([department, document, conversation])
        session.commit()
        message = Message(
            conversation_id=conversation.id,
            role="user",
            content="secret",
            attachments=[{"filename": "b.txt", "mime": "text/plain", "size": 1, "uri": "/tmp/b.txt"}],
        )
        invite = Invite(
            company_id=company_b,
            email="guest@b.com",
            invited_by=bob_id,
            token_hash=invites.new_token()[1],
            expires_at=conversation.created_at + invites.INVITE_TTL,
        )
        session.add_all([message, invite])
        session.commit()
        ids = {
            "document_id": document.id,
            "conversation_id": conversation.id,
            "message_id": message.id,
            "department_id": department.id,
            "invite_id": invite.id,
            "user_id": bob_id,
            "index": 0,
        }
    return alice, ids


def _fill(path: str, ids: dict) -> str:
    """Substitute company B's ids. A KeyError means a route takes an id this file has
    no company-B resource for: add one to the fixture above."""
    return re.sub(r"\{(\w+)\}", lambda m: str(ids[m[1]]), path)


@pytest.mark.parametrize("method,path", COMPANY_ROUTES)
def test_another_companys_slug_is_not_found(companies, method, path):
    alice, ids = companies
    as_alice_in_b = client_for(_user_id_from(alice), "company-b")

    response = as_alice_in_b.request(method, _fill(path, ids), json={"title": "x", "name": "x"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"


@pytest.mark.parametrize("method,path", ROUTES_TAKING_IDS)
def test_another_companys_ids_are_not_found_under_your_own_slug(companies, method, path):
    alice, ids = companies

    response = alice.request(method, _fill(path, ids), json={"title": "x", "name": "x"})

    assert response.status_code == 404
    assert response.json()["detail"] != "Company not found"  # got past the slug, stopped at the id


def test_another_companys_ids_are_refused_in_request_bodies(companies):
    alice, ids = companies
    upload = {"file": ("a.md", b"# A", "text/markdown")}

    attempts = [
        alice.post("/transfer-ownership", json={"user_id": str(ids["user_id"])}),
        alice.post("/invites", json={"email": "x@a.com", "department_id": str(ids["department_id"])}),
        alice.patch(f"/members/{_user_id_from(alice)}", json={"department_id": str(ids["department_id"])}),
        alice.post(
            "/documents",
            files=upload,
            data={"visibility": "department", "department_id": str(ids["department_id"])},
        ),
        alice.post("/chat", data={"message": "hi", "conversation_id": str(ids["conversation_id"])}),
    ]

    assert [r.status_code for r in attempts] == [404] * len(attempts)


@pytest.mark.parametrize("method,path", COMPANY_ROUTES)
def test_company_routes_need_a_signed_in_user(companies, method, path):
    _, ids = companies
    anonymous = TestClient(app, base_url="http://testserver/companies/company-b")

    assert anonymous.request(method, _fill(path, ids)).status_code == 401


def test_an_instance_admin_is_not_a_member_of_any_company(companies, instance_admin_client):
    _, ids = companies

    for method, path in COMPANY_ROUTES:
        response = instance_admin_client.request(
            method, f"/companies/company-b{_fill(path, ids)}", json={"title": "x", "name": "x"}
        )
        assert response.status_code == 404, (method, path)


def test_unknown_slug_looks_the_same_as_not_a_member(companies):
    alice, _ = companies
    stranger = client_for(_user_id_from(alice), f"no-such-company-{uuid.uuid4().hex[:6]}")

    response = stranger.get("/documents")

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"
