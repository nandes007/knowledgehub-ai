# KnowledgeHub AI

Internal knowledge assistant that solves knowledge loss from employee turnover. Employees upload company documents (PDF, Word, PowerPoint, Markdown), and anyone can chat with the knowledge base — with streaming answers, conversation history, and source citations. Full-stack, production-ready RAG product.

> Status: early scaffold — see [`knowledgehub-ai.md`](knowledgehub-ai.md) for the full plan and [`tasks/todo.md`](tasks/todo.md) for the build-in-progress task list.

## Stack

FastAPI + PostgreSQL + Chroma on the backend, Next.js + TypeScript + Tailwind on the frontend, SSE for streaming, JWT auth, Docker Compose for local dev. Full rationale in `docs/architecture.md`.

## Run locally

```bash
cp .env.example .env   # fill in OPENAI_API_KEY at minimum
docker compose up
```

(Compose setup lands in Task 20 — until then, see `backend/` and `frontend/` for running each service directly.)

## Docs

- [`docs/architecture.md`](docs/architecture.md) — data flow, diagrams, design decisions
- [`docs/api-contract.md`](docs/api-contract.md) — endpoints, request/response shapes, SSE event format
- [`knowledgehub-ai.md`](knowledgehub-ai.md) — full project plan
- [`tasks/todo.md`](tasks/todo.md) — task-by-task build tracker, linked to GitHub issues
