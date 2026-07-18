# Task 28: AI Evaluation (RAGAS + retrieval metrics)

**Feature:** Measurable retrieval quality (Phase 7, Days 31–35 — intentionally last)
**Branch:** `feat/evals`

**Description:** Build an eval set, baseline retrieval metrics, run RAGAS end-to-end, run one improvement experiment, write it up. This produces your strongest interview sentence: "recall@5 went from X% to Y% after Z."

**Acceptance criteria:**
- [ ] `evals/dataset.jsonl`: 25–50 question → expected-source pairs, including hard cases (multi-doc, tables, "list all X")
- [ ] Script computes recall@k / MRR; baseline recorded in `docs/evals.md`
- [ ] RAGAS run (faithfulness, answer relevancy, context precision/recall); baseline recorded
- [ ] One experiment (chunk size, contextual descriptions, or reranker) measured against baseline
- [ ] `docs/evals.md` has methodology, results table, next steps; linked from README

**Verification:**
- [ ] Results table shows baseline vs. experiment numbers for the same dataset

**Dependencies:** Task 24 (needs a real knowledge base to evaluate)

**Files likely touched:** evals/dataset.jsonl, evals/run_retrieval_metrics.py, evals/run_ragas.py, docs/evals.md, README.md

**Estimated scope:** L — split into per-day issues on GitHub if it drags
