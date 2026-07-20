# API Contract (v0 — planned)

Update this file in the same commit as any endpoint change. This is v0: shapes will firm up as each endpoint is actually implemented (see `tasks/todo.md`).

## Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, display_name?}` | `{access_token, token_type}` |
| POST | `/auth/login` | `{email, password}` | `{access_token, token_type}` |

All routes below require `Authorization: Bearer <access_token>`. Missing or invalid tokens get `401`.

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
- Exactly one `done` event ends a successful stream, carrying citations plus
  the persisted `message_id` (the assistant message) and `conversation_id`
  (existing if `conversation_id` was passed in the request, otherwise a new
  one created for this exchange).
- On error mid-stream: `event: error` with `data: {"message": "..."}`, then the
  connection closes without a `done` event. The user's message is still
  persisted even if the assistant's answer fails.

## Conversations

| Method | Path | Response |
|---|---|---|
| POST | `/conversations` | `{id, title, created_at, updated_at}` — title defaults to "New chat" |
| GET | `/conversations` | `[{id, title, created_at, updated_at}]` newest (`updated_at` desc) first |
| GET | `/conversations/{id}/messages` | `[{id, role, content, sources, created_at}]` chronological |

`GET /conversations/{id}/messages` 404s if the conversation doesn't exist or isn't owned by the current user.

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
