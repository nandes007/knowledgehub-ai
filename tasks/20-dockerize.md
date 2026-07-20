# Task 20: Dockerize Everything

**Feature:** Containerization (Day 21)
**Branch:** `chore/dockerize`

**Description:** Backend + frontend Dockerfiles, full docker-compose (Postgres, backend, frontend, volumes for Chroma + uploads).

**Acceptance criteria:**
- [x] Multi-stage Dockerfiles for backend and frontend
- [x] docker-compose runs all services with named volumes for Postgres, Chroma, uploads
- [x] All config via env vars, documented in `.env.example`

**Verification:**
- [x] Fresh clone + `.env` + `docker compose up` = working app end-to-end

**Dependencies:** Task 19

**Files likely touched:** backend/Dockerfile, frontend/Dockerfile, docker-compose.yml, .env.example

**Estimated scope:** M
