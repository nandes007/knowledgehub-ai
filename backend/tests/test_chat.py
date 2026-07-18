from fastapi.testclient import TestClient

from app.main import app
from app.services.llm import get_llm_provider
from ingestion.chunk import chunk_markdown
from ingestion.index import VectorStore, get_vector_store


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer(self, prompt: str) -> str:
        return "Employees get 20 days of PTO per year."


_VOCAB = ["vacation", "pto", "policy", "days", "onboarding", "laptop"]


def _bag_of_words(text: str) -> list[float]:
    words = set(text.lower().split())
    return [1.0 if w in words else 0.0 for w in _VOCAB]


def test_chat_returns_grounded_answer_with_sources(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    fake_llm = _FakeLLM()
    chunks = chunk_markdown("# Vacation Policy\n\nEmployees get 20 days of PTO per year.")
    embeddings = fake_llm.embed_texts([c.text for c in chunks])
    store.upsert_chunks(
        document_id="doc-1",
        user_id="seed-user",
        filename="policy.md",
        chunks=chunks,
        embeddings=embeddings,
    )

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "20 days of PTO" in body["answer"]
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["filename"] == "policy.md"
    assert body["sources"][0]["document_id"] == "doc-1"


def test_chat_requires_a_message(tmp_path):
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(persist_dir=str(tmp_path))
    try:
        client = TestClient(app)
        response = client.post("/chat", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
