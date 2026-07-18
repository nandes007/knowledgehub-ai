# Task 17: Auth Frontend

**Feature:** Login/register UI (Day 17)
**Branch:** `feat/auth-frontend`

**Description:** Login/register pages, token storage, authenticated fetch wrapper, redirect unauthenticated users, logout.

**Acceptance criteria:**
- [ ] `(auth)/login` and `(auth)/register` pages work
- [ ] Token attached to every API call (including SSE)
- [ ] Unauthenticated visits redirect to login; logout clears the session

**Verification:**
- [ ] Fresh browser → register → land in an empty, private workspace

**Dependencies:** Task 16

**Files likely touched:** frontend/app/(auth)/*, frontend/lib/api.ts, frontend/lib/sse.ts

**Estimated scope:** M
