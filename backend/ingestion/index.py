import hashlib
import math
import re
import uuid
from collections import Counter
from functools import lru_cache

from qdrant_client import QdrantClient, models

from app.config import settings
from ingestion.chunk import Chunk

_COLLECTION_NAME = "knowledge_chunks"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BM25_K1 = 1.5
_BM25_B = 0.75


def chunk_id(document_id: str, index: int, content: str) -> str:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"{document_id}::{index}::{content_hash}"


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _bm25_scores(query: str, documents: list[str]) -> list[float]:
    """Okapi BM25. Codes like INV-2024-8871 tokenize identically on both sides,
    so exact-identifier queries score far above merely topical chunks."""
    docs = [Counter(_tokenize(d)) for d in documents]
    lengths = [sum(c.values()) for c in docs]
    avg_length = (sum(lengths) / len(lengths)) or 1.0
    scores = [0.0] * len(docs)
    for term in set(_tokenize(query)):
        doc_freq = sum(1 for c in docs if term in c)
        if not doc_freq:
            continue
        idf = math.log(1 + (len(docs) - doc_freq + 0.5) / (doc_freq + 0.5))
        for i, counts in enumerate(docs):
            freq = counts.get(term, 0)
            if freq:
                norm = 1 - _BM25_B + _BM25_B * lengths[i] / avg_length
                scores[i] += idf * freq * (_BM25_K1 + 1) / (freq + _BM25_K1 * norm)
    return scores


def _to_filter(where: dict | None) -> models.Filter | None:
    """Translate the Chroma-style `where` dicts rag.py builds ({"field": value},
    {"$and": [...]}, {"$or": [...]}) into a Qdrant filter."""
    if not where:
        return None
    if "$and" in where:
        return models.Filter(must=[_to_filter(w) for w in where["$and"]])
    if "$or" in where:
        return models.Filter(should=[_to_filter(w) for w in where["$or"]])
    return models.Filter(
        must=[models.FieldCondition(key=k, match=models.MatchValue(value=v)) for k, v in where.items()]
    )


@lru_cache
def _local_client(path: str) -> QdrantClient:
    # Embedded mode locks its directory, so every VectorStore on one path must
    # share a single client.
    return QdrantClient(path=path)


class VectorStore:
    def __init__(self, persist_dir: str | None = None) -> None:
        """persist_dir (tests, evals) or QDRANT_PATH -> embedded Qdrant, no server;
        QDRANT_URL -> the Qdrant server."""
        if persist_dir is None and settings.qdrant_url:
            self._client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        else:
            self._client = _local_client(persist_dir or settings.qdrant_path)

    def _ensure_collection(self, vector_size: int) -> None:
        # Created on first write: the vector size comes from the embedding model.
        if not self._client.collection_exists(_COLLECTION_NAME):
            self._client.create_collection(
                _COLLECTION_NAME,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )

    def upsert_chunks(
        self,
        *,
        document_id: str,
        user_id: str,
        filename: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        doc_type: str = "general",
        company_id: str | None = None,
        department_id: str | None = None,
        department: str | None = None,
        visibility: str = "company",
    ) -> int:
        if not chunks:
            return 0
        self._ensure_collection(len(embeddings[0]))
        points = [
            models.PointStruct(
                # Qdrant ids must be UUIDs or ints; uuid5 keeps them deterministic,
                # so re-ingesting a document overwrites rather than duplicates.
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id(document_id, c.index, c.text))),
                vector=embedding,
                payload={
                    "text": c.text,
                    "document_id": document_id,
                    "company_id": company_id or "",
                    "user_id": user_id,
                    "filename": filename,
                    "doc_type": doc_type,
                    "department_id": department_id or "",
                    "department": department or department_id or "",
                    "visibility": visibility,
                    "h1": c.h1 or "",
                    "h2": c.h2 or "",
                },
            )
            for c, embedding in zip(chunks, embeddings)
        ]
        self._client.upsert(_COLLECTION_NAME, points=points)
        return len(chunks)

    def delete_by_document(self, document_id: str) -> None:
        if not self._client.collection_exists(_COLLECTION_NAME):
            return
        self._client.delete(
            _COLLECTION_NAME,
            points_selector=models.FilterSelector(filter=_to_filter({"document_id": document_id})),
        )

    def query(self, query_embedding: list[float], *, top_k: int = 5, where: dict | None = None) -> list[dict]:
        if not self._client.collection_exists(_COLLECTION_NAME):
            return []
        points = self._client.query_points(
            _COLLECTION_NAME, query=query_embedding, query_filter=_to_filter(where), limit=top_k
        ).points
        return [{"id": str(p.id), **p.payload} for p in points]

    def keyword_query(self, query: str, *, top_k: int = 5, where: dict | None = None) -> list[dict]:
        # ponytail: BM25 over the (filtered) corpus at query time - no second index to keep in
        # sync with ingest/delete. Ceiling is a few tens of thousands of chunks; past that,
        # move the sparse side to Qdrant sparse vectors (BM25 via fastembed).
        if not self._client.collection_exists(_COLLECTION_NAME):
            return []
        records, offset = [], None
        while True:
            page, offset = self._client.scroll(
                _COLLECTION_NAME, scroll_filter=_to_filter(where), limit=1000, offset=offset
            )
            records.extend(page)
            if offset is None:
                break
        if not records:
            return []
        scores = _bm25_scores(query, [r.payload["text"] for r in records])
        ranked = sorted((s for s in zip(scores, records) if s[0] > 0), key=lambda s: s[0], reverse=True)
        return [{"id": str(r.id), **r.payload} for _, r in ranked[:top_k]]


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()
