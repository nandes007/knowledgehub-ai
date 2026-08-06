# Retrieval and answer evaluation

How good is retrieval, and did the changes we shipped actually help? This page
records the method, the numbers, and what they say to do next.

Everything here is reproducible from the repo — no production data required.

```bash
cd backend
uv sync --extra evals

# retrieval metrics (embeddings only, cents per run)
uv run python -m evals.run_retrieval_metrics --no-hybrid   # baseline
uv run python -m evals.run_retrieval_metrics               # hybrid + RRF

# RAGAS end-to-end (answers + LLM judge, a few tens of cents per run)
uv run python -m evals.run_ragas --no-hybrid
uv run python -m evals.run_ragas
```

## Methodology

**Corpus** — `backend/evals/corpus/`, 13 markdown documents for the fictional
company the assistant already answers as. It deliberately contains material
that punishes lazy retrieval:

- two *superseded* policies (`salary-bands-2025-archived.md`,
  `expense-policy-2024-archived.md`) whose numbers are plausible but wrong
- two *neighbouring* documents (`jakarta-office-guide.md`,
  `sales-team-handbook.md`) that share vocabulary with the real answers
  without containing them

**Dataset** — `backend/evals/dataset.jsonl`, 50 question → expected-source
pairs with a written ground truth. Each row is tagged so results can be sliced:

| Tag | Questions | What it tests |
| --- | --- | --- |
| `simple` | 22 | One fact, one document |
| `numeric` | 16 | A specific figure or deadline |
| `table` | 12 | The answer only exists in a markdown table |
| `distractor` | 11 | A superseded or neighbouring document competes |
| `multi-doc` | 6 | The full answer needs two documents |
| `list-all` | 3 | Enumerate every item ("list all severity levels") |

**Retrieval metrics** — computed at document level over the top-5 chunks the
chat endpoint would use. `recall@k` is the fraction of a question's expected
documents appearing in the top *k* chunks, averaged over questions; documents
are deduplicated, so five chunks of one file count once. `MRR` is the mean
reciprocal rank of the first relevant chunk. The scripts call
`app.services.rag._retrieve` directly, so the numbers describe the shipped
retriever rather than a reimplementation of it.

**RAGAS** — every question is answered with the production system prompt and
`gpt-4o-mini`, then judged by `gpt-4o-mini` on faithfulness, answer relevancy,
context precision (with reference), and context recall.

## Baseline: dense retrieval

`text-embedding-3-small`, chunk size 800, top-5, no BM25.

| Slice | Questions | recall@1 | recall@3 | recall@5 | MRR |
| --- | --- | --- | --- | --- | --- |
| all | 50 | 0.850 | 0.990 | 1.000 | 0.950 |
| distractor | 11 | 0.636 | 1.000 | 1.000 | 0.864 |
| list-all | 3 | 1.000 | 1.000 | 1.000 | 1.000 |
| multi-doc | 6 | 0.417 | 0.917 | 1.000 | 0.917 |
| numeric | 16 | 0.812 | 1.000 | 1.000 | 0.906 |
| simple | 22 | 0.955 | 1.000 | 1.000 | 0.977 |
| table | 12 | 0.792 | 1.000 | 1.000 | 0.917 |

| faithfulness | answer_relevancy | context_precision | context_recall |
| --- | --- | --- | --- |
| 0.937 | 0.832 | 0.930 | 0.977 |

Reading it: the right document is essentially always in the top 5, so
`recall@5` carries no signal on a corpus this size. The discriminating numbers
are `recall@1` and `MRR`, and the weak slices are the deliberate hard cases —
`multi-doc` at 0.417 (the second document rarely ranks first) and `distractor`
at 0.636 (an archived policy sometimes outranks the current one).

## Experiment 1: hybrid retrieval (dense + BM25, fused with RRF)

The change already shipped behind `HYBRID_SEARCH`: retrieve 20 candidates from
each of dense and BM25, fuse with reciprocal rank fusion, keep the top 5. Same
corpus, same dataset, same chunking — only the flag changes.

| Metric | Baseline (dense) | Hybrid + RRF | Δ |
| --- | --- | --- | --- |
| recall@1 | 0.850 | 0.840 | −0.010 |
| recall@3 | 0.990 | 0.980 | −0.010 |
| recall@5 | 1.000 | 0.990 | −0.010 |
| MRR | 0.950 | 0.950 | 0.000 |
| faithfulness | 0.937 | 0.917 | −0.020 |
| answer_relevancy | 0.832 | 0.828 | −0.004 |
| context_precision | 0.930 | 0.880 | −0.050 |
| context_recall | 0.977 | 0.957 | −0.020 |

**Hybrid retrieval did not pay for itself on this dataset.** Eight of nine
measurements moved slightly down or stayed flat, and the two runs are
independent (retrieval metrics use no LLM; RAGAS does), which makes a
consistent small regression more credible than noise.

It is not uniformly worse. On the `multi-doc` slice hybrid beats dense on the
metrics that matter there — `recall@1` 0.500 vs 0.417 and `MRR` 1.000 vs 0.917
— because BM25 surfaces the second, less semantically-central document. It
loses on `simple` questions, where BM25 pulls in keyword-matching chunks from
the archived and neighbouring documents and RRF promotes them.

The honest caveat: BM25 was added for exact-identifier queries (invoice
numbers, ticket IDs, error codes), and **this dataset barely contains any**.
The experiment shows hybrid doesn't help *these* questions; it does not show
BM25 is useless. That gap is the first item in next steps.

## Experiment 2: chunk size

Re-ingested the corpus at chunk sizes 400 and 1200 against the 800 baseline.
Results were **identical at every k on every slice**. The cause is visible in
the chunk counts: 97 chunks at 400, 90 at both 800 and 1200. Header-aware
splitting already cuts the corpus at `#`/`##` boundaries, and almost every
resulting section is under 800 characters, so the character splitter rarely
fires. Chunk size is not a lever on markdown documents shaped like these.

## What this says to do next

1. **Add exact-identifier questions to the dataset.** Ticket IDs, invoice
   numbers, error codes, and product SKUs are what BM25 was built for and what
   real employees search. Until the eval covers them, the hybrid flag is being
   judged on questions it was never meant to win.
2. **Re-decide the `HYBRID_SEARCH` default after (1).** On current evidence
   hybrid costs a little accuracy for no measured gain, but the evidence is
   incomplete in a known direction. Don't flip the default on this data alone.
3. **Make `recall@5` mean something.** A corpus of 13 documents saturates it.
   Either grow the corpus toward a realistic few hundred documents or move to
   chunk-level ground truth, where "which passage" is a real question.
4. **Attack the `multi-doc` slice.** `recall@1` of 0.417 is the worst number
   on the page. Query decomposition or simply retrieving more candidates
   before fusion are the cheap things to try first.
5. **Run each configuration more than once.** Every number here is a single
   run. The deltas in experiment 1 are small enough that run-to-run variance
   has not been ruled out; repeat runs with a variance band before treating
   a 0.01 difference as real.

## Limitations

- The corpus is synthetic. It is realistic in shape and deliberately
  adversarial, but it is not this company's actual knowledge base.
- Ground truth is single-annotator (the author's) and written alongside the
  corpus, which biases toward questions the corpus answers cleanly.
- Judge and generator are the same model (`gpt-4o-mini`), which is known to
  inflate faithfulness scores.
- Metrics are document-level. A retriever that returns the right document with
  the wrong passage scores full marks here.
