import uuid

import pytest
from sqlmodel import Session, select

from app.config import settings
from app.main import app
from app.models.company import Company
from app.models.conversation import Conversation
from app.models.department import Department
from app.models.document import Document
from app.models.invite import Invite
from app.models.membership import Membership
from app.models.message import Message
from app.services.llm import get_llm_provider
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _registered_client, _user_id_from, account, client_for


@pytest.fixture
def user(member_client):
    """A signed-in account, outside any company."""
    return account(member_client)


# --- Creating --------------------------------------------------------------------------------


def test_creating_a_company_makes_the_creator_its_owner(user):
    response = user.post("/companies", json={"name": "  Acme & Sons  "})

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["slug"], body["role"], body["status"]) == ("Acme & Sons", "acme-sons", "owner", "active")
    mine = {c["slug"]: c["role"] for c in user.get("/auth/me").json()["companies"]}
    assert mine == {"test-company": "member", "acme-sons": "owner"}
    assert client_for(_user_id_from(user), "acme-sons").get("/members").status_code == 200


def test_slugs_are_unique_and_avoid_the_apps_own_paths(user):
    slugs = [user.post("/companies", json={"name": name}).json()["slug"] for name in ("A.B", "A B", "Login", "日本")]
    assert slugs == ["a-b", "a-b-2", "login-2", "company"]


def test_duplicate_and_blank_company_names_are_rejected(user):
    assert user.post("/companies", json={"name": "Test Company"}).status_code == 409
    assert user.post("/companies", json={"name": "   "}).status_code == 422


def test_creating_a_company_needs_a_signed_in_user(anon_client):
    assert anon_client.post("/companies", json={"name": "Acme"}).status_code == 401


def test_company_ownership_cap(user, monkeypatch):
    monkeypatch.setattr(settings, "max_companies_per_user", 2)

    created = [user.post("/companies", json={"name": f"Co {n}"}) for n in range(3)]

    assert [r.status_code for r in created] == [201, 201, 403]
    assert "Company limit reached" in created[2].json()["detail"]
    # Being a member of a company (Test Company) does not count against the cap.

    monkeypatch.setattr(settings, "max_companies_per_user", 0)
    assert user.post("/companies", json={"name": "Co 3"}).status_code == 201


# --- Reading and renaming --------------------------------------------------------------------


def test_any_member_can_read_their_company(member_client):
    body = member_client.get("").json()
    assert (body["name"], body["slug"], body["role"]) == ("Test Company", "test-company", "member")


def test_owner_renames_the_company_and_the_slug_stays(owner_client, admin_client):
    assert admin_client.patch("", json={"name": "Renamed"}).status_code == 403

    response = owner_client.patch("", json={"name": "Renamed"})

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["slug"]) == ("Renamed", "test-company")
    assert owner_client.get("/documents").status_code == 200  # old links still work


def test_rename_rejects_a_name_another_company_uses(owner_client, other_company_client):
    assert owner_client.patch("", json={"name": "Other Company"}).status_code == 409
    assert owner_client.patch("", json={"name": "Test Company"}).status_code == 200  # its own name


# --- Deleting --------------------------------------------------------------------------------


class _FakeLLM:
    def embed_texts(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_only_the_owner_deletes_the_company_and_everything_in_it_goes(
    owner_client, admin_client, other_company_client, db_engine, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "qdrant"))
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        owner_client.post("/departments", json={"name": "Engineering"})
        owner_client.post("/invites", json={"email": "pending@example.com"})
        owner_client.post("/documents", files={"file": ("policy.md", b"# Policy\n\nTwenty days.", "text/markdown")})
        conversation_id = uuid.UUID(admin_client.post("/conversations").json()["id"])
        with Session(db_engine) as session:
            session.add(Message(conversation_id=conversation_id, role="user", content="hi"))
            session.commit()
        other_company_client.post("/conversations")
        assert store.query([1.0, 0.0], top_k=5) != []

        assert admin_client.delete("").status_code == 403
        assert owner_client.delete("").status_code == 204

        assert store.query([1.0, 0.0], top_k=5) == []
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_vector_store, None)

    assert [p for p in (tmp_path / "uploads").rglob("*") if p.is_file()] == []
    with Session(db_engine) as session:
        assert [c.name for c in session.exec(select(Company))] == ["Other Company"]
        for model in (Membership, Conversation):
            assert len(session.exec(select(model)).all()) == 1, model  # the other company's
        for model in (Department, Invite, Document, Message):
            assert session.exec(select(model)).all() == [], model
    assert owner_client.get("").status_code == 404
    assert account(owner_client).get("/auth/me").json()["companies"] == []
