from ingestion.chunk import Chunk
from ingestion.index import VectorStore, chunk_id


def test_chunk_id_is_deterministic():
    assert chunk_id("doc-1", 0, "hello") == chunk_id("doc-1", 0, "hello")


def test_chunk_id_changes_with_content():
    assert chunk_id("doc-1", 0, "hello") != chunk_id("doc-1", 0, "world")


def test_upsert_then_query_returns_matching_chunk(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    chunk = Chunk(text="Vacation policy: 20 days PTO", index=0, h1="Policy", h2="Vacation")

    store.upsert_chunks(
        document_id="doc-1",
        user_id="u1",
        filename="policy.md",
        chunks=[chunk],
        embeddings=[[1.0, 0.0, 0.0]],
    )
    results = store.query([1.0, 0.0, 0.0], top_k=1)

    assert results[0]["document_id"] == "doc-1"
    assert results[0]["filename"] == "policy.md"
    assert "PTO" in results[0]["text"]


def test_query_filters_by_where_clause(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    c1 = Chunk(text="doc for user1", index=0, h1=None, h2=None)
    c2 = Chunk(text="doc for user2", index=0, h1=None, h2=None)
    store.upsert_chunks(document_id="doc-1", user_id="user1", filename="a.md", chunks=[c1], embeddings=[[1.0, 0.0]])
    store.upsert_chunks(document_id="doc-2", user_id="user2", filename="b.md", chunks=[c2], embeddings=[[1.0, 0.0]])

    results = store.query([1.0, 0.0], top_k=5, where={"user_id": "user1"})

    assert len(results) == 1
    assert results[0]["user_id"] == "user1"


def test_upsert_returns_chunk_count(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    chunks = [
        Chunk(text="first", index=0, h1=None, h2=None),
        Chunk(text="second", index=1, h1=None, h2=None),
    ]

    count = store.upsert_chunks(
        document_id="doc-1",
        user_id="u1",
        filename="a.md",
        chunks=chunks,
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
    )

    assert count == 2


def test_delete_by_document_removes_only_that_documents_chunks(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    c1 = Chunk(text="doc1 content", index=0, h1=None, h2=None)
    c2 = Chunk(text="doc2 content", index=0, h1=None, h2=None)
    store.upsert_chunks(document_id="doc-1", user_id="u1", filename="a.md", chunks=[c1], embeddings=[[1.0, 0.0]])
    store.upsert_chunks(document_id="doc-2", user_id="u1", filename="b.md", chunks=[c2], embeddings=[[1.0, 0.0]])

    store.delete_by_document("doc-1")

    results = store.query([1.0, 0.0], top_k=10)
    assert all(r["document_id"] != "doc-1" for r in results)
    assert any(r["document_id"] == "doc-2" for r in results)
