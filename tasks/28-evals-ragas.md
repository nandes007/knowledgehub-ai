# Task 28: AI Evaluation (RAGAS + retrieval metrics)

**Feature:** Measurable retrieval quality (Phase 7, Days 31–35 — intentionally last)
**Branch:** `feat/evals`

**Description:** Build an eval set, baseline retrieval metrics, run RAGAS end-to-end, run one improvement experiment, write it up. This produces your strongest interview sentence: "recall@5 went from X% to Y% after Z."

**Acceptance criteria:**
- [x] `backend/evals/dataset.jsonl`: 25–50 question → expected-source pairs, including hard cases (multi-doc, tables, "list all X")
- [x] Script computes recall@k / MRR; baseline recorded in `docs/evals.md`
- [x] RAGAS run (faithfulness, answer relevancy, context precision/recall); baseline recorded
- [x] One experiment (chunk size, contextual descriptions, or reranker) measured against baseline
- [x] `docs/evals.md` has methodology, results table, next steps; linked from README

**Verification:**
- [x] Results table shows baseline vs. experiment numbers for the same dataset

**Dependencies:** Task 24 (needs a real knowledge base to evaluate)

**Files likely touched:** evals/dataset.jsonl, evals/run_retrieval_metrics.py, evals/run_ragas.py, docs/evals.md, README.md

**Estimated scope:** L — split into per-day issues on GitHub if it drags

## Outcome

- Corpus and dataset live in `backend/evals/` (importable next to `app`/`ingestion`), not repo root.
- 13-document corpus with superseded and neighbouring documents as distractors; 50 tagged questions.
- Baseline dense retrieval: recall@1 0.850, MRR 0.950, RAGAS faithfulness 0.937.
- Experiment: hybrid + RRF measured **slightly worse** overall (recall@1 0.840, context precision 0.930 → 0.880), better only on the `multi-doc` slice. Written up with the caveat that the dataset lacks the exact-identifier queries BM25 was added for.
- Second experiment (chunk size 400/1200) was a no-op: header-aware splitting already bounds sections below 800 chars.
- `HYBRID_SEARCH` default left unchanged — see next steps in `docs/evals.md`.
