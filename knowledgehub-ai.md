# KnowledgeHub AI — Project Plan & Progress Tracker

> **Pitch:** KnowledgeHub AI is an internal knowledge assistant that solves knowledge loss from employee turnover. Employees upload company documents (PDF, Word, PowerPoint, Markdown), and anyone can chat with the knowledge base — with streaming answers, conversation history, and source citations. Built as a full-stack, production-ready RAG product.

**How to use this file:** work top-to-bottom. Check a box only when the "Definition of Done" for that day is met. If a day takes two days, take two days — the *sequence* matters, the dates don't. Commit and push every day, even unfinished work.

---

## 1. Goals & Scope

### v1 (MVP) — must have
- [ ] Chat with the knowledge base (RAG) with **streaming** responses
- [ ] **Conversation history** (persisted, resumable, sidebar list)
- [ ] **Knowledge upload**: users upload PDF / DOCX / PPTX / MD → background ingestion → searchable
- [ ] Document management: list uploaded docs with status, delete docs (removes vectors too)
- [ ] **Authentication** (email + password, JWT), data scoped per user
- [ ] **Source citations** under each answer
- [ ] Dockerized, deployed with a live URL, portfolio-quality README

### v2 — after MVP is achieved
- [ ] Department / role-based document visibility (metadata filtering at query time)
- [ ] Hybrid search (dense + BM25) and reranking
- [ ] Admin dashboard (usage stats, cost tracking)
- [ ] **AI / Retrieval evaluation (RAGAS)** ← intentionally last, see Phase 7

### Out of scope (write it down so you don't drift)
- SSO / OAuth providers
- Multi-tenant orgs / billing
- Mobile app
- Fine-tuning models

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.12+) | Already in Python (LangChain/Chroma), async-native, great for SSE streaming |
| ORM / DB layer | **SQLModel** (or SQLAlchemy 2.x) | Typed models, plays well with FastAPI |
| Relational DB | **PostgreSQL 16** | Users, conversations, messages, document registry |
| Vector DB | **Chroma** (persistent) | Keep existing investment; per-file upsert/delete by ID |
| Ingestion | **MarkItDown + LangChain splitters** | Existing pipeline, moved into `backend/ingestion/` |
| Embeddings | OpenAI `text-embedding-3-large` | Already in use |
| LLM | OpenAI (or swappable via env var) | Keep provider behind one service class so it's swappable |
| Frontend | **Next.js (App Router) + React + TypeScript** | Most hireable combo, good streaming support |
| Styling | **Tailwind CSS** | Fast iteration, consistent look |
| Markdown rendering | `react-markdown` | Assistant answers render as rich text |
| Streaming | **SSE** (Server-Sent Events) | Simpler than WebSockets for one-way token streams |
| Auth | JWT (`python-jose` + `passlib[bcrypt]`) | Simple, credible, interview-explainable |
| Background jobs | FastAPI `BackgroundTasks` (v1) → Celery/RQ (only if needed) | Don't over-engineer v1 |
| File storage | Local disk volume (v1), MinIO/S3 optional later | Keep it simple first |
| Container | Docker + docker-compose | One-command startup |
| Deploy | Single VPS (Hetzner/DO) + Caddy, or Railway/Render | Live URL multiplies credibility |
| Rate limiting | `slowapi` | Production hygiene |
| Tests | `pytest` + `httpx` (backend), light Playwright smoke test (optional) | Enough to be credible |
| Evals (Phase 7) | **RAGAS** + custom recall@k script | Measurable retrieval quality |

---

## 3. Repository & Folder Structure (Monorepo)

One repo: `knowledge-hub-ai`. Backend and frontend live together but stay **loosely coupled through the HTTP API contract only** — no shared code across the boundary.

```
knowledge-hub-ai/
├── README.md                  # portfolio-quality: pitch, architecture diagram, screenshots, run-in-3-commands
├── NOTES.md                   # daily log of problems hit + solutions (interview stories)
├── docker-compose.yml         # postgres + backend + frontend (+ caddy in prod)
├── .env.example               # every required env var, documented, no secrets
├── docs/
│   ├── architecture.md        # diagram + design decisions (why SSE, why upsert, why monorepo)
│   └── api-contract.md        # endpoint list, request/response shapes, SSE event format
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py            # FastAPI app factory, routers, CORS, middleware
│   │   ├── config.py          # pydantic-settings, env vars
│   │   ├── db.py              # engine, session dependency
│   │   ├── models/            # SQLModel tables: user, conversation, message, document
│   │   ├── schemas/           # request/response Pydantic models (API contract)
│   │   ├── routers/
│   │   │   ├── auth.py        # /auth/register, /auth/login
│   │   │   ├── chat.py        # /chat (SSE streaming)
│   │   │   ├── conversations.py
│   │   │   └── documents.py   # upload, list, delete
│   │   ├── services/
│   │   │   ├── rag.py         # retrieve → build prompt → stream LLM tokens
│   │   │   ├── llm.py         # provider wrapper (swappable)
│   │   │   └── auth.py        # hashing, JWT create/verify
│   │   └── deps.py            # get_current_user, get_session
│   ├── ingestion/             # existing pipeline moves here, refactored
│   │   ├── convert.py         # MarkItDown wrapper + OCR fallback hook
│   │   ├── chunk.py           # header split → char split → breadcrumb prefix
│   │   ├── index.py           # per-file UPSERT/DELETE by deterministic chunk IDs
│   │   └── pipeline.py        # ingest_document(document_id) — the background task entrypoint
│   └── tests/
│       ├── test_auth.py
│       ├── test_chat.py
│       └── test_documents.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── app/
│   │   ├── (auth)/login/  register/
│   │   ├── chat/[conversationId]/    # main chat page
│   │   └── knowledge/                # upload + document list page
│   ├── components/
│   │   ├── ChatPanel.tsx  MessageBubble.tsx  Sidebar.tsx
│   │   ├── SourceList.tsx            # citations under answers
│   │   └── UploadDropzone.tsx  DocumentTable.tsx
│   └── lib/
│       ├── api.ts                    # typed fetch wrappers
│       └── sse.ts                    # SSE consumption helper
└── scripts/
    └── seed.py                       # optional: seed demo user + sample docs
```

---

## 4. Data Model & DDL (PostgreSQL)

Four tables for v1. UUID primary keys, timestamps everywhere, soft references to vector store via `documents.id` used inside chunk IDs.

```sql
-- users
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    role            TEXT NOT NULL DEFAULT 'member',       -- 'member' | 'admin' (v2: department roles)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- conversations
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL DEFAULT 'New chat',      -- auto-generate from first message later
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC);

-- messages
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    sources         JSONB,                                  -- [{document_id, filename, chunk_preview}] for citations
    token_count     INTEGER,                                -- cost tracking / observability
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- documents (registry of uploaded knowledge files)
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    content_type    TEXT NOT NULL,                          -- application/pdf, docx mime, etc.
    file_path       TEXT NOT NULL,                          -- storage location on disk/S3
    file_hash       TEXT NOT NULL,                          -- md5/sha256, dedupe & change detection
    status          TEXT NOT NULL DEFAULT 'processing'
                    CHECK (status IN ('processing', 'ready', 'failed')),
    error_message   TEXT,                                   -- populated when status = 'failed'
    doc_type        TEXT NOT NULL DEFAULT 'general',        -- onboarding, policy, product... (v2: filtering)
    department      TEXT,                                   -- v2: visibility filtering
    chunk_count     INTEGER,                                -- set after successful ingestion
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_user ON documents(user_id, created_at DESC);
CREATE INDEX idx_documents_status ON documents(status);
```

**Vector store convention (Chroma):** every chunk gets a deterministic ID
`{document_id}::{chunk_index}::{content_hash[:12]}` and metadata
`{document_id, user_id, filename, doc_type, department, h1, h2}`.
Then: delete a file's vectors with `where={"document_id": ...}`; re-ingest = delete-then-upsert for that file only. **Never rebuild the whole collection.**

---

## 5. Versioning & Git Workflow

- **Monorepo**, `main` branch always deployable.
- Branch per feature/day: `feat/chat-streaming`, `feat/upload-endpoint`, `fix/sse-reconnect`. Merge to `main` via PR (yes, even solo — the PR descriptions become portfolio evidence).
- **Conventional Commits**: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`. Clean history reads well to reviewers.
- Tag releases: `v0.1.0` end of Week 1 (API skeleton), `v0.2.0` end of Week 2 (chat UI), `v0.3.0` (upload), `v0.4.0` (auth + citations), **`v1.0.0` = deployed MVP**, `v1.1.0+` = v2 features, `v1.x` eval milestone.
- API contract changes = update `docs/api-contract.md` in the same commit as the code change (frontend + backend change together in one commit — this is the monorepo payoff).
- `.env.example` updated in the same PR as any new env var. Secrets never committed.

**Daily habits (non-negotiable):**
- [ ] Commit + push every day, even unfinished
- [ ] One line in `NOTES.md`: what I did, what broke, how I fixed it
- [ ] Check the day's box here only when Definition of Done is met

---

## 6. Day-by-Day Plan

### Phase 0 — Preparation (Days 0.1–0.3)

- [ ] **Day 0.1 — Repo & tooling.** Create repo `knowledge-hub-ai`, folder skeleton above, README stub with the pitch, `.env.example`, `.gitignore`, `NOTES.md`. Install Node LTS, Python 3.12, Docker.
  *Done when:* repo pushed, skeleton folders committed.
- [ ] **Day 0.2 — Learn the unknowns.** Skim FastAPI (routing, `Depends`, `StreamingResponse`), Next.js App Router pages/layouts, how SSE works (format of `data:` frames). If new to React: do the official React "tic-tac-toe" tutorial today.
  *Done when:* you can explain SSE frame format and App Router file routing out loud.
- [ ] **Day 0.3 — Design on paper.** Draw the data model (section 4), the request flow (upload → background ingest → chat → retrieve → stream), and copy the v1 scope into the README. Write `docs/api-contract.md` v0 with planned endpoints.
  *Done when:* `docs/architecture.md` has the diagram (photo of paper is fine for now).

### Phase 1 — Backend skeleton + RAG as an API (Week 1)

- [ ] **Day 1 — FastAPI + Postgres.** App factory, `/healthz`, docker-compose with Postgres, SQLModel models + tables for all four tables, session dependency.
  *Done when:* `docker compose up` starts Postgres, `GET /healthz` returns 200, tables exist.
- [ ] **Day 2 — RAG endpoint (non-streaming).** Move ingestion code into `backend/ingestion/`. `POST /chat`: retrieve top-k from Chroma → build prompt → full LLM answer. Hardcode one user.
  *Done when:* `curl POST /chat` returns a grounded answer from your existing indexed docs.
- [ ] **Day 3 — SSE streaming.** Convert `/chat` to `StreamingResponse` with async generator yielding token events + a final `done` event carrying sources/metadata. Define the SSE event shapes in `api-contract.md`.
  *Done when:* `curl -N` shows tokens arriving progressively. (Hardest backend day — expect friction with async generators.)
- [ ] **Day 4 — Conversation persistence.** `POST /conversations`, `GET /conversations`, `GET /conversations/{id}/messages`. Persist user + assistant messages; include last N messages in the LLM prompt so follow-ups work.
  *Done when:* a two-turn conversation via curl shows the model using prior context.
- [ ] **Day 5 — Tests + buffer.** 3–5 pytest tests (health, chat happy path, history CRUD). Refactor anything ugly. Catch up on slippage. Tag `v0.1.0`.
  *Done when:* `pytest` green, tag pushed.

### Phase 2 — Frontend chat UI (Week 2)

- [ ] **Day 6 — Layout with fake data.** Next.js + Tailwind. Sidebar (conversation list) + chat panel, all static.
  *Done when:* the layout looks like a chat app with dummy messages.
- [ ] **Day 7 — Wire to backend (non-streaming).** `lib/api.ts` fetch wrappers; send a message, render the full response. Handle CORS on the backend.
  *Done when:* typing a question in the browser returns a real RAG answer.
- [ ] **Day 8 — Streaming UI.** Consume SSE in `lib/sse.ts`; render tokens live, auto-scroll, "thinking" indicator, render markdown with `react-markdown`.
  *Done when:* answers visibly stream token-by-token in the browser.
- [ ] **Day 9 — History UI.** Sidebar loads real conversations, click to open, "New chat" creates one, active conversation highlighted, auto-title from first message.
  *Done when:* refresh the page and every past conversation is still there and openable.
- [ ] **Day 10 — Polish pass.** Loading/error/empty states (backend down, request failed, no conversations yet), keyboard submit, disabled states while streaming, reasonable mobile layout. Tag `v0.2.0`.
  *Done when:* killing the backend mid-chat shows a friendly error, not a broken UI.

### Phase 3 — Knowledge upload, the differentiator (Week 3)

- [ ] **Day 11 — Upload endpoint.** `POST /documents` (multipart), save file to disk volume, insert `documents` row `status='processing'`, return immediately.
  *Done when:* curl upload returns 202-style response with document id + status.
- [ ] **Day 12 — Background ingestion + per-file upsert.** `BackgroundTasks` runs `pipeline.ingest_document(id)`: convert → chunk → embed → **upsert by deterministic chunk IDs** → set `status='ready'` + `chunk_count`, or `status='failed'` + `error_message`. This replaces the old full-rebuild forever.
  *Done when:* uploading one file adds only its chunks; existing vectors untouched.
- [ ] **Day 13 — List & delete.** `GET /documents` (with statuses), `DELETE /documents/{id}` removes file + DB row + its vectors (`where={"document_id": ...}`).
  *Done when:* after delete, questions about that doc no longer retrieve it.
- [ ] **Day 14 — Knowledge page UI.** Drag-and-drop upload (`UploadDropzone`), document table with live status (poll every 3–5s), delete with confirm.
  *Done when:* upload → watch status flip to *ready* → doc appears in table.
- [ ] **Day 15 — End-to-end loop test.** The loop that IS the product: upload PDF → ready → ask about it → cited, correct answer. Fix everything that breaks (something will). Tag `v0.3.0`.
  *Done when:* you can demo the full loop in under 2 minutes without touching a terminal.

### Phase 4 — Auth + citations + robustness (Week 4)

- [ ] **Day 16 — Auth backend.** `/auth/register`, `/auth/login` (JWT), password hashing, `get_current_user` dependency, protect all routes, scope conversations/documents to owner.
  *Done when:* requests without a token get 401; user A can't see user B's data.
- [ ] **Day 17 — Auth frontend.** Login/register pages, token storage, authenticated fetch wrapper, redirect unauthenticated users, logout.
  *Done when:* fresh browser → register → land in an empty, private workspace.
- [ ] **Day 18 — Citations.** RAG service returns source chunks; final SSE `done` event carries `sources`; persist to `messages.sources`; render `SourceList` under each answer (filename + snippet).
  *Done when:* every grounded answer shows which documents it came from.
- [ ] **Day 19 — Ugly inputs.** Max file size limit, scanned-PDF detection (near-empty extraction → `failed` with clear message, or OCR fallback if time allows), corrupt files, unsupported types, duplicate upload detection via `file_hash`.
  *Done when:* every bad file yields a clear user-facing error, never a 500.
- [ ] **Day 20 — Buffer / catch-up.** You will need it. Tag `v0.4.0`.

### Phase 5 — Production-ready pass (Week 5)

- [ ] **Day 21 — Dockerize everything.** Backend + frontend Dockerfiles, full docker-compose (Postgres, backend, frontend, volumes for Chroma + uploads).
  *Done when:* fresh clone + `.env` + `docker compose up` = working app.
- [ ] **Day 22 — Deploy.** VPS + Compose + Caddy (HTTPS), or Railway/Render. Point a domain or use provided URL.
  *Done when:* the app works at a public HTTPS URL from your phone.
- [ ] **Day 23 — Observability.** Structured logging (JSON), log every LLM call with model + token counts, simple admin stats endpoint (messages/day, docs, est. cost).
  *Done when:* you can answer "what did yesterday cost?" from logs/endpoint.
- [ ] **Day 24 — Hardening.** Rate limiting (`slowapi`) on chat + upload, input length limits, strict CORS, security headers, confirm secrets only in env, DB backups note.
  *Done when:* hammering `/chat` in a loop gets rate-limited, not a huge bill.
- [ ] **Day 25 — Portfolio README.** Architecture diagram, GIF/screenshots of the demo loop, run-in-3-commands, "Design decisions" section (SSE vs WebSockets, per-file upsert vs rebuild, monorepo, BackgroundTasks vs Celery). Tag **`v1.0.0`** 🎉
  *Done when:* someone who never met you understands the project from README alone.

### Phase 6 — v2 expansion (pick by energy, ~1 week)

- [ ] **Day 26–27 — Department visibility.** `department` + `visibility` metadata on documents; Chroma `where` filtering at query time based on the asking user's role; UI selector on upload.
- [ ] **Day 28 — Hybrid search + rerank.** Add BM25 alongside dense retrieval, merge, then rerank (cross-encoder or Cohere rerank).
- [ ] **Day 29–30 — Admin dashboard.** Usage stats, per-user doc counts, cost over time.

### Phase 7 — AI Evaluation (final phase, after MVP objectives achieved)

- [ ] **Day 31 — Build the eval set.** 25–50 (question → expected source document/chunk) pairs from your real knowledge base, saved as `evals/dataset.jsonl`. Include hard cases: multi-doc questions, table lookups, "list all X" questions.
- [ ] **Day 32 — Retrieval metrics baseline.** Script computing recall@k / MRR against the dataset for the current pipeline. Record baseline numbers in `docs/evals.md`.
- [ ] **Day 33 — RAGAS end-to-end.** Run RAGAS (faithfulness, answer relevancy, context precision/recall) on generated answers. Record baseline.
- [ ] **Day 34 — Experiment + measure.** Try one improvement (contextual chunk descriptions, different chunk size, reranker) and re-measure. Keep a results table.
  *Done when:* you can say "retrieval recall@5 went from X% to Y% after Z" — your strongest interview sentence.
- [ ] **Day 35 — Write it up.** `docs/evals.md` with methodology, results table, and what you'd try next. Link it from README.

---

## 7. Definition of "Production Ready" (release checklist)

- [ ] Live HTTPS URL, uptime through a full demo
- [ ] Auth on every route, per-user data isolation verified
- [ ] Upload → ingest → cited answer loop works for PDF, DOCX, PPTX, MD
- [ ] No full-collection rebuilds anywhere; delete removes vectors
- [ ] Graceful errors for every failure mode tested in Day 19
- [ ] Rate limiting + input limits on all expensive endpoints
- [ ] Logs answer "what happened and what did it cost?"
- [ ] `docker compose up` works from a fresh clone
- [ ] README + architecture doc + eval results complete
