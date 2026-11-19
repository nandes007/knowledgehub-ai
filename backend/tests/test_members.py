import pytest
from sqlmodel import Session, select

from app.models.conversation import Conversation
from app.models.document import Document
from app.models.membership import Membership
from tests.conftest import _registered_client, _user_id_from, company_id_of


@pytest.fixture
def team(db_engine):
    """One company: an owner, two admins and two members."""
    people = {
        name: _registered_client(db_engine, f"{name}@team.com", role=role)
        for name, role in [
            ("owner", "owner"),
            ("admin", "admin"),
            ("admin2", "admin"),
            ("member", "member"),
            ("member2", "member"),
        ]
    }
    people["ids"] = {name: str(_user_id_from(c)) for name, c in people.items()}
    return people


def _roles(client) -> dict[str, str]:
    return {m["email"].split("@")[0]: m["role"] for m in client.get("/members").json()}


# --- Listing ---------------------------------------------------------------------------------


def test_owner_and_admin_can_list_members_but_a_member_cannot(team):
    assert _roles(team["owner"]) == {
        "owner": "owner", "admin": "admin", "admin2": "admin", "member": "member", "member2": "member"
    }
    assert team["admin"].get("/members").status_code == 200
    assert team["member"].get("/members").status_code == 403


# --- Changing roles --------------------------------------------------------------------------


def test_owner_promotes_and_demotes(team):
    ids = team["ids"]

    promoted = team["owner"].patch(f"/members/{ids['member']}", json={"role": "admin"})
    demoted = team["owner"].patch(f"/members/{ids['admin']}", json={"role": "member"})

    assert promoted.status_code == 200 and promoted.json()["role"] == "admin"
    assert demoted.status_code == 200 and demoted.json()["role"] == "member"


def test_a_role_change_applies_on_the_next_request(team):
    """No waiting for a token to expire: membership is read on every request."""
    assert team["member"].get("/members").status_code == 403

    team["owner"].patch(f"/members/{team['ids']['member']}", json={"role": "admin"})

    assert team["member"].get("/members").status_code == 200


def test_an_admin_cannot_change_any_role(team):
    ids = team["ids"]

    for target, role in [("member", "admin"), ("admin2", "member"), ("owner", "member")]:
        response = team["admin"].patch(f"/members/{ids[target]}", json={"role": role})
        assert response.status_code == 403, target

    assert _roles(team["owner"])["member"] == "member"


def test_nobody_can_change_their_own_role(team):
    ids = team["ids"]

    as_owner = team["owner"].patch(f"/members/{ids['owner']}", json={"role": "admin"})
    as_admin = team["admin"].patch(f"/members/{ids['admin']}", json={"role": "member"})

    assert as_owner.status_code == 403 and as_admin.status_code == 403
    assert as_owner.json()["detail"] == "You cannot change your own role"


def test_owner_role_cannot_be_granted_by_editing_a_member(team):
    response = team["owner"].patch(f"/members/{team['ids']['admin']}", json={"role": "owner"})

    assert response.status_code == 400
    assert _roles(team["owner"])["admin"] == "admin"


def test_unknown_role_is_rejected(team):
    response = team["owner"].patch(f"/members/{team['ids']['member']}", json={"role": "superadmin"})
    assert response.status_code == 422


# --- Departments -----------------------------------------------------------------------------


def test_admin_sets_and_clears_a_members_department(team):
    dept = team["admin"].post("/departments", json={"name": "Engineering"}).json()
    member_id = team["ids"]["member"]

    assigned = team["admin"].patch(f"/members/{member_id}", json={"department_id": dept["id"]})
    assert assigned.json()["department_name"] == "Engineering"
    assert assigned.json()["role"] == "member"

    untouched = team["admin"].patch(f"/members/{member_id}", json={})
    assert untouched.json()["department_id"] == dept["id"]

    cleared = team["admin"].patch(f"/members/{member_id}", json={"department_id": None})
    assert cleared.json()["department_id"] is None


def test_admin_cannot_edit_another_admin_or_the_owner(team):
    dept = team["admin"].post("/departments", json={"name": "Engineering"}).json()

    for target in ("admin2", "owner"):
        response = team["admin"].patch(f"/members/{team['ids'][target]}", json={"department_id": dept["id"]})
        assert response.status_code == 403, target


# --- Removing and leaving --------------------------------------------------------------------


def test_admin_removes_a_member_but_not_an_admin_or_the_owner(team):
    ids = team["ids"]

    assert team["admin"].delete(f"/members/{ids['member']}").status_code == 204
    assert team["admin"].delete(f"/members/{ids['admin2']}").status_code == 403
    assert team["admin"].delete(f"/members/{ids['owner']}").status_code == 403

    assert set(_roles(team["owner"])) == {"owner", "admin", "admin2", "member2"}
    # Removed means out at once, and indistinguishable from never having been in.
    assert team["member"].get("/documents").status_code == 404


def test_owner_removes_an_admin(team):
    assert team["owner"].delete(f"/members/{team['ids']['admin']}").status_code == 204
    assert "admin" not in _roles(team["owner"])


def test_a_member_cannot_remove_anyone_else(team):
    response = team["member"].delete(f"/members/{team['ids']['member2']}")
    assert response.status_code == 403


def test_members_and_admins_can_leave(team):
    assert team["member"].delete(f"/members/{team['ids']['member']}").status_code == 204
    assert team["admin"].delete(f"/members/{team['ids']['admin']}").status_code == 204
    assert set(_roles(team["owner"])) == {"owner", "admin2", "member2"}


def test_the_owner_cannot_leave_without_transferring_ownership(team):
    response = team["owner"].delete(f"/members/{team['ids']['owner']}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Transfer ownership before leaving the company"
    assert _roles(team["owner"])["owner"] == "owner"


def test_removing_a_member_keeps_their_documents_and_deletes_their_conversations(team, db_engine):
    member_id = _user_id_from(team["member"])
    team["member"].post("/conversations")
    team["member2"].post("/conversations")
    with Session(db_engine) as session:
        session.add(
            Document(
                company_id=company_id_of(db_engine),
                uploaded_by=member_id,
                filename="kept.md",
                content_type="text/markdown",
                file_path="/tmp/kept.md",
                file_hash="kept",
                status="ready",
            )
        )
        session.commit()

    assert team["admin"].delete(f"/members/{member_id}").status_code == 204

    assert [d["filename"] for d in team["admin"].get("/documents").json()] == ["kept.md"]
    with Session(db_engine) as session:
        remaining = session.exec(select(Conversation.user_id)).all()
    assert remaining == [_user_id_from(team["member2"])]


def test_leaving_one_company_leaves_the_others_alone(team, db_engine):
    elsewhere = _registered_client(db_engine, "member@team.com", company_name="Elsewhere", role="admin")
    elsewhere.post("/conversations")

    team["member"].delete(f"/members/{team['ids']['member']}")

    assert len(elsewhere.get("/conversations").json()) == 1


# --- Ownership transfer ----------------------------------------------------------------------


def test_transfer_makes_the_target_owner_and_the_old_owner_an_admin(team):
    response = team["owner"].post("/transfer-ownership", json={"user_id": team["ids"]["member"]})

    assert response.status_code == 200
    assert response.json()["role"] == "owner"
    roles = _roles(team["member"])
    assert roles["member"] == "owner" and roles["owner"] == "admin"
    # The former owner may now leave.
    assert team["owner"].delete(f"/members/{team['ids']['owner']}").status_code == 204


def test_only_the_owner_can_transfer_ownership(team, db_engine):
    response = team["admin"].post("/transfer-ownership", json={"user_id": team["ids"]["admin"]})

    assert response.status_code == 403
    with Session(db_engine) as session:
        owners = session.exec(select(Membership).where(Membership.role == "owner")).all()
    assert len(owners) == 1


def test_ownership_cannot_be_transferred_to_yourself_or_a_non_member(team, db_engine):
    outsider = _registered_client(db_engine, "outsider@else.com", company_name="Elsewhere")

    to_self = team["owner"].post("/transfer-ownership", json={"user_id": team["ids"]["owner"]})
    to_outsider = team["owner"].post("/transfer-ownership", json={"user_id": str(_user_id_from(outsider))})

    assert to_self.status_code == 400
    assert to_outsider.status_code == 404
    assert _roles(team["owner"])["owner"] == "owner"
