"""Compare all retrieval configurations on identical questions, corpus and source-page labels."""

import hashlib
import json
import statistics
import time

from backend.config import ROOT, settings
from backend.database import documents, now
from backend.embeddings import identity
from backend.rag import search
from backend.schemas import Filters, Query


def load_cases(path=None):
    return json.loads(
        (path or ROOT / "evaluation/datasets/financial-v2.json").read_text()
    )


def query_for(case, mode="hybrid"):
    docs = documents()
    ids = [d["id"] for d in docs if d["title"] in case.get("document_titles", [])]
    return Query(
        question=case["question"],
        k=5,
        retrieval_mode=mode,
        filters=Filters(title=case.get("title"), document_ids=ids or None),
    )


def relevance(case, evidence):
    gold = {
        (g["source_url"], p) for g in case.get("gold_sources", []) for p in g["pages"]
    }
    found = {(e["source_url"], e["page"]) for e in evidence}
    ranks = [
        i for i, e in enumerate(evidence, 1) if (e["source_url"], e["page"]) in gold
    ]
    return (
        len(gold & found) / len(gold) if gold else None,
        1 / min(ranks) if ranks else (0 if gold else None),
    )


def run(dataset_path=None, output_name="retrieval-comparison"):
    dataset_path = dataset_path or ROOT / "evaluation/datasets/financial-v2.json"
    cases = load_cases(dataset_path)
    outcomes = {}
    metrics = {}
    for mode in ["keyword", "vector", "hybrid"]:
        results = []
        for case in cases:
            started = time.perf_counter()
            evidence = search(query_for(case, mode), gate=False)
            latency = (time.perf_counter() - started) * 1000
            recall, mrr = relevance(case, evidence)
            results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "page_recall_at_5": recall,
                    "reciprocal_rank": mrr,
                    "latency_ms": round(latency, 2),
                    "sources": [
                        {
                            "chunk_id": e["chunk_id"],
                            "source_url": e["source_url"],
                            "page": e["page"],
                        }
                        for e in evidence
                    ],
                }
            )
        outcomes[mode] = results
        relevant = [r for r in results if r["page_recall_at_5"] is not None]
        metrics[mode] = {
            "page_recall_at_5": statistics.mean(
                r["page_recall_at_5"] for r in relevant
            ),
            "mrr_at_5": statistics.mean(r["reciprocal_rank"] for r in relevant),
            "mean_latency_ms": statistics.mean(r["latency_ms"] for r in results),
            "n_questions": len(results),
            "n_positive_questions": len(relevant),
        }
    result = {
        "run_at": now(),
        "database": "postgresql"
        if settings.database_url.startswith("postgresql")
        else "sqlite",
        "model": identity(),
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "corpus": [
            {"source_url": d["source_url"], "sha256": d["content_hash"]}
            for d in documents()
        ],
        "method": "Ungated candidate page Recall@5 and MRR@5. Keyword: PostgreSQL English OR query + ts_rank_cd. Vector: cosine. Hybrid: reciprocal rank fusion, constant 60, top 60 candidates per channel. Same page labels and filters for every configuration. Latency includes first-use model loading, not an isolated service load test.",
        "metrics": metrics,
        "outcomes": outcomes,
    }
    folder = ROOT / "evaluation/results"
    stamp = result["run_at"].replace(":", "-")
    (folder / (stamp + "-retrieval.json")).write_text(json.dumps(result, indent=2))
    (folder / (output_name + ".json")).write_text(json.dumps(result, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    run()
