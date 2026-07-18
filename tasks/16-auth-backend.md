# Task 16: Auth Backend

**Feature:** Authentication (Day 16)
**Branch:** `feat/auth-backend`

**Description:** `/auth/register` and `/auth/login` (JWT via python-jose, bcrypt hashing via passlib), `get_current_user` dependency, protect all routes, scope conversations/documents to their owner.

**Acceptance criteria:**
- [ ] Register + login return a JWT; passwords bcrypt-hashed
- [ ] All routes require a valid token (401 otherwise)
- [ ] Conversations and documents scoped by `user_id` — user A cannot read user B's data
- [ ] Hardcoded user from Task 02 removed

**Verification:**
- [ ] Requests without a token → 401
- [ ] Two test users: cross-access attempts return 404/403

**Dependencies:** Task 15

**Files likely touched:** backend/app/routers/auth.py, backend/app/services/auth.py, backend/app/deps.py, backend/app/routers/* (protection)

**Estimated scope:** M
