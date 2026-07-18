# Task 01: FastAPI + Postgres Skeleton

**Feature:** Backend foundation (Day 1)
**Branch:** `feat/backend-skeleton`

**Description:** FastAPI app factory with `/healthz`, docker-compose running Postgres 16, SQLModel models for all four tables (users, conversations, messages, documents), and a session dependency.

**Acceptance criteria:**
- [ ] `docker compose up` starts Postgres with a persistent volume
- [ ] `GET /healthz` returns 200
- [ ] All four tables from section 4 DDL exist with indexes
- [ ] `get_session` dependency wired in `deps.py`

**Verification:**
- [ ] `curl localhost:8000/healthz` → 200
- [ ] `psql` (or `\dt` via docker exec) shows users, conversations, messages, documents

**Dependencies:** Task 00

**Files likely touched:** docker-compose.yml, backend/pyproject.toml, backend/app/main.py, backend/app/config.py, backend/app/db.py, backend/app/models/*, backend/app/deps.py

**Estimated scope:** M
