# Task 25 (v2): Department Visibility

**Feature:** Role-based document filtering (Days 26–27)
**Branch:** `feat/department-visibility`

**Description:** `department` + `visibility` metadata on documents; Chroma `where` filtering at query time based on the asking user's role; department selector on upload.

**Acceptance criteria:**
- [ ] Upload accepts department/visibility; stored in DB + chunk metadata
- [ ] Retrieval filters with Chroma `where` by user's role/department
- [ ] UI selector on upload; user in dept A never retrieves dept-B-only docs

**Verification:**
- [ ] Two users, two departments: cross-department questions return nothing from the other's docs

**Dependencies:** Task 24 (MVP shipped)

**Estimated scope:** M
