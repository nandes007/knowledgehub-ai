# Task 04: Conversation Persistence

**Feature:** Conversation history backend (Day 4)
**Branch:** `feat/conversation-persistence`

**Description:** CRUD for conversations and messages; persist both user and assistant messages; include last N messages in the LLM prompt so follow-up questions work.

**Acceptance criteria:**
- [ ] `POST /conversations`, `GET /conversations`, `GET /conversations/{id}/messages` implemented
- [ ] User + assistant messages persisted (with `sources` JSONB on assistant messages)
- [ ] Last N messages included in the prompt for context

**Verification:**
- [ ] Two-turn conversation via curl: second answer clearly uses prior context

**Dependencies:** Task 03

**Files likely touched:** backend/app/routers/conversations.py, backend/app/routers/chat.py, backend/app/services/rag.py, backend/app/schemas/*

**Estimated scope:** M
