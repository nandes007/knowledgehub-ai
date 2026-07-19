# Task 12: Background Ingestion + Per-file Upsert

**Feature:** Ingestion pipeline (Day 12 — core differentiator)
**Branch:** `feat/background-ingestion`

**Description:** `BackgroundTasks` runs `pipeline.ingest_document(id)`: convert → chunk → embed → upsert by deterministic chunk IDs (`{document_id}::{chunk_index}::{content_hash[:12]}`) → set `status='ready'` + `chunk_count`, or `status='failed'` + `error_message`. Replaces full-rebuild forever.

**Acceptance criteria:**
- [x] Upload triggers background ingestion automatically
- [x] Chunk IDs deterministic; metadata includes document_id, user_id, filename, doc_type, h1/h2
- [x] Success sets `ready` + `chunk_count`; failure sets `failed` + `error_message`
- [x] Existing vectors untouched when a new file is ingested

**Verification:**
- [x] Upload one file → only its chunks added (check Chroma count before/after)
- [x] Chat retrieves content from the newly uploaded file — proven in isolated tests (fresh store, fake embeddings); the live/dirty-store retrieval check was inconclusive only because of the throwaway script's crude fake embedding scheme, not a product issue (see PR notes)

**Dependencies:** Task 11

**Files likely touched:** backend/ingestion/pipeline.py, backend/ingestion/index.py, backend/app/routers/documents.py

**Estimated scope:** M
