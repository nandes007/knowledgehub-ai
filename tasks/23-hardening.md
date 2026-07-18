# Task 23: Hardening

**Feature:** Production hygiene (Day 24)
**Branch:** `feat/hardening`

**Description:** Rate limiting (`slowapi`) on chat + upload, input length limits, strict CORS, security headers, confirm secrets only in env, DB backup note.

**Acceptance criteria:**
- [ ] `/chat` and `/documents` rate-limited per user/IP
- [ ] Message length + file size limits enforced
- [ ] Strict CORS origins; security headers set
- [ ] Backup approach documented (even if just a pg_dump cron note)

**Verification:**
- [ ] Hammering `/chat` in a loop gets 429s, not a huge bill

**Dependencies:** Task 22

**Files likely touched:** backend/app/main.py, backend/app/routers/chat.py, backend/app/routers/documents.py, docs/architecture.md

**Estimated scope:** S
