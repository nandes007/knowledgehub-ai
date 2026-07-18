# Task 13: Document List & Delete

**Feature:** Document management (Day 13)
**Branch:** `feat/document-management`

**Description:** `GET /documents` (with statuses) and `DELETE /documents/{id}` which removes the file, the DB row, and its vectors via `where={"document_id": ...}`.

**Acceptance criteria:**
- [ ] `GET /documents` returns list with status, chunk_count, timestamps
- [ ] Delete removes file from disk + DB row + all its vectors
- [ ] Never triggers a full-collection rebuild

**Verification:**
- [ ] After delete, questions about that doc no longer retrieve it

**Dependencies:** Task 12

**Files likely touched:** backend/app/routers/documents.py, backend/ingestion/index.py

**Estimated scope:** S
