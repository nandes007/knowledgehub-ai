# Task 11: Document Upload Endpoint

**Feature:** Knowledge upload (Day 11)
**Branch:** `feat/upload-endpoint`

**Description:** `POST /documents` (multipart): save file to the disk volume, insert a `documents` row with `status='processing'`, return immediately (202-style).

**Acceptance criteria:**
- [x] Multipart upload saves the file and computes `file_hash`
- [x] `documents` row inserted with `status='processing'`
- [x] Response returns document id + status without waiting for ingestion

**Verification:**
- [x] `curl -F file=@doc.pdf /documents` returns id + `processing`

**Dependencies:** Task 05 (backend only — can run parallel to frontend tasks 06–10)

**Files likely touched:** backend/app/routers/documents.py, backend/app/schemas/*, backend/app/config.py

**Estimated scope:** S
