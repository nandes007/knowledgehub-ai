# Task 22: Observability

**Feature:** Logging & cost tracking (Day 23)
**Branch:** `feat/observability`

**Description:** Structured JSON logging, log every LLM call with model + token counts, simple admin stats endpoint (messages/day, docs, estimated cost).

**Acceptance criteria:**
- [ ] JSON logs with request context
- [ ] Every LLM call logged with model + prompt/completion tokens
- [ ] Stats endpoint returns messages/day, doc count, estimated cost

**Verification:**
- [ ] You can answer "what did yesterday cost?" from logs/endpoint

**Dependencies:** Task 21

**Files likely touched:** backend/app/main.py, backend/app/services/llm.py, backend/app/routers/* (stats endpoint)

**Estimated scope:** S
