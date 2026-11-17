import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models.company import Company
from app.models.department import Department
from app.models.membership import Membership
from app.models.user import User
from app.services.auth import hash_password
from tests.conftest import _override_db, client_for


def _setup_company_and_users(db_engine):
    _override_db(db_engine)
    with Session(db_engine, expire_on_commit=False) as session:
        company_a = Company(name="Acme Corp", slug="acme-corp", status="active")
        company_b = Company(name="Beta Inc", slug="beta-inc", status="active")
        session.add(company_a)
        session.add(company_b)
        session.commit()

        dept_a = Department(name="Engineering", company_id=company_a.id)
        dept_b = Department(name="Design", company_id=company_b.id)
        session.add(dept_a)
        session.add(dept_b)
        session.commit()

        users = {
            name: User(email=f"{name}@example.com", password_hash=hash_password("pw123456"))
            for name in ("admin_a", "admin_b", "member_a")
        }
        session.add_all(users.values())
        session.commit()
        session.add_all(
            [
                Membership(user_id=users["admin_a"].id, company_id=company_a.id, role="admin", department_id=dept_a.id),
                Membership(user_id=users["admin_b"].id, company_id=company_b.id, role="admin", department_id=dept_b.id),
                Membership(user_id=users["member_a"].id, company_id=company_a.id, role="member", department_id=dept_a.id),
            ]
        )
        session.commit()

        return {
            "company_a": company_a,
            "company_b": company_b,
            "dept_a": dept_a,
            "dept_b": dept_b,
            **users,
        }


def _client(entities, name: str) -> TestClient:
    """Signed in as that user, scoped to their own company."""
    return client_for(entities[name].id, "acme-corp" if name.endswith("_a") else "beta-inc")


def test_create_department_success(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "admin_a")

    response = client.post("/departments", json={"name": "Marketing"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Marketing"
    assert data["company_id"] == str(entities["company_a"].id)
    assert "id" in data
    assert "created_at" in data

    # Verify DB persistence
    with Session(db_engine) as session:
        dept = session.exec(select(Department).where(Department.name == "Marketing")).first()
        assert dept is not None
        assert dept.company_id == entities["company_a"].id


def test_create_department_duplicate_name_conflict(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "admin_a")

    # Already has "Engineering"
    response = client.post("/departments", json={"name": "Engineering"})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_create_department_same_name_different_company_allowed(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "admin_b")

    # Company B creating "Engineering" should succeed even though Company A has "Engineering"
    response = client.post("/departments", json={"name": "Engineering"})
    assert response.status_code == 201
    assert response.json()["company_id"] == str(entities["company_b"].id)


def test_list_departments_scoped_to_company(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "admin_a")

    response = client.get("/departments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Engineering"
    assert data[0]["company_id"] == str(entities["company_a"].id)


def test_delete_department_success(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "admin_a")

    dept_id = entities["dept_a"].id
    response = client.delete(f"/departments/{dept_id}")
    assert response.status_code == 204

    with Session(db_engine) as session:
        dept = session.get(Department, dept_id)
        assert dept is None


def test_delete_department_not_found(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "admin_a")

    random_id = uuid.uuid4()
    response = client.delete(f"/departments/{random_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Department not found"


def test_delete_department_cross_company_isolation(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "admin_a")

    dept_b_id = entities["dept_b"].id
    response = client.delete(f"/departments/{dept_b_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Department not found"

    # Verify Dept B still exists in DB
    with Session(db_engine) as session:
        dept = session.get(Department, dept_b_id)
        assert dept is not None


def test_departments_non_admin_forbidden(db_engine):
    entities = _setup_company_and_users(db_engine)
    client = _client(entities, "member_a")

    assert client.post("/departments", json={"name": "Ops"}).status_code == 403
    assert client.get("/departments").status_code == 403
    assert client.delete(f"/departments/{entities['dept_a'].id}").status_code == 403


def test_departments_unauthenticated_unauthorized(db_engine):
    _setup_company_and_users(db_engine)
    client = TestClient(app, base_url="http://testserver/companies/acme-corp")

    assert client.post("/departments", json={"name": "Ops"}).status_code == 401
    assert client.get("/departments").status_code == 401
    assert client.delete(f"/departments/{uuid.uuid4()}").status_code == 401
