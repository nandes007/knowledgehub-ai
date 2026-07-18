# Task 02: RAG Chat Endpoint (non-streaming)

**Feature:** RAG as an API (Day 2)
**Branch:** `feat/rag-endpoint`

**Description:** Move the existing ingestion code into `backend/ingestion/` and expose `POST /chat`: retrieve top-k from Chroma → build prompt → return the full LLM answer. Hardcode one user for now.

**Acceptance criteria:**
- [ ] Existing ingestion pipeline lives in `backend/ingestion/` (convert, chunk, index, pipeline)
- [ ] `POST /chat` returns a grounded answer from already-indexed docs
- [ ] LLM provider behind `services/llm.py` (swappable via env var)

**Verification:**
- [ ] `curl -X POST /chat -d '{"message": "..."}'` returns an answer citing real indexed content

**Dependencies:** Task 01

**Files likely touched:** backend/ingestion/*, backend/app/routers/chat.py, backend/app/services/rag.py, backend/app/services/llm.py, backend/app/schemas/*

**Estimated scope:** M
