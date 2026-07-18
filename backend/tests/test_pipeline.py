from ingestion.index import VectorStore
from ingestion.pipeline import ingest_file


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def test_ingest_file_converts_chunks_embeds_and_upserts(tmp_path):
    file_path = tmp_path / "policy.md"
    file_path.write_text("# Policy\n\nEmployees get 20 days of PTO per year.")
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))

    chunk_count = ingest_file(
        file_path,
        document_id="doc-1",
        user_id="u1",
        filename="policy.md",
        llm=_FakeLLM(),
        vector_store=store,
    )

    assert chunk_count >= 1
    results = store.query([1.0, 0.0], top_k=5)
    assert any("PTO" in r["text"] for r in results)
    assert results[0]["document_id"] == "doc-1"
