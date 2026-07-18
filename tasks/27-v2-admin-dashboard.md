# Task 27 (v2): Admin Dashboard

**Feature:** Usage stats UI (Days 29–30)
**Branch:** `feat/admin-dashboard`

**Description:** Admin-only page: usage stats, per-user doc counts, cost over time. Builds on the Task 22 stats endpoint.

**Acceptance criteria:**
- [ ] Admin role gate (`users.role = 'admin'`) on API + page
- [ ] Messages/day, docs per user, and cost-over-time charts
- [ ] Non-admins get 403 / redirected

**Verification:**
- [ ] Log in as admin → see stats; as member → denied

**Dependencies:** Tasks 22 and 24

**Estimated scope:** M
