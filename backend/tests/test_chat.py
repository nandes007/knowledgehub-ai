import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm import get_llm_provider
from ingestion.chunk import chunk_markdown
from ingestion.index import VectorStore, get_vector_store

_VOCAB = ["vacation", "pto", "policy", "days", "onboarding", "laptop"]
_ANSWER_TOKENS = ["Employees ", "get ", "20 ", "days ", "of ", "PTO ", "per ", "year."]


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, prompt: str):
        yield from _ANSWER_TOKENS


class _FailingFakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, prompt: str):
        yield "Emplo"
        raise RuntimeError("upstream LLM timed out")


def _bag_of_words(text: str) -> list[float]:
    words = set(text.lower().split())
    return [1.0 if w in words else 0.0 for w in _VOCAB]


def _seeded_store(tmp_path) -> VectorStore:
    store = VectorStore(persist_dir=str(tmp_path))
    chunks = chunk_markdown("# Vacation Policy\n\nEmployees get 20 days of PTO per year.")
    embeddings = [_bag_of_words(c.text) for c in chunks]
    store.upsert_chunks(
        document_id="doc-1",
        user_id="seed-user",
        filename="policy.md",
        chunks=chunks,
        embeddings=embeddings,
    )
    return store


def _parse_sse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def test_chat_streams_tokens_then_a_done_event_with_sources(tmp_path):
    store = _seeded_store(tmp_path)
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(response.text)
    token_events = [data for event, data in events if event == "token"]
    done_events = [data for event, data in events if event == "done"]

    assert [e["text"] for e in token_events] == _ANSWER_TOKENS
    assert len(done_events) == 1
    assert done_events[0]["sources"][0]["filename"] == "policy.md"
    assert done_events[0]["sources"][0]["document_id"] == "doc-1"


def test_chat_emits_error_event_on_llm_failure_mid_stream(tmp_path):
    store = _seeded_store(tmp_path)
    app.dependency_overrides[get_llm_provider] = lambda: _FailingFakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        app.dependency_overrides.clear()

    events = _parse_sse_events(response.text)
    assert events[0] == ("token", {"text": "Emplo"})
    assert events[-1][0] == "error"
    assert "upstream LLM timed out" in events[-1][1]["message"]
    assert not any(event == "done" for event, _ in events)


def test_chat_requires_a_message(tmp_path):
    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(persist_dir=str(tmp_path))
    try:
        client = TestClient(app)
        response = client.post("/chat", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
