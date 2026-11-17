import pytest
from sqlmodel import Session, select

from app.cli import create_instance_admin
from app.main import app
from app.models.company import Company
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.membership import Membership
from app.models.user import User
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _registered_client, _user_id_from, account, client_for, company_id_of

INSTANCE_ROUTES = sorted(
    (method.upper(), path)
    for path, operations in app.openapi()["paths"].items()
    if path.startswith("/instance")
    for method in operations
)


# --- Who gets in -----------------------------------------------------------------------------


@pytest.mark.parametrize("method,path", INSTANCE_ROUTES)
def test_platform_routes_refuse_everyone_but_instance_admins(owner_client, anon_client, method, path):
    """Owning a company grants nothing on the platform."""
    path = path.replace("{user_id}", str(_user_id_from(owner_client))).replace("{company_id}", "x")

    assert account(owner_client).request(method, path).status_code == 403
    assert anon_client.request(method, path).status_code == 401


def test_cli_bootstraps_an_instance_admin_who_can_log_in(anon_client, db_engine):
    create_instance_admin("root@example.com", "password123", engine=db_engine)

    token = anon_client.post(
        "/auth/login", json={"email": "root@example.com", "password": "password123"}
    ).json()["access_token"]
    anon_client.headers["Authorization"] = f"Bearer {token}"

    me = anon_client.get("/auth/me").json()
    assert me["is_instance_admin"] is True and me["companies"] == []
    assert anon_client.get("/instance/companies").status_code == 200
    with pytest.raises(ValueError):
        create_instance_admin("root@example.com", "password123", engine=db_engine)


def test_an_instance_admin_can_also_be_an_ordinary_member(instance_admin_client, db_engine):
    """A membership, not the platform role, is what opens a company."""
    assert instance_admin_client.get("/companies/test-company/documents").status_code == 404

    as_member = _registered_client(db_engine, "instance-admin@example.com", role="member")

    assert as_member.get("/documents").status_code == 200
    assert as_member.get("/members").status_code == 403  # a member like any other


# --- Users -----------------------------------------------------------------------------------


def test_lists_users_with_their_companies_and_filters_by_approval(
    instance_admin_client, owner_client, other_company_client, db_engine
):
    with Session(db_engine) as session:
        session.add(User(email="waiting@example.com", password_hash="x", approval_status="pending"))
        session.commit()

    everyone = {u["email"]: u for u in instance_admin_client.get("/instance/users").json()}
    pending = instance_admin_client.get("/instance/users", params={"approval_status": "pending"}).json()

    assert set(everyone) == {
        "instance-admin@example.com", "owner-user@example.com", "other-company-user@example.com", "waiting@example.com"
    }
    assert everyone["owner-user@example.com"]["companies"] == [
        {"name": "Test Company", "slug": "test-company", "role": "owner"}
    ]
    assert everyone["instance-admin@example.com"]["is_instance_admin"] is True
    assert [u["email"] for u in pending] == ["waiting@example.com"]


def test_approve_and_reject_unknown_user_is_404(instance_admin_client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert instance_admin_client.patch(f"/instance/users/{missing}/approve").status_code == 404
    assert instance_admin_client.patch(f"/instance/users/{missing}/reject").status_code == 404
    assert instance_admin_client.delete(f"/instance/users/{missing}").status_code == 404


def test_an_instance_admin_cannot_reject_or_delete_themselves(instance_admin_client):
    me = instance_admin_client.get("/auth/me").json()["id"]

    assert instance_admin_client.patch(f"/instance/users/{me}/reject").status_code == 403
    assert instance_admin_client.delete(f"/instance/users/{me}").status_code == 403


def test_deleting_a_user_keeps_their_uploads_and_removes_their_chats(
    instance_admin_client, owner_client, admin_client, db_engine
):
    admin_id = _user_id_from(admin_client)
    admin_client.post("/conversations")
    with Session(db_engine) as session:
        session.add(
            Document(
                company_id=company_id_of(db_engine),
                uploaded_by=admin_id,
                filename="kept.md",
                content_type="text/markdown",
                file_path="/tmp/kept.md",
                file_hash="kept",
                status="ready",
            )
        )
        session.commit()

    assert instance_admin_client.delete(f"/instance/users/{admin_id}").status_code == 204

    with Session(db_engine) as session:
        assert session.get(User, admin_id) is None
        assert session.exec(select(Conversation)).all() == []
        assert session.exec(select(Membership.role)).all() == ["owner"]
        # The upload stays with the company, now credited to its owner.
        assert session.exec(select(Document)).one().uploaded_by == _user_id_from(owner_client)
    assert admin_client.get("/documents").status_code == 401


def test_a_user_who_owns_a_company_cannot_be_deleted(instance_admin_client, owner_client):
    response = instance_admin_client.delete(f"/instance/users/{_user_id_from(owner_client)}")

    assert response.status_code == 409
    assert owner_client.get("/documents").status_code == 200


# --- Companies -------------------------------------------------------------------------------


def test_lists_companies_with_member_counts(instance_admin_client, owner_client, admin_client, other_company_client):
    companies = {c["slug"]: c for c in instance_admin_client.get("/instance/companies").json()}

    assert {slug: c["member_count"] for slug, c in companies.items()} == {"test-company": 2, "other-company": 1}
    assert companies["test-company"]["status"] == "active"


def test_suspending_a_company_blocks_it_until_reactivated(instance_admin_client, owner_client, db_engine):
    company_id = company_id_of(db_engine)
    elsewhere = _registered_client(db_engine, "owner-user@example.com", company_name="Elsewhere", role="owner")

    suspended = instance_admin_client.patch(f"/instance/companies/{company_id}/suspend")
    assert suspended.status_code == 200 and suspended.json()["status"] == "suspended"
    assert owner_client.get("/documents").status_code == 403
    assert elsewhere.get("/documents").status_code == 200  # the owner's other company is unaffected
    me = account(owner_client).get("/auth/me").json()
    assert {c["slug"]: c["status"] for c in me["companies"]} == {"test-company": "suspended", "elsewhere": "active"}

    activated = instance_admin_client.patch(f"/instance/companies/{company_id}/activate")
    assert activated.status_code == 200 and activated.json()["status"] == "active"
    assert owner_client.get("/documents").status_code == 200


def test_deleting_a_company_removes_it_for_its_members(instance_admin_client, owner_client, db_engine, tmp_path):
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(persist_dir=str(tmp_path))
    try:
        response = instance_admin_client.delete(f"/instance/companies/{company_id_of(db_engine)}")
    finally:
        app.dependency_overrides.pop(get_vector_store, None)

    assert response.status_code == 204
    with Session(db_engine) as session:
        assert session.exec(select(Company)).all() == []
        assert session.exec(select(Membership)).all() == []
        assert session.get(User, _user_id_from(owner_client)) is not None  # the account survives
    assert client_for(_user_id_from(owner_client), "test-company").get("/documents").status_code == 404


def test_unknown_company_is_404(instance_admin_client):
    missing = "00000000-0000-0000-0000-000000000000"
    for method, action in [("PATCH", "/suspend"), ("PATCH", "/activate"), ("DELETE", "")]:
        assert instance_admin_client.request(method, f"/instance/companies/{missing}{action}").status_code == 404
