# Task 12: Background Ingestion + Per-file Upsert

**Feature:** Ingestion pipeline (Day 12 — core differentiator)
**Branch:** `feat/background-ingestion`

**Description:** `BackgroundTasks` runs `pipeline.ingest_document(id)`: convert → chunk → embed → upsert by deterministic chunk IDs (`{document_id}::{chunk_index}::{content_hash[:12]}`) → set `status='ready'` + `chunk_count`, or `status='failed'` + `error_message`. Replaces full-rebuild forever.

**Acceptance criteria:**
- [ ] Upload triggers background ingestion automatically
- [ ] Chunk IDs deterministic; metadata includes document_id, user_id, filename, doc_type, h1/h2
- [ ] Success sets `ready` + `chunk_count`; failure sets `failed` + `error_message`
- [ ] Existing vectors untouched when a new file is ingested

**Verification:**
- [ ] Upload one file → only its chunks added (check Chroma count before/after)
- [ ] Chat retrieves content from the newly uploaded file

**Dependencies:** Task 11

**Files likely touched:** backend/ingestion/pipeline.py, backend/ingestion/index.py, backend/app/routers/documents.py

**Estimated scope:** M
