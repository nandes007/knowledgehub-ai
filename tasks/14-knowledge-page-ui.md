# Task 14: Knowledge Page UI

**Feature:** Upload + document table (Day 14)
**Branch:** `feat/knowledge-page`

**Description:** Drag-and-drop upload (`UploadDropzone`), document table with live status (poll every 3–5s), delete with confirmation.

**Acceptance criteria:**
- [x] Drag-and-drop or click-to-upload works for PDF/DOCX/PPTX/MD
- [x] Table shows filename, status, uploaded date; status polls until `ready`/`failed`
- [x] Delete asks for confirmation, then removes the row

**Verification:**
- [x] Upload in browser → watch status flip to *ready* → doc appears in table

**Dependencies:** Tasks 10 and 13

**Files likely touched:** frontend/app/knowledge/*, frontend/components/UploadDropzone.tsx, frontend/components/DocumentTable.tsx, frontend/lib/api.ts

**Estimated scope:** M
