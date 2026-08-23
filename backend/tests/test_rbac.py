from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.deps import AdminDep, CurrentUserDep, SuperAdminDep, require_role
from app.main import app
from app.models.company import Company
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from tests.conftest import _override_db

# Test router to exercise the RBAC and role dependencies
rbac_test_router = APIRouter(prefix="/test-rbac", tags=["test-rbac"])


@rbac_test_router.get("/current-user")
def endpoint_current_user(current_user: CurrentUserDep):
    return {"email": current_user.email, "role": current_user.role}


@rbac_test_router.get("/admin-only")
def endpoint_admin_only(current_user: AdminDep):
    return {"email": current_user.email, "role": current_user.role}


@rbac_test_router.get("/superadmin-only")
def endpoint_superadmin_only(current_user: SuperAdminDep):
    return {"email": current_user.email, "role": current_user.role}


@rbac_test_router.get("/admin-exclusive")
def endpoint_admin_exclusive(current_user: Annotated[User, Depends(require_role("admin"))]):
    return {"email": current_user.email, "role": current_user.role}


app.include_router(rbac_test_router)


def _create_user_with_token(
    db_engine,
    email: str,
    role: str = "member",
    approval_status: str = "approved",
    company_name: str | None = "Test Company",
    company_status: str = "active",
) -> tuple[TestClient, User]:
    _override_db(db_engine)
    with Session(db_engine) as session:
        company_id = None
        if company_name is not None:
            company = Company(name=company_name, status=company_status)
            session.add(company)
            session.commit()
            session.refresh(company)
            company_id = company.id

        user = User(
            email=email,
            password_hash=hash_password("password123"),
            role=role,
            approval_status=approval_status,
            company_id=company_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(user_id)}"
    return client, user


def test_current_user_dep_allows_approved_member(db_engine):
    client, _ = _create_user_with_token(db_engine, "member@example.com", role="member")
    response = client.get("/test-rbac/current-user")
    assert response.status_code == 200
    assert response.json() == {"email": "member@example.com", "role": "member"}


def test_get_current_user_rejects_pending_user(db_engine):
    client, _ = _create_user_with_token(
        db_engine, "pending@example.com", role="member", approval_status="pending"
    )
    response = client.get("/test-rbac/current-user")
    assert response.status_code == 403
    assert response.json()["detail"] == "Your account is pending approval"


def test_get_current_user_rejects_rejected_user(db_engine):
    client, _ = _create_user_with_token(
        db_engine, "rejected@example.com", role="member", approval_status="rejected"
    )
    response = client.get("/test-rbac/current-user")
    assert response.status_code == 403
    assert response.json()["detail"] == "Your registration has been rejected"


def test_get_current_user_rejects_suspended_company(db_engine):
    client, _ = _create_user_with_token(
        db_engine,
        "suspended@example.com",
        role="member",
        approval_status="approved",
        company_name="Suspended Co",
        company_status="suspended",
    )
    response = client.get("/test-rbac/current-user")
    assert response.status_code == 403
    assert response.json()["detail"] == "Your company has been suspended"


def test_superadmin_without_company_passes_get_current_user(db_engine):
    client, _ = _create_user_with_token(
        db_engine,
        "superadmin@platform.internal",
        role="superadmin",
        approval_status="approved",
        company_name=None,
    )
    response = client.get("/test-rbac/current-user")
    assert response.status_code == 200
    assert response.json() == {"email": "superadmin@platform.internal", "role": "superadmin"}


def test_superadmin_dep_allows_superadmin(db_engine):
    client, _ = _create_user_with_token(
        db_engine,
        "superadmin@platform.internal",
        role="superadmin",
        approval_status="approved",
        company_name=None,
    )
    response = client.get("/test-rbac/superadmin-only")
    assert response.status_code == 200
    assert response.json()["role"] == "superadmin"


def test_superadmin_dep_rejects_admin(db_engine):
    client, _ = _create_user_with_token(
        db_engine, "admin@example.com", role="admin", approval_status="approved", company_name="Admin Co"
    )
    response = client.get("/test-rbac/superadmin-only")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_superadmin_dep_rejects_member(db_engine):
    client, _ = _create_user_with_token(
        db_engine, "member@example.com", role="member", approval_status="approved", company_name="Member Co"
    )
    response = client.get("/test-rbac/superadmin-only")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_admin_dep_allows_admin(db_engine):
    client, _ = _create_user_with_token(
        db_engine, "admin@example.com", role="admin", approval_status="approved", company_name="Admin Co"
    )
    response = client.get("/test-rbac/admin-only")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_dep_allows_superadmin(db_engine):
    client, _ = _create_user_with_token(
        db_engine,
        "superadmin@platform.internal",
        role="superadmin",
        approval_status="approved",
        company_name=None,
    )
    response = client.get("/test-rbac/admin-only")
    assert response.status_code == 200
    assert response.json()["role"] == "superadmin"


def test_admin_dep_rejects_member(db_engine):
    client, _ = _create_user_with_token(
        db_engine, "member@example.com", role="member", approval_status="approved", company_name="Member Co"
    )
    response = client.get("/test-rbac/admin-only")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_require_role_factory_role_filter(db_engine):
    client_admin, _ = _create_user_with_token(
        db_engine, "admin@example.com", role="admin", approval_status="approved", company_name="Admin Co"
    )
    response_ok = client_admin.get("/test-rbac/admin-exclusive")
    assert response_ok.status_code == 200
    assert response_ok.json() == {"email": "admin@example.com", "role": "admin"}

    client_superadmin, _ = _create_user_with_token(
        db_engine, "superadmin@example.com", role="superadmin", approval_status="approved", company_name=None
    )
    response_forbidden = client_superadmin.get("/test-rbac/admin-exclusive")
    assert response_forbidden.status_code == 403
    assert response_forbidden.json()["detail"] == "Insufficient permissions"

    client_member, _ = _create_user_with_token(
        db_engine, "member@example.com", role="member", approval_status="approved", company_name="Member Co"
    )
    response_forbidden2 = client_member.get("/test-rbac/admin-exclusive")
    assert response_forbidden2.status_code == 403
    assert response_forbidden2.json()["detail"] == "Insufficient permissions"


def test_unauthenticated_request_returns_401():
    anon_client = TestClient(app)
    response = anon_client.get("/test-rbac/current-user")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
