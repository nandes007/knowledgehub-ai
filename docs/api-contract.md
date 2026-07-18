# API Contract (v0 — planned)

Update this file in the same commit as any endpoint change. This is v0: shapes will firm up as each endpoint is actually implemented (see `tasks/todo.md`).

## Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, display_name?}` | `{access_token, token_type}` |
| POST | `/auth/login` | `{email, password}` | `{access_token, token_type}` |

All routes below require `Authorization: Bearer <access_token>` once Task 16 lands. Until then, a hardcoded user is used (Task 02–15).

## Chat

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/chat` | `{conversation_id?, message}` | SSE stream (see below) |

### SSE event format

```
event: token
data: {"text": "partial answer chunk"}

event: done
data: {"sources": [{"document_id": "...", "filename": "...", "chunk_preview": "..."}], "message_id": "...", "conversation_id": "..."}
```

- `token` events repeat as the model generates output.
- Exactly one `done` event ends the stream, carrying citations and metadata.
- On error mid-stream: `event: error` with `data: {"message": "..."}`, then the connection closes.

## Conversations

| Method | Path | Response |
|---|---|---|
| POST | `/conversations` | `{id, title, created_at}` |
| GET | `/conversations` | `[{id, title, updated_at}]` newest first |
| GET | `/conversations/{id}/messages` | `[{id, role, content, sources, created_at}]` |

## Documents

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/documents` | multipart file | `{id, filename, status: "processing"}` |
| GET | `/documents` | — | `[{id, filename, status, chunk_count, error_message, created_at}]` |
| DELETE | `/documents/{id}` | — | `204` |

`status` transitions: `processing` → `ready` \| `failed`.

## Health

| Method | Path | Response |
|---|---|---|
| GET | `/healthz` | `{status: "ok"}` |
