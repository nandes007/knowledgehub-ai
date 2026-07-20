import json
import uuid

from app.main import app
from app.services.llm import get_llm_provider
from ingestion.chunk import chunk_markdown
from ingestion.index import VectorStore, get_vector_store

_VOCAB = ["vacation", "pto", "policy", "days", "onboarding", "laptop", "sick"]
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


class _RecordingLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, prompt: str):
        self.prompts.append(prompt)
        yield "20 days"


def _bag_of_words(text: str) -> list[float]:
    words = set(text.lower().split())
    return [1.0 if w in words else 0.0 for w in _VOCAB]


def _seeded_store(tmp_path, user_id) -> VectorStore:
    store = VectorStore(persist_dir=str(tmp_path))
    chunks = chunk_markdown("# Vacation Policy\n\nEmployees get 20 days of PTO per year.")
    embeddings = [_bag_of_words(c.text) for c in chunks]
    store.upsert_chunks(
        document_id="doc-1",
        user_id=str(user_id),
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


def _override(llm) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: llm


def _override_store(store: VectorStore) -> None:
    app.dependency_overrides[get_vector_store] = lambda: store


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_llm_provider, None)
    app.dependency_overrides.pop(get_vector_store, None)


def test_chat_creates_a_conversation_when_none_given(client, tmp_path, test_user_id):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id))
    try:
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        _clear_overrides()

    assert response.status_code == 200
    done = next(data for event, data in _parse_sse_events(response.text) if event == "done")
    assert done["sources"][0]["filename"] == "policy.md"
    assert uuid.UUID(done["conversation_id"])
    assert uuid.UUID(done["message_id"])


def test_chat_persists_user_and_assistant_messages(client, tmp_path, test_user_id):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id))
    try:
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        _clear_overrides()

    conversation_id = _parse_sse_events(response.text)[-1][1]["conversation_id"]
    messages = client.get(f"/conversations/{conversation_id}/messages").json()

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "How many vacation days do I get?"
    assert messages[1]["content"] == "".join(_ANSWER_TOKENS)
    assert messages[1]["sources"][0]["filename"] == "policy.md"


def test_chat_includes_history_in_the_prompt_for_follow_ups(client, tmp_path, test_user_id):
    store = _seeded_store(tmp_path, test_user_id)
    recording_llm = _RecordingLLM()
    _override(recording_llm)
    _override_store(store)
    try:
        first = client.post("/chat", json={"message": "How many vacation days do I get?"})
        conversation_id = _parse_sse_events(first.text)[-1][1]["conversation_id"]

        client.post(
            "/chat",
            json={"message": "And how many sick days?", "conversation_id": conversation_id},
        )
    finally:
        _clear_overrides()

    assert len(recording_llm.prompts) == 2
    second_prompt = recording_llm.prompts[1]
    assert "How many vacation days do I get?" in second_prompt
    assert "20 days" in second_prompt


def test_chat_emits_error_event_on_llm_failure_mid_stream(client, tmp_path, test_user_id):
    _override(_FailingFakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id))
    try:
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        _clear_overrides()

    events = _parse_sse_events(response.text)
    assert events[0] == ("token", {"text": "Emplo"})
    assert events[-1][0] == "error"
    assert not any(event == "done" for event, _ in events)


def test_chat_with_unknown_conversation_id_returns_404(client, tmp_path, test_user_id):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id))
    try:
        response = client.post(
            "/chat",
            json={"message": "hi", "conversation_id": str(uuid.uuid4())},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 404


def test_chat_requires_a_message(client, tmp_path, test_user_id):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id))
    try:
        response = client.post("/chat", json={})
    finally:
        _clear_overrides()

    assert response.status_code == 422
