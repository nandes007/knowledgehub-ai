from app.config import settings
from app.services.llm import TokenUsage
from app.services.rag import stream_answer
from ingestion.chunk import Chunk
from ingestion.index import VectorStore


class _TopicalLLM:
    """Embeds everything next to the handbook chunk - i.e. dense retrieval that
    misses the exact identifier, which is what hybrid search is here to fix."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None):
        yield "answer"


def _seeded_store(tmp_path) -> VectorStore:
    store = VectorStore(persist_dir=str(tmp_path))
    store.upsert_chunks(
        document_id="doc-handbook",
        user_id="u1",
        filename="handbook.md",
        chunks=[Chunk(text="Employees may request time off from their manager.", index=0, h1=None, h2=None)],
        embeddings=[[1.0, 0.0]],
    )
    store.upsert_chunks(
        document_id="doc-tickets",
        user_id="u1",
        filename="tickets.md",
        chunks=[Chunk(text="Ticket ABC-9931 covers laptop replacement.", index=0, h1=None, h2=None)],
        embeddings=[[0.0, 1.0]],
    )
    return store


def test_hybrid_ranks_exact_keyword_match_first(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "hybrid_search", True)

    _, sources, _ = stream_answer("What is ABC-9931?", llm=_TopicalLLM(), vector_store=_seeded_store(tmp_path))

    assert sources[0]["filename"] == "tickets.md"


def test_dense_only_when_flag_is_off(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "hybrid_search", False)

    _, sources, _ = stream_answer("What is ABC-9931?", llm=_TopicalLLM(), vector_store=_seeded_store(tmp_path))

    assert sources[0]["filename"] == "handbook.md"


def test_hybrid_still_respects_visibility_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "hybrid_search", True)
    store = _seeded_store(tmp_path)
    store.upsert_chunks(
        document_id="doc-finance",
        user_id="u1",
        filename="finance.md",
        chunks=[Chunk(text="Ticket ABC-9931 refund was approved.", index=0, h1=None, h2=None)],
        embeddings=[[0.0, 1.0]],
        department="finance",
        visibility="department",
    )

    _, sources, _ = stream_answer(
        "What is ABC-9931?",
        llm=_TopicalLLM(),
        vector_store=store,
        department="engineering",
    )

    assert all(s["filename"] != "finance.md" for s in sources)
