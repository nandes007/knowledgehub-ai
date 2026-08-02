import json
from pathlib import Path

import pytest

from evals.metrics import load_dataset, mean_reciprocal_rank, recall_at_k

_DATASET = Path(__file__).resolve().parent.parent / "evals" / "dataset.jsonl"


def test_recall_at_k_counts_only_the_top_k():
    # expected source sits at rank 3, so it counts at k=3 but not at k=2
    retrieved = ["a.md", "b.md", "c.md", "d.md"]
    assert recall_at_k(retrieved, ["c.md"], k=3) == 1.0
    assert recall_at_k(retrieved, ["c.md"], k=2) == 0.0


def test_recall_at_k_is_partial_for_multi_source_questions():
    retrieved = ["a.md", "b.md"]
    assert recall_at_k(retrieved, ["a.md", "z.md"], k=5) == 0.5


def test_recall_at_k_ignores_duplicate_retrievals():
    # several chunks of the same document must not inflate recall
    retrieved = ["a.md", "a.md", "a.md"]
    assert recall_at_k(retrieved, ["a.md", "b.md"], k=3) == 0.5


def test_mrr_uses_the_first_relevant_rank():
    assert mean_reciprocal_rank([(["x.md", "a.md"], ["a.md"])]) == 0.5
    assert mean_reciprocal_rank([(["a.md"], ["a.md"])]) == 1.0


def test_mrr_scores_zero_when_nothing_relevant_is_retrieved():
    assert mean_reciprocal_rank([(["x.md"], ["a.md"])]) == 0.0


def test_mrr_averages_over_questions():
    cases = [(["a.md"], ["a.md"]), (["x.md", "b.md"], ["b.md"])]
    assert mean_reciprocal_rank(cases) == pytest.approx(0.75)


def test_dataset_rows_are_well_formed_and_point_at_real_corpus_files():
    corpus = {p.name for p in (_DATASET.parent / "corpus").glob("*.md")}
    rows = load_dataset(_DATASET)

    assert 25 <= len(rows) <= 50
    assert len({r["id"] for r in rows}) == len(rows)
    for row in rows:
        assert row["question"].strip()
        assert row["ground_truth"].strip()
        assert row["expected_sources"], row["id"]
        assert set(row["expected_sources"]) <= corpus, row["id"]

    tags = {tag for row in rows for tag in row["tags"]}
    assert {"multi-doc", "table", "list-all"} <= tags


def test_dataset_file_is_valid_jsonl():
    for line in _DATASET.read_text(encoding="utf-8").splitlines():
        if line.strip():
            json.loads(line)
