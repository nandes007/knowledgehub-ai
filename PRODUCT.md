# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Employees inside a company who need an answer that lives in a document someone else wrote — often someone who has since left. Secondarily, an admin (`users.role = 'admin'`) who checks usage and cost rather than asking questions.

## Product Purpose

KnowledgeHub AI solves knowledge loss from employee turnover. Employees upload company documents (PDF, Word, PowerPoint, Markdown); anyone can then chat with that knowledge base and get a streamed, source-cited answer instead of hunting through files or paging a coworker who may not be there anymore. Success is an employee finding a trustworthy answer on their own.

## Positioning

Not a generic chatbot: every answer is grounded in the org's own uploaded documents and shows exactly which document(s) it came from. Trust is verifiable (citation), not assumed (confidence).

## Operating Context

- Auth: email + password (JWT), all data scoped per user.
- Upload PDF/DOCX/PPTX/MD → background ingestion (chunk, embed, per-file upsert) → status goes processing → ready/failed.
- Chat: ask a question, get a token-streamed (SSE) answer with source citations; conversations persist and are resumable from a history sidebar.
- Admin (not yet built): usage stats — messages/day, document count, estimated LLM cost — gated to `role = 'admin'`.

## Capabilities and Constraints

- Stack: FastAPI + PostgreSQL + Chroma (backend), Next.js + TypeScript + Tailwind (frontend), SSE for streaming.
- Chroma runs in-process against a local persist directory, so the backend can only ever run as a single replica.
- Production hygiene already in place: per-user rate limiting, input length limits, strict CORS, security headers, structured JSON logs.
- Open (v2, not yet built): department-scoped document visibility, hybrid search + rerank, admin dashboard, RAGAS eval suite.

## Brand Commitments

None yet. No existing colors, logo, or typeface — confirmed with the user. This redesign is the first visual identity the product will have.

## Evidence on Hand

- Live deployment: knowledgehubai.nandes.tech.
- Existing, working screens: login/register, chat (streaming + citations + history sidebar), knowledge (upload/list/status/delete).
- No admin dashboard UI exists yet (planned, task 27).
- No product screenshots captured yet (README notes this as pending).
- No landing/marketing page exists; visiting the app goes straight to auth.

## Product Principles

1. Grounded over generic — an answer's value is its traceability to a real source, not its confidence.
2. Every employee completes the core loop unaided — this is an internal tool used by non-technical staff, not a power-user console.
3. Turnover-proofing is the point — the product exists so institutional knowledge outlives the person who had it.
4. Trust through transparency — citations are the product's credibility mechanism; never obscure them for the sake of a cleaner screen.

## Accessibility & Inclusion

No product-specific requirement established yet.
