# API Contract

Update this file in the same commit as any endpoint change.

## Account (not company-scoped)

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, display_name?, invite_token?}` | `201 {message, approval_status, company_slug}` |
| POST | `/auth/login` | `{email, password}` | `{access_token, token_type}` |
| GET | `/auth/me` | — | `{id, email, display_name, is_instance_admin, approval_status, companies: [{id, name, slug, status, role, department_id, department_name}]}` |
| POST | `/companies` | `{name}` | `201 {id, name, slug, status, role: "owner"}` — caller becomes owner |
| GET | `/invites/{token}` | — | `{company_name, email, role}` — public |
| POST | `/invites/{token}/accept` | — | `{company_slug}` — must be logged in as the invited email |

- Registration creates only an account. `SIGNUP_MODE` decides the rest: `open` (approved at once),
  `approval` (pending until an instance admin approves; login then says pending/rejected with `403`),
  `closed` (`403` unless a valid `invite_token` for that email is sent). An invite token joins its
  company and skips approval in every mode.
- `MAX_COMPANIES_PER_USER` (0 = unlimited) caps companies a user owns; over it, `POST /companies` is `403`.

All routes below require `Authorization: Bearer <access_token>`. Missing or invalid tokens get `401`.
The token carries only the user id: memberships and roles are read on every request.

## Company-scoped routes

Everything in the sections below lives under `/companies/{slug}`. An unknown slug and a company the
caller isn't a member of both give `404`. A suspended company gives `403` for that company only.
Roles rank `owner` > `admin` > `member`; insufficient role gives `403`.

| Method | Path | Min role | Body | Response |
|---|---|---|---|---|
| GET | `/companies/{slug}` | member | — | `{id, name, slug, status, role}` |
| PATCH | `/companies/{slug}` | owner | `{name}` | renamed company; the slug never changes |
| DELETE | `/companies/{slug}` | owner | — | `204`; removes memberships, invites, departments, documents, files, vectors, conversations |
| GET | `/companies/{slug}/stats` | admin | — | `{messages_per_day, document_count, estimated_cost_usd, documents_per_user, cost_per_day}` |

### Members

| Method | Path | Min role | Body | Response |
|---|---|---|---|---|
| GET | `/members` | admin | — | `[{user_id, email, display_name, role, department_id, department_name, joined_at}]` |
| PATCH | `/members/{user_id}` | admin | `{role?, department_id?}` | member; `department_id: null` clears it |
| DELETE | `/members/{user_id}` | member (self) / admin | — | `204`; their uploads stay, their conversations here are deleted |
| POST | `/transfer-ownership` | owner | `{user_id}` | new owner; previous owner becomes admin |

Rules: only the owner changes roles (`admin`/`member`; ownership moves by transfer only); an admin
manages members only; nobody changes their own role; the owner can't leave or be removed (`409`)
until ownership is transferred.

### Invites

| Method | Path | Min role | Body | Response |
|---|---|---|---|---|
| POST | `/invites` | admin | `{email, role, department_id?}` | `201 {id, email, role, department_id, expires_at, created_at, token}` |
| GET | `/invites` | admin | — | pending invites (no token) |
| DELETE | `/invites/{id}` | admin | — | `204` |

The token is returned once (only its hash is stored); the web app turns it into `/invite/{token}`.
Invites are bound to the email, single-use, expire after 7 days, and a new invite for the same email
replaces the old one. Only the owner can invite admins. Inviting an existing member is `409`. No email is sent.

### Departments

| Method | Path | Min role | Body | Response |
|---|---|---|---|---|
| GET | `/departments` | member | — | `[{id, name, company_id, created_at}]` |
| POST | `/departments` | admin | `{name}` | `201` department |
| DELETE | `/departments/{id}` | admin | — | `204` |

## Chat

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/companies/{slug}/chat` | `multipart/form-data`: `message`, `conversation_id?`, `files` (0-5) | SSE stream (see below) |

- `message` may be empty when files are attached. Neither text nor files gives `422`.
- Attachments: PNG, JPG, WEBP, GIF, PDF, DOCX, PPTX, MD, TXT, CSV (by extension), each
  up to `MAX_UPLOAD_SIZE_MB`. Bad type/count gives `400`, oversize gives `413`, before
  anything is stored. Attachments are private to the conversation and never indexed.
- Answers may embed pictures from retrieved documents as `![caption](/documents/{id}/images/{n})`; the path is relative to `/companies/{slug}`.
- Retrieval only searches the current company, filtered by the caller's role and department there.
- `MAX_MESSAGES_PER_COMPANY_PER_DAY` (0 = unlimited) caps chat messages per company per day; over it gives `403` with a message naming the limit.

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

Paths are under `/companies/{slug}`; each user sees only their own conversations in that company.

| Method | Path | Response |
|---|---|---|
| POST | `/conversations` | `{id, title, created_at, updated_at}` — title defaults to "New chat" |
| GET | `/conversations` | `[{id, title, created_at, updated_at}]` newest (`updated_at` desc) first |
| GET | `/conversations/{id}/messages` | `[{id, role, content, sources, attachments, created_at}]` chronological; `attachments` is `[{filename, mime, size, truncated}]` or `null` |
| GET | `/conversations/{id}/messages/{message_id}/attachments/{n}` | The attached file (owner only, else `404`) |

`GET /conversations/{id}/messages` 404s if the conversation doesn't exist or isn't owned by the current user.

## Documents

Paths are under `/companies/{slug}`. Uploading and deleting need admin. Members see company-wide documents plus their department's. `MAX_DOCUMENTS_PER_COMPANY` (0 = unlimited) caps uploads with a `403` naming the limit.

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/documents` | multipart file | `{id, filename, status: "processing"}` |
| GET | `/documents` | — | `[{id, filename, status, chunk_count, error_message, created_at}]` |
| DELETE | `/documents/{id}` | — | `204` |
| GET | `/documents/{id}/images/{n}` | — | PNG of a picture kept from the document at ingestion; same visibility rules as the document, else `404` |

`status` transitions: `processing` → `ready` \| `failed`.

## Instance administration

Instance admins only (`403` otherwise). These routes never expose a company's documents or chats; an
instance admin needs an ordinary membership for that. Bootstrap the first one with
`python -m app.cli create-instance-admin`.

| Method | Path | Response |
|---|---|---|
| GET | `/instance/users?approval_status=` | `[{id, email, display_name, is_instance_admin, approval_status, companies: [{name, slug, role}], created_at}]` |
| PATCH | `/instance/users/{id}/approve` \| `/reject` | user |
| DELETE | `/instance/users/{id}` | `204`; `409` if they own a company |
| GET | `/instance/companies` | `[{id, name, slug, status, member_count, created_at, updated_at}]` |
| PATCH | `/instance/companies/{id}/suspend` \| `/activate` | company |
| DELETE | `/instance/companies/{id}` | `204` |
| GET | `/instance/stats` | instance-wide usage, same shape as company stats |

## Health

| Method | Path | Response |
|---|---|---|
| GET | `/healthz` | `{status: "ok"}` |
