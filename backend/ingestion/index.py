import hashlib
import math
import re
from collections import Counter
from functools import lru_cache

import chromadb

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


class VectorStore:
    def __init__(self, persist_dir: str | None = None) -> None:
        client = chromadb.PersistentClient(path=persist_dir or settings.chroma_persist_dir)
        self._collection = client.get_or_create_collection(_COLLECTION_NAME)

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
        ids = [chunk_id(document_id, c.index, c.text) for c in chunks]
        metadatas = [
            {
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
            }
            for c in chunks
        ]
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=metadatas,
        )
        return len(chunks)

    def delete_by_document(self, document_id: str) -> None:
        self._collection.delete(where={"document_id": document_id})

    def query(self, query_embedding: list[float], *, top_k: int = 5, where: dict | None = None) -> list[dict]:
        results = self._collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where)
        matches = []
        for id_, text, meta in zip(results["ids"][0], results["documents"][0], results["metadatas"][0]):
            matches.append({"id": id_, "text": text, **meta})
        return matches

    def keyword_query(self, query: str, *, top_k: int = 5, where: dict | None = None) -> list[dict]:
        # ponytail: BM25 over the (filtered) corpus at query time - no second index to keep in
        # sync with ingest/delete. Ceiling is a few tens of thousands of chunks; past that,
        # move the sparse side to Postgres tsvector or a real BM25 index.
        results = self._collection.get(where=where, include=["documents", "metadatas"])
        documents = results["documents"]
        if not documents:
            return []
        scored = zip(_bm25_scores(query, documents), results["ids"], documents, results["metadatas"])
        ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: s[0], reverse=True)
        return [{"id": id_, "text": text, **meta} for _, id_, text, meta in ranked[:top_k]]


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()
