from app.config import settings
from app.main import app
from app.rate_limit import limiter
from app.services.llm import get_llm_provider
from ingestion.index import VectorStore, get_vector_store


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def generate_answer_stream(self, prompt: str, *, usage=None):
        yield "hi"


def _override(llm) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: llm


def _override_store(store: VectorStore) -> None:
    app.dependency_overrides[get_vector_store] = lambda: store


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_llm_provider, None)
    app.dependency_overrides.pop(get_vector_store, None)
    limiter.reset()


def test_chat_returns_429_after_exceeding_the_per_user_limit(client, tmp_path):
    _override(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        responses = [client.post("/chat", json={"message": "hi"}) for _ in range(21)]
    finally:
        _clear_overrides()

    assert responses[-1].status_code == 429
    assert any(r.status_code == 200 for r in responses)


def test_upload_document_returns_429_after_exceeding_the_per_user_limit(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        responses = [
            client.post(
                "/documents",
                files={"file": (f"doc{i}.md", f"# Doc {i}\n\ncontent {i}".encode(), "text/markdown")},
            )
            for i in range(11)
        ]
    finally:
        _clear_overrides()

    assert responses[-1].status_code == 429
    assert any(r.status_code == 202 for r in responses)
