from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, select

from app.config import settings
from app.models.invite import Invite
from tests.conftest import _registered_client, account


def _invite(client, email: str = "newcomer@example.com", **extra) -> dict:
    response = client.post("/invites", json={"email": email, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _register(anon_client, email: str, token: str | None = None):
    payload = {"email": email, "password": "password123"}
    if token:
        payload["invite_token"] = token
    return anon_client.post("/auth/register", json=payload)


def _login(anon_client, email: str):
    token = anon_client.post("/auth/login", json={"email": email, "password": "password123"}).json()
    anon_client.headers["Authorization"] = f"Bearer {token['access_token']}"
    return anon_client


# --- Creating --------------------------------------------------------------------------------


def test_admin_invites_a_member_and_gets_a_link_token_once(admin_client, db_engine):
    dept = admin_client.post("/departments", json={"name": "Engineering"}).json()

    invite = _invite(admin_client, " Newcomer@Example.com ", department_id=dept["id"])

    assert invite["email"] == "newcomer@example.com"
    assert invite["role"] == "member"
    assert invite["department_id"] == dept["id"]
    assert len(invite["token"]) > 30
    # Seven days, and the token itself is never stored or listed again.
    expires = datetime.fromisoformat(invite["expires_at"]).replace(tzinfo=timezone.utc)
    assert timedelta(days=6, hours=23) < expires - datetime.now(timezone.utc) <= timedelta(days=7)
    listed = admin_client.get("/invites").json()
    assert [i["email"] for i in listed] == ["newcomer@example.com"]
    assert "token" not in listed[0]
    with Session(db_engine) as session:
        assert session.exec(select(Invite)).one().token_hash != invite["token"]


def test_only_the_owner_can_invite_an_admin(admin_client, owner_client):
    refused = admin_client.post("/invites", json={"email": "boss@example.com", "role": "admin"})
    allowed = owner_client.post("/invites", json={"email": "boss@example.com", "role": "admin"})

    assert refused.status_code == 403
    assert allowed.status_code == 201


def test_nobody_can_be_invited_as_owner(owner_client):
    response = owner_client.post("/invites", json={"email": "heir@example.com", "role": "owner"})
    assert response.status_code == 422


def test_members_cannot_invite_or_see_invites(member_client):
    assert member_client.post("/invites", json={"email": "friend@example.com"}).status_code == 403
    assert member_client.get("/invites").status_code == 403


def test_inviting_an_existing_member_is_refused(admin_client, member_client):
    response = admin_client.post("/invites", json={"email": "Test-User@example.com"})

    assert response.status_code == 409
    assert response.json()["detail"] == "This person is already a member"


def test_reinviting_replaces_the_earlier_link(admin_client, anon_client):
    first = _invite(admin_client)
    second = _invite(admin_client)

    assert len(admin_client.get("/invites").json()) == 1
    assert anon_client.get(f"/invites/{first['token']}").status_code == 404
    assert anon_client.get(f"/invites/{second['token']}").status_code == 200


def test_admin_revokes_a_pending_invite(admin_client, anon_client):
    invite = _invite(admin_client)

    assert admin_client.delete(f"/invites/{invite['id']}").status_code == 204

    assert admin_client.get("/invites").json() == []
    assert anon_client.get(f"/invites/{invite['token']}").status_code == 404


# --- Accepting -------------------------------------------------------------------------------


def test_invite_page_previews_company_and_email_without_signing_in(admin_client, anon_client):
    invite = _invite(admin_client)

    response = anon_client.get(f"/invites/{invite['token']}")

    assert response.status_code == 200
    assert response.json() == {"company_name": "Test Company", "email": "newcomer@example.com", "role": "member"}


@pytest.mark.parametrize("signup_mode", ["open", "approval", "closed"])
def test_a_new_person_registers_through_an_invite_in_any_signup_mode(
    admin_client, anon_client, monkeypatch, signup_mode
):
    """An invite vouches for the account: no approval wait, and closed signup lets it in."""
    monkeypatch.setattr(settings, "signup_mode", signup_mode)
    dept = admin_client.post("/departments", json={"name": "Engineering"}).json()
    invite = _invite(admin_client, department_id=dept["id"])

    response = _register(anon_client, "newcomer@example.com", invite["token"])

    assert response.status_code == 201
    assert response.json()["approval_status"] == "approved"
    assert response.json()["company_slug"] == "test-company"
    me = _login(anon_client, "newcomer@example.com").get("/auth/me").json()
    assert [(c["slug"], c["role"], c["department_name"]) for c in me["companies"]] == [
        ("test-company", "member", "Engineering")
    ]
    assert admin_client.get("/invites").json() == []


def test_an_existing_user_accepts_after_signing_in(admin_client, other_company_client):
    invite = _invite(admin_client, "other-company-user@example.com")
    outsider = account(other_company_client)

    response = outsider.post(f"/invites/{invite['token']}/accept")

    assert response.status_code == 200
    assert response.json() == {"company_slug": "test-company"}
    slugs = {c["slug"] for c in outsider.get("/auth/me").json()["companies"]}
    assert slugs == {"other-company", "test-company"}


def test_an_invite_works_once(admin_client, other_company_client, anon_client):
    invite = _invite(admin_client, "other-company-user@example.com")
    outsider = account(other_company_client)
    outsider.post(f"/invites/{invite['token']}/accept")

    assert outsider.post(f"/invites/{invite['token']}/accept").status_code == 404
    assert anon_client.get(f"/invites/{invite['token']}").status_code == 404


def test_an_invite_only_works_for_the_invited_email(admin_client, other_company_client, anon_client):
    invite = _invite(admin_client, "newcomer@example.com")

    accepted = account(other_company_client).post(f"/invites/{invite['token']}/accept")
    registered = _register(anon_client, "someone-else@example.com", invite["token"])

    assert accepted.status_code == 403
    assert registered.status_code == 403
    assert len(admin_client.get("/invites").json()) == 1  # still there for the right person


def test_an_expired_invite_is_dead_everywhere(admin_client, anon_client, db_engine):
    invite = _invite(admin_client)
    with Session(db_engine) as session:
        row = session.exec(select(Invite)).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.add(row)
        session.commit()

    assert anon_client.get(f"/invites/{invite['token']}").status_code == 404
    assert _register(anon_client, "newcomer@example.com", invite["token"]).status_code == 404
    assert admin_client.get("/invites").json() == []


def test_someone_who_joined_another_way_gets_a_clear_message(admin_client, db_engine):
    invite = _invite(admin_client)
    newcomer = account(_registered_client(db_engine, "newcomer@example.com"))  # now a member already

    response = newcomer.post(f"/invites/{invite['token']}/accept")

    assert response.status_code == 409
    assert response.json()["detail"] == "You are already a member of Test Company"


def test_accepting_needs_a_signed_in_user(admin_client, anon_client):
    invite = _invite(admin_client)
    assert anon_client.post(f"/invites/{invite['token']}/accept").status_code == 401
