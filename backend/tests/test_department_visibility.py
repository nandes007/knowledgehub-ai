import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_engine, get_session
from app.main import app
from app.services.llm import TokenUsage, get_llm_provider
from ingestion.index import VectorStore, get_vector_store


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None):
        if usage is not None:
            usage.prompt_tokens = 1
            usage.completion_tokens = 1
        yield "answer"


def _client_for(db_engine, email: str, department: str | None) -> TestClient:
    def _get_session_override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_engine] = lambda: db_engine
    test_client = TestClient(app)
    response = test_client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "department": department},
    )
    test_client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return test_client


def _sources(response) -> list[dict]:
    done_block = next(block for block in response.text.split("\n\n") if block.startswith("event: done"))
    data_line = next(line for line in done_block.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))["sources"]


def test_department_only_doc_is_invisible_to_a_user_in_another_department(db_engine, tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        eng_client = _client_for(db_engine, "eng@example.com", "engineering")
        hr_client = _client_for(db_engine, "hr@example.com", "hr")

        eng_client.post(
            "/documents",
            files={"file": ("bands.md", b"# Salary Bands\n\nEngineering pay bands.", "text/markdown")},
            data={"department": "engineering", "visibility": "department"},
        )

        cross_dept = hr_client.post("/chat", json={"message": "What are the salary bands?"})
        same_dept = eng_client.post("/chat", json={"message": "What are the salary bands?"})
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_vector_store, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)

    assert _sources(cross_dept) == []
    assert any(s["filename"] == "bands.md" for s in _sources(same_dept))


def test_company_wide_doc_is_visible_across_departments(db_engine, tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        eng_client = _client_for(db_engine, "eng2@example.com", "engineering")
        hr_client = _client_for(db_engine, "hr2@example.com", "hr")

        eng_client.post(
            "/documents",
            files={"file": ("handbook.md", b"# Handbook\n\nCompany-wide holiday schedule.", "text/markdown")},
        )

        response = hr_client.post("/chat", json={"message": "What is the holiday schedule?"})
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_vector_store, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)

    assert any(s["filename"] == "handbook.md" for s in _sources(response))


def test_upload_rejects_department_visibility_without_a_department(db_engine, tmp_path):
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(persist_dir=str(tmp_path))
    try:
        client = _client_for(db_engine, "solo@example.com", None)
        response = client.post(
            "/documents",
            files={"file": ("a.md", b"# A\n\ncontent", "text/markdown")},
            data={"visibility": "department"},
        )
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_vector_store, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)

    assert response.status_code == 400
