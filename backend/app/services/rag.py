from collections.abc import Iterator

from app.services.llm import LLMProvider
from ingestion.index import VectorStore

_TOP_K = 5
_CHUNK_PREVIEW_LENGTH = 200

_SYSTEM_PROMPT = (
    "You are KnowledgeHub AI, an internal knowledge assistant. "
    "Answer the question using only the provided context. "
    "If the context doesn't contain the answer, say you don't know."
)


def stream_answer(
    question: str,
    *,
    user_id: str,
    llm: LLMProvider,
    vector_store: VectorStore,
) -> tuple[Iterator[str], list[dict]]:
    query_embedding = llm.embed_texts([question])[0]
    matches = vector_store.query(query_embedding, top_k=_TOP_K, where={"user_id": user_id})

    context = "\n\n---\n\n".join(m["text"] for m in matches)
    prompt = f"{_SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"

    sources = [
        {
            "document_id": m["document_id"],
            "filename": m["filename"],
            "chunk_preview": m["text"][:_CHUNK_PREVIEW_LENGTH],
        }
        for m in matches
    ]
    return llm.generate_answer_stream(prompt), sources
