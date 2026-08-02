"""Retrieval metrics for the eval harness.

Sources are compared by filename: the dataset says which document *should* be
retrieved, and the retriever returns chunks whose `filename` metadata we map
back to documents.
"""

import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
CORPUS_DIR = Path(__file__).resolve().parent / "corpus"


def load_dataset(path: Path | None = None) -> list[dict]:
    lines = (path or DATASET_PATH).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def recall_at_k(retrieved: list[str], expected: list[str], *, k: int) -> float:
    """Fraction of the expected documents that appear in the top-k results.

    Deduplicated on purpose: five chunks of the same document is one document
    found, not five.
    """
    found = set(retrieved[:k]) & set(expected)
    return len(found) / len(set(expected))


def mean_reciprocal_rank(cases: list[tuple[list[str], list[str]]]) -> float:
    """Mean of 1/rank of the first relevant document, over (retrieved, expected)."""
    total = 0.0
    for retrieved, expected in cases:
        for rank, source in enumerate(retrieved, start=1):
            if source in set(expected):
                total += 1 / rank
                break
    return total / len(cases) if cases else 0.0
