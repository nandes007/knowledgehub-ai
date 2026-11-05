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
| POST | `/chat` | `multipart/form-data`: `message`, `conversation_id?`, `files` (0-5) | SSE stream (see below) |

- `message` may be empty when files are attached. Neither text nor files gives `422`.
- Attachments: PNG, JPG, WEBP, GIF, PDF, DOCX, PPTX, MD, TXT, CSV (by extension), each
  up to `MAX_UPLOAD_SIZE_MB`. Bad type/count gives `400`, oversize gives `413`, before
  anything is stored. Attachments are private to the conversation and never indexed.
- Answers may embed pictures from retrieved documents as `![caption](/documents/{id}/images/{n})`.

### SSE event format

```
event: status
data: {"text": "Reading report.pdf…"}

event: token
data: {"text": "partial answer chunk"}

event: done
data: {"sources": [{"document_id": "...", "filename": "...", "chunk_preview": "..."}], "message_id": "...", "conversation_id": "..."}
```

- `status` events (optional) come before tokens while attachments are read.
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
| GET | `/conversations/{id}/messages` | `[{id, role, content, sources, attachments, created_at}]` chronological; `attachments` is `[{filename, mime, size, truncated}]` or `null` |
| GET | `/conversations/{id}/messages/{message_id}/attachments/{n}` | The attached file (owner only, else `404`) |

`GET /conversations/{id}/messages` 404s if the conversation doesn't exist or isn't owned by the current user.

## Documents

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/documents` | multipart file | `{id, filename, status: "processing"}` |
| GET | `/documents` | — | `[{id, filename, status, chunk_count, error_message, created_at}]` |
| DELETE | `/documents/{id}` | — | `204` |
| GET | `/documents/{id}/images/{n}` | — | PNG of a picture kept from the document at ingestion; same visibility rules as the document, else `404` |

`status` transitions: `processing` → `ready` \| `failed`.

## Health

| Method | Path | Response |
|---|---|---|
| GET | `/healthz` | `{status: "ok"}` |
