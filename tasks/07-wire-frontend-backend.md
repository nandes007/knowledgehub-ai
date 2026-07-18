# Task 07: Wire Frontend to Backend (non-streaming)

**Feature:** Frontend ↔ API integration (Day 7)
**Branch:** `feat/wire-frontend`

**Description:** Typed fetch wrappers in `lib/api.ts`; send a message and render the full response. Configure CORS on the backend.

**Acceptance criteria:**
- [ ] `lib/api.ts` has typed fetch wrappers matching `docs/api-contract.md`
- [ ] Typing a question in the browser returns a real RAG answer
- [ ] CORS configured (strict origin, not `*`)

**Verification:**
- [ ] End-to-end in browser: question → real grounded answer rendered

**Dependencies:** Task 06

**Files likely touched:** frontend/lib/api.ts, frontend/components/ChatPanel.tsx, backend/app/main.py

**Estimated scope:** S
