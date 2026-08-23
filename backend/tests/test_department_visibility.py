import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models.company import Company
from app.models.department import Department
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from app.services.llm import TokenUsage, get_llm_provider
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _override_db


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None):
        if usage is not None:
            usage.prompt_tokens = 1
            usage.completion_tokens = 1
        yield "answer"


def _setup_test_tenancy(db_engine):
    _override_db(db_engine)
    with Session(db_engine, expire_on_commit=False) as session:
        company = Company(name="Visibility Corp", status="active")
        session.add(company)
        session.commit()

        dept_eng = Department(name="Engineering", company_id=company.id)
        dept_hr = Department(name="HR", company_id=company.id)
        session.add_all([dept_eng, dept_hr])
        session.commit()

        admin = User(
            email="admin@vis.com",
            password_hash=hash_password("pw"),
            role="admin",
            approval_status="approved",
            company_id=company.id,
            department_id=dept_eng.id,
        )
        eng_member = User(
            email="eng@vis.com",
            password_hash=hash_password("pw"),
            role="member",
            approval_status="approved",
            company_id=company.id,
            department_id=dept_eng.id,
        )
        hr_member = User(
            email="hr@vis.com",
            password_hash=hash_password("pw"),
            role="member",
            approval_status="approved",
            company_id=company.id,
            department_id=dept_hr.id,
        )
        solo_member = User(
            email="solo@vis.com",
            password_hash=hash_password("pw"),
            role="member",
            approval_status="approved",
            company_id=company.id,
            department_id=None,
        )
        session.add_all([admin, eng_member, hr_member, solo_member])
        session.commit()

    def make_client(user_id):
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {create_access_token(user_id)}"
        return c

    return {
        "admin_client": make_client(admin.id),
        "eng_client": make_client(eng_member.id),
        "hr_client": make_client(hr_member.id),
        "solo_client": make_client(solo_member.id),
        "dept_eng_id": dept_eng.id,
        "dept_hr_id": dept_hr.id,
    }


def _sources(response) -> list[dict]:
    done_block = next(block for block in response.text.split("\n\n") if block.startswith("event: done"))
    data_line = next(line for line in done_block.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))["sources"]


def test_list_documents_respects_department_and_role_visibility(db_engine, tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        env = _setup_test_tenancy(db_engine)
        admin = env["admin_client"]
        eng_user = env["eng_client"]
        hr_user = env["hr_client"]
        solo_user = env["solo_client"]

        # Admin uploads company-wide document
        admin.post(
            "/documents",
            files={"file": ("handbook.md", b"# Handbook", "text/markdown")},
            data={"visibility": "company"},
        )

        # Admin uploads engineering-only document
        admin.post(
            "/documents",
            files={"file": ("eng_spec.md", b"# Engineering Spec", "text/markdown")},
            data={"visibility": "department", "department_id": str(env["dept_eng_id"])},
        )

        # Admin uploads HR-only document
        admin.post(
            "/documents",
            files={"file": ("hr_policy.md", b"# HR Policy", "text/markdown")},
            data={"visibility": "department", "department_id": str(env["dept_hr_id"])},
        )

        # 1. Admin sees all 3 docs
        admin_docs = [d["filename"] for d in admin.get("/documents").json()]
        assert "handbook.md" in admin_docs
        assert "eng_spec.md" in admin_docs
        assert "hr_policy.md" in admin_docs

        # 2. Engineering member sees handbook + eng_spec (not hr_policy)
        eng_docs = [d["filename"] for d in eng_user.get("/documents").json()]
        assert "handbook.md" in eng_docs
        assert "eng_spec.md" in eng_docs
        assert "hr_policy.md" not in eng_docs

        # 3. HR member sees handbook + hr_policy (not eng_spec)
        hr_docs = [d["filename"] for d in hr_user.get("/documents").json()]
        assert "handbook.md" in hr_docs
        assert "hr_policy.md" in hr_docs
        assert "eng_spec.md" not in hr_docs

        # 4. Solo member with no department sees only company-wide doc
        solo_docs = [d["filename"] for d in solo_user.get("/documents").json()]
        assert "handbook.md" in solo_docs
        assert "eng_spec.md" not in solo_docs
        assert "hr_policy.md" not in solo_docs
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_vector_store, None)


def test_chat_retrieval_respects_department_and_role_visibility(db_engine, tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        env = _setup_test_tenancy(db_engine)
        admin = env["admin_client"]
        eng_user = env["eng_client"]
        hr_user = env["hr_client"]
        solo_user = env["solo_client"]

        # Admin uploads company-wide document
        admin.post(
            "/documents",
            files={"file": ("handbook.md", b"# Handbook\n\nCompany handbook rules", "text/markdown")},
            data={"visibility": "company"},
        )

        # Admin uploads engineering-only document
        admin.post(
            "/documents",
            files={"file": ("eng_spec.md", b"# Engineering Spec\n\nEngineering system spec", "text/markdown")},
            data={"visibility": "department", "department_id": str(env["dept_eng_id"])},
        )

        # Admin uploads HR-only document
        admin.post(
            "/documents",
            files={"file": ("hr_policy.md", b"# HR Policy\n\nHR policy rules", "text/markdown")},
            data={"visibility": "department", "department_id": str(env["dept_hr_id"])},
        )

        # 1. Admin chat retrieves all
        admin_sources = [s["filename"] for s in _sources(admin.post("/chat", json={"message": "specs"}))]
        assert "handbook.md" in admin_sources
        assert "eng_spec.md" in admin_sources
        assert "hr_policy.md" in admin_sources

        # 2. Engineering member retrieves handbook + eng_spec, but NOT hr_policy
        eng_sources = [s["filename"] for s in _sources(eng_user.post("/chat", json={"message": "specs"}))]
        assert "handbook.md" in eng_sources
        assert "eng_spec.md" in eng_sources
        assert "hr_policy.md" not in eng_sources

        # 3. HR member retrieves handbook + hr_policy, but NOT eng_spec
        hr_sources = [s["filename"] for s in _sources(hr_user.post("/chat", json={"message": "specs"}))]
        assert "handbook.md" in hr_sources
        assert "hr_policy.md" in hr_sources
        assert "eng_spec.md" not in hr_sources

        # 4. Solo member retrieves only handbook
        solo_sources = [s["filename"] for s in _sources(solo_user.post("/chat", json={"message": "specs"}))]
        assert "handbook.md" in solo_sources
        assert "eng_spec.md" not in solo_sources
        assert "hr_policy.md" not in solo_sources
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_vector_store, None)


def test_upload_rejects_department_visibility_without_a_department(db_engine, tmp_path):
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(persist_dir=str(tmp_path))
    try:
        env = _setup_test_tenancy(db_engine)
        admin = env["admin_client"]
        response = admin.post(
            "/documents",
            files={"file": ("a.md", b"# A\n\ncontent", "text/markdown")},
            data={"visibility": "department"},
        )
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_vector_store, None)

    assert response.status_code == 400
    assert "department is required" in response.json()["detail"].lower()
