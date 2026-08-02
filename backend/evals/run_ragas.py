"""RAGAS end-to-end scores for the answers the chat endpoint actually produces.

    uv run python -m evals.run_ragas --no-hybrid   # baseline
    uv run python -m evals.run_ragas              # hybrid + RRF

Every question is answered through app.services.rag.stream_answer, so the
prompt, retrieval, and model are the shipped ones. This calls the OpenAI API
once per question plus several judge calls per metric — use --limit while
iterating.
"""

import argparse
import os

from app.config import settings
from app.services import rag
from app.services.llm import get_llm_provider
from evals.harness import DEFAULT_CHUNK_SIZE, build_index, retrieve
from evals.metrics import load_dataset

_METRIC_COLUMNS = (
    "faithfulness",
    "answer_relevancy",
    "llm_context_precision_with_reference",
    "context_recall",
)


def _answer(question: str, contexts: list[str]) -> str:
    """Generate an answer from already-retrieved contexts, using the shipped prompt."""
    prompt = rag._SYSTEM_PROMPT + "\n\n<context>\n" + "\n\n---\n\n".join(contexts) + (
        f"\n</context>\n\nQuestion: {question}\nAnswer:"
    )
    return "".join(get_llm_provider().generate_answer_stream(prompt))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hybrid", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--limit", type=int, help="evaluate only the first N questions")
    args = parser.parse_args()

    # ragas builds its own OpenAI clients from the environment.
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    store = build_index(chunk_size=args.chunk_size)
    rows = load_dataset()[: args.limit]

    samples = []
    for i, row in enumerate(rows, start=1):
        contexts = [m["text"] for m in retrieve(row["question"], store, hybrid=args.hybrid)]
        print(f"  [{i}/{len(rows)}] {row['id']}", flush=True)
        samples.append(
            SingleTurnSample(
                user_input=row["question"],
                retrieved_contexts=contexts,
                response=_answer(row["question"], contexts),
                reference=row["ground_truth"],
            )
        )

    judge = LangchainLLMWrapper(ChatOpenAI(model=settings.chat_model, temperature=0))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=settings.embedding_model))
    result = evaluate(
        EvaluationDataset(samples=samples),
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
        ],
        llm=judge,
        embeddings=embeddings,
    )

    scores = result.to_pandas()[list(_METRIC_COLUMNS)].mean()
    label = "hybrid (dense + BM25, RRF)" if args.hybrid else "dense only"
    print(f"\n### RAGAS — {label}, {len(rows)} questions, judge={settings.chat_model}\n")
    print("| " + " | ".join(_METRIC_COLUMNS) + " |")
    print("| " + " | ".join("---" for _ in _METRIC_COLUMNS) + " |")
    print("| " + " | ".join(f"{scores[c]:.3f}" for c in _METRIC_COLUMNS) + " |")


if __name__ == "__main__":
    main()
