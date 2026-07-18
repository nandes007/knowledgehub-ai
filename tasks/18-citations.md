# Task 18: Source Citations

**Feature:** Citations under answers (Day 18)
**Branch:** `feat/citations`

**Description:** RAG service returns source chunks; final SSE `done` event carries `sources`; persist to `messages.sources`; render `SourceList` (filename + snippet) under each answer.

**Acceptance criteria:**
- [ ] `done` event includes `[{document_id, filename, chunk_preview}]`
- [ ] Sources persisted in `messages.sources` JSONB
- [ ] `SourceList` renders under each assistant answer, including on history reload

**Verification:**
- [ ] Every grounded answer shows which documents it came from

**Dependencies:** Task 17

**Files likely touched:** backend/app/services/rag.py, backend/app/routers/chat.py, frontend/components/SourceList.tsx, frontend/lib/sse.ts, docs/api-contract.md

**Estimated scope:** M
