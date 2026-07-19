# Task 09: Conversation History UI

**Feature:** Sidebar history (Day 9)
**Branch:** `feat/history-ui`

**Description:** Sidebar loads real conversations, click to open, "New chat" creates one, active conversation highlighted, auto-title from first message.

**Acceptance criteria:**
- [x] Sidebar lists real conversations (newest first)
- [x] Click opens `chat/[conversationId]`; active one highlighted
- [x] "New chat" creates a conversation; title auto-set from first message

**Verification:**
- [x] Refresh the page: every past conversation is still there and openable

**Dependencies:** Task 08

**Files likely touched:** frontend/components/Sidebar.tsx, frontend/app/chat/[conversationId]/*, frontend/lib/api.ts

**Estimated scope:** M
