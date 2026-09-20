"""
Retrieval evaluation harness.

Measures retrieval quality against a golden set so tuning decisions
(thresholds, hybrid weights, reranking) are driven by numbers instead of
intuition.

Metrics:
  - hit@k : fraction of questions whose expected document appears in top-k
  - MRR   : mean reciprocal rank of the first correct result
  - score distribution: min/avg/max similarity, used to calibrate
    `retrieval_min_score` and `retrieval_low_relevance_threshold`

Usage:
    python -m scripts.eval_retrieval                 # both modes
    python -m scripts.eval_retrieval --mode dense    # dense only
    python -m scripts.eval_retrieval --mode hybrid   # hybrid only
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.core.domain import SearchResult  # noqa: E402
from app.infrastructure.chroma_vector_store import ChromaVectorStore  # noqa: E402
from app.infrastructure.hybrid_retriever import HybridRetriever  # noqa: E402
from app.infrastructure.openrouter_embedding import OpenRouterEmbedding  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


@dataclass
class GoldenCase:
    """A single question with its expected source document."""

    question: str
    expected_source: str
    # Optional keywords that must appear in at least one retrieved chunk.
    expected_keywords: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Golden set — built from the documents currently in the vector store.
# `expected_source` matches the `original_filename` chunk metadata.
# ---------------------------------------------------------------------------

GOLDEN_SET: List[GoldenCase] = [
    # --- English documents (final report.txt) ---
    GoldenCase(
        "What is the Test Lamp methodology in SMPS diagnostics?",
        "final report.txt",
        ["lamp"],
    ),
    GoldenCase(
        "What are the cold mode benchmarks for a bridge rectifier?",
        "final report.txt",
        ["bridge"],
    ),
    GoldenCase(
        "What causes a clicking or slow-to-start power supply?",
        "final report.txt",
        ["vcc"],
    ),
    GoldenCase(
        "How do I measure the switching frequency of an SMPS?",
        "final report.txt",
        ["frequenc"],
    ),
    GoldenCase(
        "What does the half-voltage rule indicate?",
        "final report.txt",
        ["half"],
    ),
    GoldenCase(
        "What is the role of the optocoupler and TL431 in the feedback loop?",
        "final report.txt",
        ["tl431"],
    ),
    GoldenCase(
        "Why must the main filter capacitor be discharged before cold testing?",
        "final report.txt",
        ["capacitor"],
    ),
    GoldenCase(
        "Component verification using multimeter diode mode",
        "final report.txt",
        ["diode"],
    ),
    GoldenCase(
        "What does a sustained bright test lamp indicate?",
        "final report.txt",
        ["lamp"],
    ),
    GoldenCase(
        "Symptom: dead power supply with no 300V rail",
        "final report.txt",
        ["300v"],
    ),
    # --- Persian documents (p*.txt) ---
    # The Persian corpus discusses the same subject in Persian, so a Persian
    # question must retrieve the Persian chunks. Expecting the English
    # document here would be measuring the golden set, not the retriever.
    GoldenCase(
        "روشن ماندن لامپ تست در منبع تغذیه سوئیچینگ نشانه چیست؟",
        "p9.txt",
        ["لامپ"],
    ),
    GoldenCase(
        "استفاده از لامپ تست چه فایده‌ای دارد؟",
        "p1.txt",
        ["لامپ"],
    ),
    GoldenCase(
        "چطور مقاومت استارت‌آپ را تست کنیم؟",
        "p10.txt",
        ["استارت"],
    ),
]


def _matches(result: SearchResult, case: GoldenCase) -> bool:
    """Return True when a result is attributable to the expected source."""
    metadata = result.chunk.metadata or {}
    source = str(
        metadata.get("original_filename") or metadata.get("source") or ""
    ).split("/")[-1]
    if not source:
        return False
    if case.expected_source.lower() not in source.lower():
        return False
    if not case.expected_keywords:
        return True
    text = (result.chunk.text or "").lower()
    return all(k.lower() in text for k in case.expected_keywords)


def evaluate(
    retriever_fn: Callable[[str], List[SearchResult]],
    cases: List[GoldenCase],
    top_k: int,
    label: str,
) -> dict:
    """
    Run a retriever over the golden set and compute metrics.

    Args:
        retriever_fn: Callable mapping a question to ranked results.
        cases: Golden cases to evaluate.
        top_k: Cut-off for hit@k.
        label: Name of the mode being evaluated.

    Returns:
        A dict of computed metrics.
    """
    hits = 0
    reciprocal_ranks: List[float] = []
    all_scores: List[float] = []
    failures: List[GoldenCase] = []

    for case in cases:
        try:
            results = retriever_fn(case.question)
        except Exception as e:
            print(f"  ! retrieval error for {case.question[:40]!r}: {e}")
            failures.append(case)
            reciprocal_ranks.append(0.0)
            continue

        for r in results[:top_k]:
            all_scores.append(r.score)

        rank = 0
        for index, result in enumerate(results[:top_k], start=1):
            if _matches(result, case):
                rank = index
                break

        if rank:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
            failures.append(case)

    total = len(cases) or 1
    return {
        "label": label,
        "queries": len(cases),
        f"hit@{top_k}": hits / total,
        "mrr": sum(reciprocal_ranks) / total,
        "score_min": min(all_scores) if all_scores else 0.0,
        "score_avg": sum(all_scores) / len(all_scores) if all_scores else 0.0,
        "score_max": max(all_scores) if all_scores else 0.0,
        "failures": [c.question for c in failures],
    }


def print_report(report: dict, top_k: int) -> None:
    """Print a metrics report for one retrieval mode."""
    print(f"\n=== {report['label']} ===")
    print(f"  queries           : {report['queries']}")
    print(f"  hit@{top_k}           : {report[f'hit@{top_k}']:.3f}")
    print(f"  MRR               : {report['mrr']:.3f}")
    print(
        "  score min/avg/max : "
        f"{report['score_min']:.4f} / {report['score_avg']:.4f} / "
        f"{report['score_max']:.4f}"
    )
    if report["failures"]:
        print(f"  misses ({len(report['failures'])}):")
        for question in report["failures"]:
            print(f"    - {question[:70]}")


def main() -> int:
    """Run the evaluation and print a comparison report."""
    parser = argparse.ArgumentParser(description="Retrieval evaluation harness")
    parser.add_argument(
        "--mode",
        choices=["dense", "hybrid", "both"],
        default="both",
        help="Which retrieval mode(s) to evaluate",
    )
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    parser.add_argument(
        "--fetch-k",
        type=int,
        default=settings.fetch_k,
        help="Candidate pool size for retrieval",
    )
    args = parser.parse_args()

    vector_store = ChromaVectorStore()
    embedding = OpenRouterEmbedding()

    chunk_count = vector_store.count()
    print(f"Vector store chunks: {chunk_count}")
    if chunk_count == 0:
        print("ERROR: vector store is empty — ingest documents first.")
        return 1

    print(f"Embedding model : {settings.embedding_model}")
    print(f"top_k={args.top_k}  fetch_k={args.fetch_k}")

    reports: List[dict] = []

    if args.mode in ("dense", "both"):

        def dense_fn(question: str) -> List[SearchResult]:
            vec = embedding.embed_query(question)
            return vector_store.search(vec, args.fetch_k)

        reports.append(evaluate(dense_fn, GOLDEN_SET, args.top_k, "DENSE ONLY"))

    if args.mode in ("hybrid", "both"):
        hybrid = HybridRetriever(
            vector_store=vector_store,
            bm25_weight=settings.hybrid_bm25_weight,
        )

        def hybrid_fn(question: str) -> List[SearchResult]:
            vec = embedding.embed_query(question)
            return hybrid.search(question, vec, args.top_k, args.fetch_k)

        reports.append(
            evaluate(hybrid_fn, GOLDEN_SET, args.top_k, "HYBRID (BM25 + DENSE)")
        )

    for report in reports:
        print_report(report, args.top_k)

    if len(reports) == 2:
        dense, hybrid = reports
        delta = hybrid[f"hit@{args.top_k}"] - dense[f"hit@{args.top_k}"]
        print("\n=== COMPARISON ===")
        print(f"  hit@{args.top_k} delta (hybrid - dense): {delta:+.3f}")
        print(f"  MRR delta               : {hybrid['mrr'] - dense['mrr']:+.3f}")

    # Persist raw numbers so threshold calibration can reference them later.
    out = Path("data/eval_retrieval_last.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "embedding_model": settings.embedding_model,
                "top_k": args.top_k,
                "fetch_k": args.fetch_k,
                "reports": reports,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
