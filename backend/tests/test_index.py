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
        company_id="comp-1",
        department_id="dept-1",
        filename="policy.md",
        chunks=[chunk],
        embeddings=[[1.0, 0.0, 0.0]],
    )
    results = store.query([1.0, 0.0, 0.0], top_k=1)

    assert results[0]["document_id"] == "doc-1"
    assert results[0]["company_id"] == "comp-1"
    assert results[0]["department_id"] == "dept-1"
    assert results[0]["department"] == "dept-1"
    assert results[0]["filename"] == "policy.md"
    assert "PTO" in results[0]["text"]


def test_query_filters_by_company_and_user(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    c1 = Chunk(text="doc for company1", index=0, h1=None, h2=None)
    c2 = Chunk(text="doc for company2", index=0, h1=None, h2=None)
    store.upsert_chunks(
        document_id="doc-1",
        company_id="company1",
        user_id="user1",
        filename="a.md",
        chunks=[c1],
        embeddings=[[1.0, 0.0]],
    )
    store.upsert_chunks(
        document_id="doc-2",
        company_id="company2",
        user_id="user2",
        filename="b.md",
        chunks=[c2],
        embeddings=[[1.0, 0.0]],
    )

    results1 = store.query([1.0, 0.0], top_k=5, where={"company_id": "company1"})
    assert len(results1) == 1
    assert results1[0]["company_id"] == "company1"
    assert results1[0]["document_id"] == "doc-1"

    results2 = store.query([1.0, 0.0], top_k=5, where={"company_id": "company2"})
    assert len(results2) == 1
    assert results2[0]["company_id"] == "company2"
    assert results2[0]["document_id"] == "doc-2"


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


def test_keyword_query_finds_exact_code_a_bad_embedding_would_miss(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    c1 = Chunk(text="General onboarding notes for new hires", index=0, h1=None, h2=None)
    c2 = Chunk(text="Invoice INV-2024-8871 was paid in March", index=0, h1=None, h2=None)
    store.upsert_chunks(document_id="doc-1", user_id="u1", filename="a.md", chunks=[c1], embeddings=[[1.0, 0.0]])
    store.upsert_chunks(document_id="doc-2", user_id="u1", filename="b.md", chunks=[c2], embeddings=[[1.0, 0.0]])

    results = store.keyword_query("INV-2024-8871", top_k=1)

    assert len(results) == 1
    assert results[0]["document_id"] == "doc-2"
    assert results[0]["filename"] == "b.md"


def test_keyword_query_filters_by_company(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    c1 = Chunk(text="secret code ZULU", index=0, h1=None, h2=None)
    c2 = Chunk(text="secret code ZULU", index=0, h1=None, h2=None)
    store.upsert_chunks(
        document_id="doc-1",
        company_id="company1",
        user_id="user1",
        filename="a.md",
        chunks=[c1],
        embeddings=[[1.0, 0.0]],
    )
    store.upsert_chunks(
        document_id="doc-2",
        company_id="company2",
        user_id="user2",
        filename="b.md",
        chunks=[c2],
        embeddings=[[1.0, 0.0]],
    )

    results = store.keyword_query("ZULU", top_k=5, where={"company_id": "company1"})

    assert len(results) == 1
    assert results[0]["company_id"] == "company1"
    assert results[0]["document_id"] == "doc-1"


def test_keyword_query_reflects_ingest_and_delete(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))
    chunk = Chunk(text="policy code ALPHA-7", index=0, h1=None, h2=None)
    store.upsert_chunks(document_id="doc-1", user_id="u1", filename="a.md", chunks=[chunk], embeddings=[[1.0, 0.0]])
    assert store.keyword_query("ALPHA-7", top_k=5)

    store.delete_by_document("doc-1")

    assert store.keyword_query("ALPHA-7", top_k=5) == []


def test_keyword_query_on_empty_store_returns_nothing(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path))

    assert store.keyword_query("anything", top_k=5) == []


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
