import json
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models.company import Company
from app.models.message import Message
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from app.services.llm import TokenUsage, get_llm_provider
from ingestion.chunk import chunk_markdown
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _override_db

_VOCAB = ["vacation", "pto", "policy", "days", "onboarding", "laptop", "sick", "secret", "alpha", "beta"]
_ANSWER_TOKENS = ["Employees ", "get ", "20 ", "days ", "of ", "PTO ", "per ", "year."]


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None):
        if usage is not None:
            usage.prompt_tokens = 100
            usage.completion_tokens = 8
        yield from _ANSWER_TOKENS


class _FailingFakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None):
        yield "Emplo"
        raise RuntimeError("upstream LLM timed out")


class _RecordingLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None):
        self.prompts.append(prompt)
        yield "20 days"


def _bag_of_words(text: str) -> list[float]:
    words = set(text.lower().split())
    return [1.0 if w in words else 0.0 for w in _VOCAB]


def _seeded_store(tmp_path, user_id, db_engine=None) -> VectorStore:
    store = VectorStore(persist_dir=str(tmp_path))
    company_id = "comp-1"
    if db_engine is not None:
        with Session(db_engine) as session:
            user = session.get(User, user_id)
            if user and user.company_id:
                company_id = str(user.company_id)

    chunks = chunk_markdown("# Vacation Policy\n\nEmployees get 20 days of PTO per year.")
    embeddings = [_bag_of_words(c.text) for c in chunks]
    store.upsert_chunks(
        document_id="doc-1",
        user_id=str(user_id),
        company_id=company_id,
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


def test_chat_creates_a_conversation_when_none_given(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        _clear_overrides()

    assert response.status_code == 200
    done = next(data for event, data in _parse_sse_events(response.text) if event == "done")
    assert done["sources"][0]["filename"] == "policy.md"
    assert uuid.UUID(done["conversation_id"])
    assert uuid.UUID(done["message_id"])


def test_chat_persists_user_and_assistant_messages(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
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


def test_chat_stores_token_count_on_assistant_message(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        _clear_overrides()

    conversation_id = uuid.UUID(_parse_sse_events(response.text)[-1][1]["conversation_id"])

    with Session(db_engine) as session:
        assistant_message = session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.role == "assistant")
        ).one()

    assert assistant_message.token_count == 108


def test_chat_includes_history_and_dynamic_company_prompt(client, tmp_path, test_user_id, db_engine):
    store = _seeded_store(tmp_path, test_user_id, db_engine)
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
    first_prompt = recording_llm.prompts[0]
    # Check that company name from DB ("Test Company") is dynamically formatted
    assert "assistant for Test Company" in first_prompt
    assert "Nandes Tech" not in first_prompt

    second_prompt = recording_llm.prompts[1]
    assert "How many vacation days do I get?" in second_prompt
    assert "20 days" in second_prompt


def test_cross_company_chat_never_surfaces_other_company_documents(db_engine, tmp_path):
    _override_db(db_engine)
    with Session(db_engine, expire_on_commit=False) as session:
        comp_a = Company(name="Acme Alpha", status="active")
        comp_b = Company(name="Beta Corp", status="active")
        session.add_all([comp_a, comp_b])
        session.commit()

        user_a = User(
            email="user@alpha.com",
            password_hash=hash_password("pw"),
            role="member",
            approval_status="approved",
            company_id=comp_a.id,
        )
        user_b = User(
            email="user@beta.com",
            password_hash=hash_password("pw"),
            role="member",
            approval_status="approved",
            company_id=comp_b.id,
        )
        session.add_all([user_a, user_b])
        session.commit()
        u_a_id, u_b_id = user_a.id, user_b.id

    client_a = TestClient(app)
    client_a.headers["Authorization"] = f"Bearer {create_access_token(u_a_id)}"
    client_b = TestClient(app)
    client_b.headers["Authorization"] = f"Bearer {create_access_token(u_b_id)}"

    store = VectorStore(persist_dir=str(tmp_path))
    chunks_a = chunk_markdown("# Secret Alpha\n\nAlpha secret policy content")
    chunks_b = chunk_markdown("# Secret Beta\n\nBeta secret policy content")
    store.upsert_chunks(
        document_id="doc-a",
        company_id=str(comp_a.id),
        user_id=str(u_a_id),
        filename="alpha_secret.md",
        chunks=chunks_a,
        embeddings=[_bag_of_words(c.text) for c in chunks_a],
    )
    store.upsert_chunks(
        document_id="doc-b",
        company_id=str(comp_b.id),
        user_id=str(u_b_id),
        filename="beta_secret.md",
        chunks=chunks_b,
        embeddings=[_bag_of_words(c.text) for c in chunks_b],
    )

    recording_llm = _RecordingLLM()
    _override(recording_llm)
    _override_store(store)

    try:
        # User A chats
        res_a = client_a.post("/chat", json={"message": "What is the secret policy?"})
        done_a = next(data for event, data in _parse_sse_events(res_a.text) if event == "done")
        sources_a = [s["filename"] for s in done_a["sources"]]
        assert "alpha_secret.md" in sources_a
        assert "beta_secret.md" not in sources_a
        assert "assistant for Acme Alpha" in recording_llm.prompts[0]

        # User B chats
        res_b = client_b.post("/chat", json={"message": "What is the secret policy?"})
        done_b = next(data for event, data in _parse_sse_events(res_b.text) if event == "done")
        sources_b = [s["filename"] for s in done_b["sources"]]
        assert "beta_secret.md" in sources_b
        assert "alpha_secret.md" not in sources_b
        assert "assistant for Beta Corp" in recording_llm.prompts[1]
    finally:
        _clear_overrides()


def test_chat_emits_error_event_on_llm_failure_mid_stream(client, tmp_path, test_user_id, db_engine):
    _override(_FailingFakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", json={"message": "How many vacation days do I get?"})
    finally:
        _clear_overrides()

    events = _parse_sse_events(response.text)
    assert events[0] == ("token", {"text": "Emplo"})
    assert events[-1][0] == "error"
    assert not any(event == "done" for event, _ in events)


def test_chat_with_unknown_conversation_id_returns_404(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post(
            "/chat",
            json={"message": "hi", "conversation_id": str(uuid.uuid4())},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 404


def test_chat_requires_a_message(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", json={})
    finally:
        _clear_overrides()

    assert response.status_code == 422


def test_chat_rejects_a_message_over_the_length_limit(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", json={"message": "x" * 4001})
    finally:
        _clear_overrides()

    assert response.status_code == 422


def test_chat_sets_conversation_title_from_first_message(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", json={"message": "What is our travel policy?"})
    finally:
        _clear_overrides()

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done = next(data for event, data in events if event == "done")
    conversation_id = done["conversation_id"]

    conv_response = client.get("/conversations")
    assert conv_response.status_code == 200
    conv = next(c for c in conv_response.json() if c["id"] == conversation_id)
    assert conv["title"] == "What is our travel policy?"
