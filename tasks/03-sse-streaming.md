# Task 03: SSE Streaming for /chat

**Feature:** Streaming responses (Day 3 — hardest backend day)
**Branch:** `feat/chat-streaming`

**Description:** Convert `/chat` to `StreamingResponse` with an async generator yielding token events plus a final `done` event carrying sources/metadata. Document the SSE event shapes in `docs/api-contract.md`.

**Acceptance criteria:**
- [ ] `/chat` streams `data:` frames token-by-token
- [ ] Final `done` event carries sources + metadata
- [ ] SSE event shapes documented in `docs/api-contract.md` (same commit)

**Verification:**
- [ ] `curl -N -X POST /chat ...` shows tokens arriving progressively, ending with `done`

**Dependencies:** Task 02

**Files likely touched:** backend/app/routers/chat.py, backend/app/services/rag.py, docs/api-contract.md

**Estimated scope:** S

**Risk:** async generator friction is expected — budget extra time.
