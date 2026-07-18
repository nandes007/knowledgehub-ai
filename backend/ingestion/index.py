import hashlib
from functools import lru_cache

import chromadb

from app.config import settings
from ingestion.chunk import Chunk

_COLLECTION_NAME = "knowledge_chunks"


def chunk_id(document_id: str, index: int, content: str) -> str:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"{document_id}::{index}::{content_hash}"


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
        department: str | None = None,
    ) -> int:
        ids = [chunk_id(document_id, c.index, c.text) for c in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "user_id": user_id,
                "filename": filename,
                "doc_type": doc_type,
                "department": department or "",
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

    def query(self, query_embedding: list[float], *, top_k: int = 5, where: dict | None = None) -> list[dict]:
        results = self._collection.query(query_embeddings=[query_embedding], n_results=top_k, where=where)
        matches = []
        for id_, text, meta in zip(results["ids"][0], results["documents"][0], results["metadatas"][0]):
            matches.append({"id": id_, "text": text, **meta})
        return matches


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()
