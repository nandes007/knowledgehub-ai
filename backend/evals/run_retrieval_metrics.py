"""Recall@k and MRR for the retriever, over evals/dataset.jsonl.

    uv run python -m evals.run_retrieval_metrics --no-hybrid   # baseline: dense only
    uv run python -m evals.run_retrieval_metrics               # experiment: hybrid + RRF

Prints a markdown table ready to paste into docs/evals.md.
"""

import argparse
from collections import defaultdict

from evals.harness import DEFAULT_CHUNK_SIZE, build_index, retrieve, retrieved_sources
from evals.metrics import load_dataset, mean_reciprocal_rank, recall_at_k

_KS = (1, 3, 5)


def _summarize(cases: list[tuple[list[str], list[str]]]) -> dict[str, float]:
    scores = {f"recall@{k}": sum(recall_at_k(r, e, k=k) for r, e in cases) / len(cases) for k in _KS}
    scores["mrr"] = mean_reciprocal_rank(cases)
    return scores


def _row(label: str, n: int, scores: dict[str, float]) -> str:
    cells = " | ".join(f"{scores[key]:.3f}" for key in (*(f"recall@{k}" for k in _KS), "mrr"))
    return f"| {label} | {n} | {cells} |"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hybrid", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--rebuild", action="store_true", help="re-ingest the corpus first")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    args = parser.parse_args()

    store = build_index(rebuild=args.rebuild, chunk_size=args.chunk_size)
    rows = load_dataset()

    cases: list[tuple[list[str], list[str]]] = []
    by_tag: dict[str, list[tuple[list[str], list[str]]]] = defaultdict(list)
    misses: list[tuple[str, list[str]]] = []

    for row in rows:
        sources = retrieved_sources(retrieve(row["question"], store, hybrid=args.hybrid))
        case = (sources, row["expected_sources"])
        cases.append(case)
        for tag in row["tags"]:
            by_tag[tag].append(case)
        if recall_at_k(*case, k=5) < 1.0:
            misses.append((row["id"], sources[:5]))

    label = "hybrid (dense + BM25, RRF)" if args.hybrid else "dense only"
    print(f"\n### Retrieval — {label}, chunk_size={args.chunk_size}\n")
    print("| Slice | Questions | recall@1 | recall@3 | recall@5 | MRR |")
    print("| --- | --- | --- | --- | --- | --- |")
    print(_row("all", len(cases), _summarize(cases)))
    for tag, tagged in sorted(by_tag.items()):
        print(_row(tag, len(tagged), _summarize(tagged)))

    if misses:
        print(f"\nIncomplete at k=5 ({len(misses)}):")
        for question_id, sources in misses:
            print(f"  {question_id}: {sources}")


if __name__ == "__main__":
    main()
