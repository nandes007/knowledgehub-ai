# Task 26 (v2): Hybrid Search + Rerank

**Feature:** Retrieval quality (Day 28)
**Branch:** `feat/hybrid-search`

**Description:** Add BM25 alongside dense retrieval, merge result sets, then rerank (cross-encoder or Cohere rerank).

**Acceptance criteria:**
- [ ] BM25 index kept in sync with document ingest/delete
- [ ] Merged dense + sparse candidates reranked before prompting
- [ ] Behind a config flag so dense-only remains the fallback

**Verification:**
- [ ] Keyword-heavy queries (exact names, codes) that dense search missed now retrieve correctly

**Dependencies:** Task 24; pairs well with Task 28 (evals) to measure the gain

**Estimated scope:** M
