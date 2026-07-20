# Task 19: Ugly Inputs + v0.4.0

**Feature:** Upload robustness (Day 19, includes Day 20 buffer)
**Branch:** `fix/ugly-inputs`

**Description:** Max file size limit, scanned-PDF detection (near-empty extraction → `failed` with a clear message, OCR fallback only if time allows), corrupt files, unsupported types, duplicate detection via `file_hash`. Use the Day 20 buffer for slippage, then tag `v0.4.0`.

**Acceptance criteria:**
- [x] Oversized / corrupt / unsupported / scanned files all yield clear user-facing errors, never a 500
- [x] Duplicate upload (same `file_hash`) detected and reported
- [x] Errors surfaced in the document table UI

**Verification:**
- [x] Throw a folder of bad files at it: every one fails gracefully
- [x] Tag `v0.4.0` pushed

**Dependencies:** Task 18

**Files likely touched:** backend/app/routers/documents.py, backend/ingestion/convert.py, backend/ingestion/pipeline.py, frontend/components/DocumentTable.tsx

**Estimated scope:** M

## Checkpoint: end of Phase 4
- [x] Auth + citations + graceful failures all verified
