import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models.company import Company
from app.models.department import Department
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from tests.conftest import _override_db


def _setup_company_admin_and_dept(
    db_engine,
    company_name: str = "Acme Corp",
    admin_email: str = "admin@acme.com",
    dept_name: str = "Engineering",
) -> tuple[TestClient, User, Department, Company]:
    _override_db(db_engine)
    with Session(db_engine, expire_on_commit=False) as session:
        company = Company(name=company_name, status="active")
        session.add(company)
        session.commit()

        dept = Department(name=dept_name, company_id=company.id)
        session.add(dept)
        session.commit()

        admin = User(
            email=admin_email,
            password_hash=hash_password("adminpw123"),
            role="admin",
            approval_status="approved",
            company_id=company.id,
            department_id=dept.id,
        )
        session.add(admin)
        session.commit()
        admin_id = admin.id

    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(admin_id)}"
    return client, admin, dept, company


def test_post_users_creates_approved_member(db_engine):
    client, admin, dept, company = _setup_company_admin_and_dept(db_engine)

    payload = {
        "email": "engineer@acme.com",
        "password": "engpassword123",
        "display_name": "Bob Engineer",
        "department_id": str(dept.id),
        "role": "member",
    }
    response = client.post("/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "engineer@acme.com"
    assert data["display_name"] == "Bob Engineer"
    assert data["role"] == "member"
    assert data["approval_status"] == "approved"
    assert data["company_id"] == str(company.id)
    assert data["department_id"] == str(dept.id)
    assert data["department_name"] == "Engineering"

    # Verify newly created user can log in immediately
    anon = TestClient(app)
    login_res = anon.post("/auth/login", json={"email": "engineer@acme.com", "password": "engpassword123"})
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


def test_post_users_requires_department_id(db_engine):
    client, _, _, _ = _setup_company_admin_and_dept(db_engine)

    # Missing department_id
    payload = {
        "email": "nodept@acme.com",
        "password": "password123",
        "display_name": "No Dept",
    }
    response = client.post("/users", json=payload)
    assert response.status_code == 422


def test_post_users_rejects_duplicate_email(db_engine):
    client, _, dept, _ = _setup_company_admin_and_dept(db_engine)

    payload = {
        "email": "dup@acme.com",
        "password": "password123",
        "department_id": str(dept.id),
    }
    res1 = client.post("/users", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/users", json=payload)
    assert res2.status_code == 409
    assert res2.json()["detail"] == "Email already registered"


def test_post_users_rejects_foreign_department(db_engine):
    client, _, _, _ = _setup_company_admin_and_dept(db_engine, company_name="Company 1")

    # Create Department in another company
    with Session(db_engine, expire_on_commit=False) as session:
        other_comp = Company(name="Company 2", status="active")
        session.add(other_comp)
        session.commit()

        foreign_dept = Department(name="Marketing", company_id=other_comp.id)
        session.add(foreign_dept)
        session.commit()
        foreign_dept_id = foreign_dept.id

    payload = {
        "email": "foreign@acme.com",
        "password": "password123",
        "department_id": str(foreign_dept_id),
    }
    response = client.post("/users", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Department not found"


def test_get_users_returns_only_admin_company_users(db_engine):
    client1, _, dept1, comp1 = _setup_company_admin_and_dept(db_engine, company_name="Company 1", admin_email="admin1@c1.com")
    client2, _, dept2, comp2 = _setup_company_admin_and_dept(db_engine, company_name="Company 2", admin_email="admin2@c2.com")

    # Add user to company 1
    client1.post("/users", json={"email": "user1@c1.com", "password": "pw", "department_id": str(dept1.id)})

    # Add user to company 2
    client2.post("/users", json={"email": "user2@c2.com", "password": "pw", "department_id": str(dept2.id)})

    # List company 1
    res1 = client1.get("/users")
    assert res1.status_code == 200
    c1_emails = [u["email"] for u in res1.json()]
    assert "admin1@c1.com" in c1_emails
    assert "user1@c1.com" in c1_emails
    assert "user2@c2.com" not in c1_emails
    assert "admin2@c2.com" not in c1_emails

    # List company 2
    res2 = client2.get("/users")
    assert res2.status_code == 200
    c2_emails = [u["email"] for u in res2.json()]
    assert "admin2@c2.com" in c2_emails
    assert "user2@c2.com" in c2_emails
    assert "user1@c1.com" not in c2_emails
    assert "admin1@c1.com" not in c2_emails


def test_patch_user_updates_fields(db_engine):
    client, _, dept, _ = _setup_company_admin_and_dept(db_engine)

    # Create new department in same company
    with Session(db_engine, expire_on_commit=False) as session:
        dept2 = Department(name="Product", company_id=dept.company_id)
        session.add(dept2)
        session.commit()
        dept2_id = dept2.id

    create_res = client.post(
        "/users",
        json={"email": "charlie@acme.com", "password": "pw", "display_name": "Charlie", "department_id": str(dept.id)},
    )
    user_id = create_res.json()["id"]

    # Patch display_name, department_id, and promote to admin
    patch_res = client.patch(
        f"/users/{user_id}",
        json={"display_name": "Charlie Product Lead", "department_id": str(dept2_id), "role": "admin"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["display_name"] == "Charlie Product Lead"
    assert data["department_id"] == str(dept2_id)
    assert data["department_name"] == "Product"
    assert data["role"] == "admin"


def test_patch_user_cross_company_returns_404(db_engine):
    client1, _, dept1, _ = _setup_company_admin_and_dept(db_engine, company_name="Company A", admin_email="adminA@a.com")
    client2, _, dept2, _ = _setup_company_admin_and_dept(db_engine, company_name="Company B", admin_email="adminB@b.com")

    create_res = client2.post(
        "/users",
        json={"email": "target@b.com", "password": "pw", "department_id": str(dept2.id)},
    )
    b_user_id = create_res.json()["id"]

    # Admin A tries to modify user in Company B
    patch_res = client1.patch(f"/users/{b_user_id}", json={"display_name": "Hacked Name"})
    assert patch_res.status_code == 404
    assert patch_res.json()["detail"] == "User not found"


def test_delete_user_in_same_company(db_engine):
    client, _, dept, _ = _setup_company_admin_and_dept(db_engine)

    create_res = client.post(
        "/users",
        json={"email": "todelete@acme.com", "password": "pw123", "department_id": str(dept.id)},
    )
    user_id = create_res.json()["id"]

    del_res = client.delete(f"/users/{user_id}")
    assert del_res.status_code == 204

    # Verify user is gone from GET /users
    users = client.get("/users").json()
    assert not any(u["id"] == user_id for u in users)

    # Verify user cannot log in
    anon = TestClient(app)
    login_res = anon.post("/auth/login", json={"email": "todelete@acme.com", "password": "pw123"})
    assert login_res.status_code == 401


def test_delete_user_cross_company_returns_404(db_engine):
    client1, _, dept1, _ = _setup_company_admin_and_dept(db_engine, company_name="Company 1", admin_email="admin1@1.com")
    client2, _, dept2, _ = _setup_company_admin_and_dept(db_engine, company_name="Company 2", admin_email="admin2@2.com")

    create_res = client2.post(
        "/users",
        json={"email": "victim@2.com", "password": "pw", "department_id": str(dept2.id)},
    )
    victim_id = create_res.json()["id"]

    # Admin 1 tries to delete user in Company 2
    del_res = client1.delete(f"/users/{victim_id}")
    assert del_res.status_code == 404
    assert del_res.json()["detail"] == "User not found"


def test_users_endpoints_reject_member_role(client, anon_client):
    # Standard client fixture has 'member' role
    assert client.get("/users").status_code == 403
    assert client.post("/users", json={"email": "m@m.com", "password": "pw", "department_id": str(uuid.uuid4())}).status_code == 403
    assert client.patch(f"/users/{uuid.uuid4()}", json={"display_name": "x"}).status_code == 403
    assert client.delete(f"/users/{uuid.uuid4()}").status_code == 403

    # Anonymous client
    assert anon_client.get("/users").status_code == 401
    assert anon_client.post("/users", json={}).status_code == 401


def test_end_to_end_admin_user_crud_flow(db_engine):
    admin_client, _, dept, comp = _setup_company_admin_and_dept(db_engine)

    # 1. Admin creates a new member
    create_res = admin_client.post(
        "/users",
        json={
            "email": "dev@acme.com",
            "password": "initialpassword",
            "display_name": "Dev User",
            "department_id": str(dept.id),
        },
    )
    assert create_res.status_code == 201
    dev_id = create_res.json()["id"]

    # 2. Admin lists users and finds newly created user
    list_res = admin_client.get("/users")
    assert list_res.status_code == 200
    assert any(u["id"] == dev_id for u in list_res.json())

    # 3. Admin updates user display_name and role
    update_res = admin_client.patch(
        f"/users/{dev_id}",
        json={"display_name": "Senior Dev", "role": "admin"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["display_name"] == "Senior Dev"
    assert update_res.json()["role"] == "admin"

    # 4. User logs in successfully and inspects /auth/me
    anon_client = TestClient(app)
    login_res = anon_client.post(
        "/auth/login",
        json={"email": "dev@acme.com", "password": "initialpassword"},
    )
    assert login_res.status_code == 200
    dev_token = login_res.json()["access_token"]

    dev_client = TestClient(app)
    dev_client.headers["Authorization"] = f"Bearer {dev_token}"
    me_res = dev_client.get("/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["display_name"] == "Senior Dev"
    assert me_res.json()["role"] == "admin"
    assert me_res.json()["company_name"] == "Acme Corp"

    # 5. Admin deletes the user
    del_res = admin_client.delete(f"/users/{dev_id}")
    assert del_res.status_code == 204

    # 6. Deleted user cannot log in
    login_after_del = anon_client.post(
        "/auth/login",
        json={"email": "dev@acme.com", "password": "initialpassword"},
    )
    assert login_after_del.status_code == 401
