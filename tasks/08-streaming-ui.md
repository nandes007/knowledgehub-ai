# Task 08: Streaming UI

**Feature:** Live token rendering (Day 8)
**Branch:** `feat/streaming-ui`

**Description:** Consume SSE in `lib/sse.ts`; render tokens live with auto-scroll, a "thinking" indicator, and markdown rendering via `react-markdown`.

**Acceptance criteria:**
- [x] `lib/sse.ts` parses token events and the final `done` event
- [x] Tokens render live with auto-scroll
- [x] "Thinking" indicator before first token; markdown rendered in answers

**Verification:**
- [x] Answers visibly stream token-by-token in the browser

**Dependencies:** Task 07

**Files likely touched:** frontend/lib/sse.ts, frontend/components/ChatPanel.tsx, frontend/components/MessageBubble.tsx

**Estimated scope:** M
