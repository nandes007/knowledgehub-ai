from pathlib import Path

from app.services.llm import LLMProvider, get_llm_provider
from ingestion.chunk import chunk_markdown
from ingestion.convert import convert_to_markdown
from ingestion.index import VectorStore, get_vector_store


def ingest_file(
    file_path: Path,
    *,
    document_id: str,
    user_id: str,
    filename: str,
    doc_type: str = "general",
    department: str | None = None,
    llm: LLMProvider | None = None,
    vector_store: VectorStore | None = None,
) -> int:
    llm = llm or get_llm_provider()
    vector_store = vector_store or get_vector_store()

    text = convert_to_markdown(file_path)
    chunks = chunk_markdown(text)
    embeddings = llm.embed_texts([c.text for c in chunks])

    return vector_store.upsert_chunks(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
        doc_type=doc_type,
        department=department,
    )
