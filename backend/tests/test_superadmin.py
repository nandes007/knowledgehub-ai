import uuid

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, select

from app.cli import create_superadmin, main as cli_main
from app.main import app
from app.models.company import Company
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from tests.conftest import _override_db


def _create_superadmin_client(db_engine, email: str = "superadmin@platform.internal") -> tuple[TestClient, User]:
    _override_db(db_engine)
    with Session(db_engine) as session:
        user = User(
            email=email,
            password_hash=hash_password("password123"),
            role="superadmin",
            approval_status="approved",
            company_id=None,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(user_id)}"
    return client, user


def test_cli_create_superadmin(db_engine):
    user = create_superadmin(
        email="cli-superadmin@platform.internal",
        password="supersecretpassword",
        display_name="CLI Superadmin",
        engine=db_engine,
    )

    assert user.email == "cli-superadmin@platform.internal"
    assert user.role == "superadmin"
    assert user.approval_status == "approved"
    assert user.company_id is None
    assert user.display_name == "CLI Superadmin"

    with Session(db_engine) as session:
        db_user = session.exec(
            select(User).where(User.email == "cli-superadmin@platform.internal")
        ).first()
        assert db_user is not None
        assert db_user.role == "superadmin"
        assert db_user.company_id is None
        assert db_user.approval_status == "approved"


def test_cli_create_superadmin_rejects_duplicate_email(db_engine):
    create_superadmin(
        email="dup-superadmin@platform.internal",
        password="password123",
        engine=db_engine,
    )

    with pytest.raises(ValueError, match="already exists"):
        create_superadmin(
            email="dup-superadmin@platform.internal",
            password="anotherpassword",
            engine=db_engine,
        )


def test_cli_main_entrypoint(db_engine, monkeypatch):
    monkeypatch.setattr("app.cli.get_engine", lambda: db_engine)
    # Test valid execution
    cli_main(["create-superadmin", "--email", "main-cli@platform.internal", "--password", "password123"])

    with Session(db_engine) as session:
        user = session.exec(
            select(User).where(User.email == "main-cli@platform.internal")
        ).first()
        assert user is not None

    # Test duplicate execution exits with 1
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["create-superadmin", "--email", "main-cli@platform.internal", "--password", "password123"])
    assert exc_info.value.code == 1


def test_get_users_with_and_without_filter(db_engine):
    sa_client, _ = _create_superadmin_client(db_engine)

    with Session(db_engine) as session:
        comp = Company(name="Test Co", status="active")
        session.add(comp)
        session.commit()
        session.refresh(comp)

        u1 = User(
            email="u1@test.com",
            password_hash=hash_password("pw"),
            role="admin",
            approval_status="pending",
            company_id=comp.id,
        )
        u2 = User(
            email="u2@test.com",
            password_hash=hash_password("pw"),
            role="member",
            approval_status="approved",
            company_id=comp.id,
        )
        session.add_all([u1, u2])
        session.commit()

    # 1. Unfiltered list
    res_all = sa_client.get("/superadmin/users")
    assert res_all.status_code == 200
    all_users = res_all.json()
    emails = [u["email"] for u in all_users]
    assert "u1@test.com" in emails
    assert "u2@test.com" in emails

    # 2. Filter by pending
    res_pending = sa_client.get("/superadmin/users?approval_status=pending")
    assert res_pending.status_code == 200
    pending_users = res_pending.json()
    assert all(u["approval_status"] == "pending" for u in pending_users)
    assert any(u["email"] == "u1@test.com" for u in pending_users)
    assert not any(u["email"] == "u2@test.com" for u in pending_users)

    # 3. Filter by approved
    res_approved = sa_client.get("/superadmin/users?approval_status=approved")
    assert res_approved.status_code == 200
    approved_users = res_approved.json()
    assert all(u["approval_status"] == "approved" for u in approved_users)
    assert any(u["email"] == "u2@test.com" for u in approved_users)
    assert not any(u["email"] == "u1@test.com" for u in approved_users)


def test_approve_and_reject_user(db_engine):
    sa_client, _ = _create_superadmin_client(db_engine)

    with Session(db_engine) as session:
        comp = Company(name="Approve Co", status="active")
        session.add(comp)
        session.commit()
        session.refresh(comp)

        pending_user = User(
            email="to-approve@test.com",
            password_hash=hash_password("pw123"),
            role="admin",
            approval_status="pending",
            company_id=comp.id,
        )
        to_reject_user = User(
            email="to-reject@test.com",
            password_hash=hash_password("pw123"),
            role="admin",
            approval_status="pending",
            company_id=comp.id,
        )
        session.add_all([pending_user, to_reject_user])
        session.commit()
        session.refresh(pending_user)
        session.refresh(to_reject_user)
        pending_id = pending_user.id
        reject_id = to_reject_user.id

    # 1. Approve user
    res_app = sa_client.patch(f"/superadmin/users/{pending_id}/approve")
    assert res_app.status_code == 200
    assert res_app.json()["approval_status"] == "approved"

    # Verify user can log in
    anon = TestClient(app)
    login_res = anon.post("/auth/login", json={"email": "to-approve@test.com", "password": "pw123"})
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # 2. Reject user
    res_rej = sa_client.patch(f"/superadmin/users/{reject_id}/reject")
    assert res_rej.status_code == 200
    assert res_rej.json()["approval_status"] == "rejected"

    # Verify user cannot log in
    login_rej_res = anon.post("/auth/login", json={"email": "to-reject@test.com", "password": "pw123"})
    assert login_rej_res.status_code == 403
    assert login_rej_res.json()["detail"] == "Your registration has been rejected"


def test_approve_reject_nonexistent_user_returns_404(db_engine):
    sa_client, _ = _create_superadmin_client(db_engine)
    random_id = uuid.uuid4()
    assert sa_client.patch(f"/superadmin/users/{random_id}/approve").status_code == 404
    assert sa_client.patch(f"/superadmin/users/{random_id}/reject").status_code == 404


def test_list_and_suspend_and_activate_companies(db_engine):
    sa_client, _ = _create_superadmin_client(db_engine)

    with Session(db_engine) as session:
        c1 = Company(name="Company 1", status="active")
        c2 = Company(name="Company 2", status="active")
        session.add_all([c1, c2])
        session.commit()
        session.refresh(c1)
        session.refresh(c2)
        c1_id = c1.id

        user = User(
            email="admin@company1.com",
            password_hash=hash_password("pw123"),
            role="admin",
            approval_status="approved",
            company_id=c1.id,
        )
        session.add(user)
        session.commit()

    # 1. List companies
    res_list = sa_client.get("/superadmin/companies")
    assert res_list.status_code == 200
    comp_names = [c["name"] for c in res_list.json()]
    assert "Company 1" in comp_names
    assert "Company 2" in comp_names

    # 2. Suspend Company 1
    res_suspend = sa_client.patch(f"/superadmin/companies/{c1_id}/suspend")
    assert res_suspend.status_code == 200
    assert res_suspend.json()["status"] == "suspended"

    # User in Company 1 cannot log in
    anon = TestClient(app)
    login_res = anon.post("/auth/login", json={"email": "admin@company1.com", "password": "pw123"})
    assert login_res.status_code == 403
    assert login_res.json()["detail"] == "Your company has been suspended"

    # 3. Activate Company 1
    res_act = sa_client.patch(f"/superadmin/companies/{c1_id}/activate")
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "active"

    # User in Company 1 can log in again
    login_res2 = anon.post("/auth/login", json={"email": "admin@company1.com", "password": "pw123"})
    assert login_res2.status_code == 200
    assert "access_token" in login_res2.json()


def test_suspend_activate_nonexistent_company_returns_404(db_engine):
    sa_client, _ = _create_superadmin_client(db_engine)
    random_id = uuid.uuid4()
    assert sa_client.patch(f"/superadmin/companies/{random_id}/suspend").status_code == 404
    assert sa_client.patch(f"/superadmin/companies/{random_id}/activate").status_code == 404


def test_superadmin_endpoints_reject_non_superadmin_roles(client, other_client, anon_client):
    # Member client
    assert client.get("/superadmin/users").status_code == 403
    assert client.get("/superadmin/companies").status_code == 403
    assert client.patch(f"/superadmin/users/{uuid.uuid4()}/approve").status_code == 403
    assert client.patch(f"/superadmin/companies/{uuid.uuid4()}/suspend").status_code == 403

    # Anonymous client
    assert anon_client.get("/superadmin/users").status_code == 401
    assert anon_client.get("/superadmin/companies").status_code == 401


def test_end_to_end_superadmin_approval_lifecycle(db_engine):
    _override_db(db_engine)
    # 1. Bootstrap platform superadmin via CLI helper
    sa_user = create_superadmin(
        email="root@platform.internal",
        password="rootpassword",
        engine=db_engine,
    )
    sa_client = TestClient(app)
    sa_client.headers["Authorization"] = f"Bearer {create_access_token(sa_user.id)}"

    # 2. Public company admin registers
    anon_client = TestClient(app)
    reg_response = anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Ventures",
            "email": "alice@acme.com",
            "password": "alicepassword123",
            "display_name": "Alice Admin",
        },
    )
    assert reg_response.status_code == 201
    assert reg_response.json() == {"message": "Registration pending approval"}

    # 3. Alice attempts login before approval -> 403 Pending
    early_login = anon_client.post(
        "/auth/login",
        json={"email": "alice@acme.com", "password": "alicepassword123"},
    )
    assert early_login.status_code == 403
    assert early_login.json()["detail"] == "Your account is pending approval"

    # 4. Superadmin lists pending users and finds Alice
    pending_list = sa_client.get("/superadmin/users?approval_status=pending").json()
    alice_entry = next(u for u in pending_list if u["email"] == "alice@acme.com")
    assert alice_entry["company_name"] == "Acme Ventures"
    alice_id = alice_entry["id"]

    # 5. Superadmin approves Alice
    approve_res = sa_client.patch(f"/superadmin/users/{alice_id}/approve")
    assert approve_res.status_code == 200
    assert approve_res.json()["approval_status"] == "approved"

    # 6. Alice successfully logs in and accesses /auth/me
    alice_login = anon_client.post(
        "/auth/login",
        json={"email": "alice@acme.com", "password": "alicepassword123"},
    )
    assert alice_login.status_code == 200
    alice_token = alice_login.json()["access_token"]

    alice_client = TestClient(app)
    alice_client.headers["Authorization"] = f"Bearer {alice_token}"
    me_res = alice_client.get("/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "alice@acme.com"
    assert me_data["role"] == "admin"
    assert me_data["company_name"] == "Acme Ventures"
    assert me_data["approval_status"] == "approved"

    # 7. Superadmin deletes Alice (company admin)
    del_res = sa_client.delete(f"/superadmin/users/{alice_id}")
    assert del_res.status_code == 204

    # Alice can no longer log in
    alice_login_after_del = anon_client.post(
        "/auth/login",
        json={"email": "alice@acme.com", "password": "alicepassword123"},
    )
    assert alice_login_after_del.status_code == 401


def test_superadmin_delete_user_prevents_self_deletion(db_engine):
    sa_client, sa_user = _create_superadmin_client(db_engine)

    # Superadmin cannot delete self
    del_res = sa_client.delete(f"/superadmin/users/{sa_user.id}")
    assert del_res.status_code == 403
    assert del_res.json()["detail"] == "Cannot delete own account"

