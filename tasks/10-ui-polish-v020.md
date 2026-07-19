# Task 10: UI Polish + v0.2.0

**Feature:** Loading/error/empty states (Day 10)
**Branch:** `fix/ui-polish`

**Description:** Loading, error, and empty states (backend down, request failed, no conversations yet), keyboard submit, disabled states while streaming, reasonable mobile layout. Tag `v0.2.0`.

**Acceptance criteria:**
- [x] Backend down / failed request shows a friendly error, not a broken UI
- [x] Enter submits; input disabled while streaming
- [x] Empty state for no conversations; usable on mobile width

**Verification:**
- [x] Kill the backend mid-chat → friendly error
- [ ] Tag `v0.2.0` pushed — deferred until this PR merges to `main`; tagging a feature branch isn't the release point

**Dependencies:** Task 09

**Files likely touched:** frontend/components/*, frontend/app/*

**Estimated scope:** S

## Checkpoint: end of Phase 2
- [x] Full chat experience works in the browser (stream + history)
