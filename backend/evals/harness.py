"""Shared plumbing for the eval scripts: an isolated index over evals/corpus.

The index lives in its own Chroma directory so evals never touch the real
knowledge base, and retrieval goes through the production code path in
`app.services.rag` so the numbers describe the shipped retriever.
"""

import shutil
from pathlib import Path

from app.config import settings
from app.services import rag
from app.services.llm import get_llm_provider
from evals.metrics import CORPUS_DIR
from ingestion.index import VectorStore
from ingestion.pipeline import ingest_file

INDEX_ROOT = Path(__file__).resolve().parent / ".chroma-eval"
DEFAULT_CHUNK_SIZE = 800


def build_index(*, rebuild: bool = False, chunk_size: int = DEFAULT_CHUNK_SIZE) -> VectorStore:
    """Ingest the corpus once per chunk size; reuse the persisted index after that."""
    index_dir = INDEX_ROOT.with_name(f"{INDEX_ROOT.name}-{chunk_size}")
    if rebuild and index_dir.exists():
        shutil.rmtree(index_dir)
    fresh = not index_dir.exists()

    store = VectorStore(persist_dir=str(index_dir))
    if fresh:
        llm = get_llm_provider()
        for path in sorted(CORPUS_DIR.glob("*.md")):
            ingest_file(
                path,
                document_id=path.stem,
                user_id="evals",
                filename=path.name,
                llm=llm,
                vector_store=store,
                chunk_size=chunk_size,
            )
    return store


def retrieve(question: str, store: VectorStore, *, hybrid: bool) -> list[dict]:
    """Top-k matches for a question, as the chat endpoint would retrieve them."""
    # ponytail: flip the setting the retriever already reads instead of threading a
    # parameter through rag._retrieve for the sake of one script.
    settings.hybrid_search = hybrid
    embedding = get_llm_provider().embed_texts([question])[0]
    return rag._retrieve(question, embedding, store, None)


def retrieved_sources(matches: list[dict]) -> list[str]:
    """Source filenames in chunk-rank order; duplicates kept so `recall@k` means
    'in the top k chunks'. recall_at_k dedupes what survives the slice."""
    return [match["filename"] for match in matches]
