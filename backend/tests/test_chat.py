import json
import uuid
from datetime import timedelta

from sqlmodel import Session, select

from app.config import settings
from app.main import app
from app.models.message import Message
from app.services.llm import TokenUsage, get_llm_provider, message_text
from ingestion.chunk import chunk_markdown
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _registered_client, _user_id_from, company_id_of

_VOCAB = ["vacation", "pto", "policy", "days", "onboarding", "laptop", "sick", "secret", "alpha", "beta"]
_ANSWER_TOKENS = ["Employees ", "get ", "20 ", "days ", "of ", "PTO ", "per ", "year."]


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, messages, *, usage: TokenUsage | None = None):
        if usage is not None:
            usage.prompt_tokens = 100
            usage.completion_tokens = 8
        yield from _ANSWER_TOKENS


class _FailingFakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, messages, *, usage: TokenUsage | None = None):
        yield "Emplo"
        raise RuntimeError("upstream LLM timed out")


class _RecordingLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_bag_of_words(t) for t in texts]

    def generate_answer_stream(self, messages, *, usage: TokenUsage | None = None):
        prompt = message_text(messages)
        self.prompts.append(prompt)
        yield "20 days"


def _bag_of_words(text: str) -> list[float]:
    words = set(text.lower().split())
    return [1.0 if w in words else 0.0 for w in _VOCAB]


def _seeded_store(tmp_path, user_id, db_engine=None) -> VectorStore:
    store = VectorStore(persist_dir=str(tmp_path))
    company_id = str(company_id_of(db_engine)) if db_engine is not None else "comp-1"

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
        response = client.post("/chat", data={"message": "How many vacation days do I get?"})
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
        response = client.post("/chat", data={"message": "How many vacation days do I get?"})
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
        response = client.post("/chat", data={"message": "How many vacation days do I get?"})
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
        first = client.post("/chat", data={"message": "How many vacation days do I get?"})
        conversation_id = _parse_sse_events(first.text)[-1][1]["conversation_id"]

        client.post("/chat", data={"message": "And how many sick days?", "conversation_id": conversation_id},
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
    client_a = _registered_client(db_engine, "user@alpha.com", company_name="Acme Alpha")
    client_b = _registered_client(db_engine, "user@beta.com", company_name="Beta Corp")
    u_a_id, u_b_id = _user_id_from(client_a), _user_id_from(client_b)
    comp_a_id, comp_b_id = company_id_of(db_engine, "Acme Alpha"), company_id_of(db_engine, "Beta Corp")

    store = VectorStore(persist_dir=str(tmp_path))
    chunks_a = chunk_markdown("# Secret Alpha\n\nAlpha secret policy content")
    chunks_b = chunk_markdown("# Secret Beta\n\nBeta secret policy content")
    store.upsert_chunks(
        document_id="doc-a",
        company_id=str(comp_a_id),
        user_id=str(u_a_id),
        filename="alpha_secret.md",
        chunks=chunks_a,
        embeddings=[_bag_of_words(c.text) for c in chunks_a],
    )
    store.upsert_chunks(
        document_id="doc-b",
        company_id=str(comp_b_id),
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
        res_a = client_a.post("/chat", data={"message": "What is the secret policy?"})
        done_a = next(data for event, data in _parse_sse_events(res_a.text) if event == "done")
        sources_a = [s["filename"] for s in done_a["sources"]]
        assert "alpha_secret.md" in sources_a
        assert "beta_secret.md" not in sources_a
        assert "assistant for Acme Alpha" in recording_llm.prompts[0]

        # User B chats
        res_b = client_b.post("/chat", data={"message": "What is the secret policy?"})
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
        response = client.post("/chat", data={"message": "How many vacation days do I get?"})
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
        response = client.post("/chat", data={"message": "hi", "conversation_id": str(uuid.uuid4())},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 404


def test_chat_requires_a_message(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", data={})
    finally:
        _clear_overrides()

    assert response.status_code == 422


def test_chat_rejects_a_message_over_the_length_limit(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", data={"message": "x" * 4001})
    finally:
        _clear_overrides()

    assert response.status_code == 422


def test_chat_sets_conversation_title_from_first_message(client, tmp_path, test_user_id, db_engine):
    _override(_FakeLLM())
    _override_store(_seeded_store(tmp_path, test_user_id, db_engine))
    try:
        response = client.post("/chat", data={"message": "What is our travel policy?"})
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


class _RecordingStore:
    def __init__(self) -> None:
        self.filters: list[dict] = []

    def query(self, embedding, *, top_k, where):
        self.filters.append(where)
        return []

    keyword_query = query


def _retrieval_filter(client) -> dict:
    store = _RecordingStore()
    _override(_FakeLLM())
    app.dependency_overrides[get_vector_store] = lambda: store
    try:
        assert client.post("/chat", data={"message": "What is the policy?"}).status_code == 200
    finally:
        _clear_overrides()
    return store.filters[0]


def test_retrieval_is_filtered_to_the_current_company_and_the_members_visibility(db_engine):
    admin = _registered_client(db_engine, "admin@example.com", role="admin")
    dept_id = admin.post("/departments", json={"name": "Engineering"}).json()["id"]
    owner = _registered_client(db_engine, "owner@example.com", role="owner")
    engineer = _registered_client(db_engine, "eng@example.com", department_id=uuid.UUID(dept_id))
    unassigned = _registered_client(db_engine, "solo@example.com")
    company = {"company_id": str(company_id_of(db_engine))}

    # Owners and admins: the whole company, and nothing but the company.
    assert _retrieval_filter(owner) == company
    assert _retrieval_filter(admin) == company
    # Members: the company AND (company-wide OR their own department).
    assert _retrieval_filter(unassigned) == {"$and": [company, {"visibility": "company"}]}
    engineer_filter = _retrieval_filter(engineer)
    assert engineer_filter["$and"][0] == company
    assert {"visibility": "company"} in engineer_filter["$and"][1]["$or"]
    assert dept_id in json.dumps(engineer_filter)


def test_the_same_user_gets_each_companys_filter_and_conversations(db_engine):
    here = _registered_client(db_engine, "both@example.com", company_name="Here", role="admin")
    there = _registered_client(db_engine, "both@example.com", company_name="There", role="member")

    assert _retrieval_filter(here) == {"company_id": str(company_id_of(db_engine, "Here"))}
    assert _retrieval_filter(there)["$and"][0] == {"company_id": str(company_id_of(db_engine, "There"))}

    # One chat each, and neither company shows the other's.
    here_ids = [c["id"] for c in here.get("/conversations").json()]
    there_ids = [c["id"] for c in there.get("/conversations").json()]
    assert len(here_ids) == len(there_ids) == 1 and here_ids != there_ids
    assert there.get(f"/conversations/{here_ids[0]}/messages").status_code == 404


def test_daily_message_cap_per_company(client, other_client, other_company_client, db_engine, monkeypatch):
    monkeypatch.setattr(settings, "max_messages_per_company_per_day", 2)
    store = _RecordingStore()
    _override(_FakeLLM())
    app.dependency_overrides[get_vector_store] = lambda: store

    def ask(c):
        return c.post("/chat", data={"message": "What is the policy?"})

    try:
        first, second = ask(client), ask(other_client)  # two members of one company share its allowance
        over = ask(client)
        elsewhere = ask(other_company_client)

        # Yesterday's messages no longer count.
        with Session(db_engine) as session:
            for message in session.exec(select(Message)):
                message.created_at -= timedelta(days=1, minutes=1)
                session.add(message)
            session.commit()
        next_day = ask(client)

        monkeypatch.setattr(settings, "max_messages_per_company_per_day", 0)  # 0 = unlimited
        unlimited = [ask(client) for _ in range(3)]
    finally:
        _clear_overrides()

    assert [r.status_code for r in (first, second, over)] == [200, 200, 403]
    assert "Daily message limit reached" in over.json()["detail"]
    assert elsewhere.status_code == 200
    assert next_day.status_code == 200
    assert [r.status_code for r in unlimited] == [200, 200, 200]
