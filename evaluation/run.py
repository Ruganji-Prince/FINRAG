import hashlib
import json
import statistics

from backend.config import ROOT, settings
from backend.database import now, rows
from backend.embeddings import identity
from backend.rag import answer
from backend.schemas import Filters, Query


def run():
    dataset = ROOT / "evaluation/datasets/benchmark.json"
    cases = json.loads(dataset.read_text())
    corpus = rows("SELECT id,title,source_url,content_hash FROM documents")
    missing = {c["source_url"] for c in cases if c.get("source_url")} - {
        d["source_url"] for d in corpus
    }
    if missing:
        raise SystemExit("Ingest required benchmark documents first: " + str(missing))
    outcomes = []
    recalls = []
    rr = []
    citations = []
    abstentions = []
    for case in cases:
        query = Query(
            question=case["question"], k=5, filters=Filters(title=case.get("title"))
        )
        result = answer(query)
        evidence = result["evidence"]
        expected = set(case.get("pages", []))
        found = {
            e["page"] for e in evidence if e["source_url"] == case.get("source_url")
        }
        recall = len(expected & found) / len(expected) if expected else None
        ranks = [
            rank
            for rank, e in enumerate(evidence, 1)
            if e["source_url"] == case.get("source_url") and e["page"] in expected
        ]
        reciprocal = 1 / min(ranks) if ranks else 0
        if expected:
            recalls.append(recall)
            rr.append(reciprocal)
        if case["category"] == "unsupported":
            abstentions.append(int(result["abstained"]))
        valid = []
        for e in evidence:
            exists = rows(
                "SELECT c.text,c.page,d.source_url FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=? AND d.id=?",
                (e["chunk_id"], e["document_id"]),
            )
            valid.append(
                bool(
                    exists
                    and exists[0]["text"] == e["text"]
                    and exists[0]["page"] == e["page"]
                    and e["citation_url"]
                    == exists[0]["source_url"].split("#")[0] + "#page=" + str(e["page"])
                )
            )
        citations.extend(valid)
        checks = [
            needle.lower() in " ".join(e["text"] for e in evidence).lower()
            for needle in case.get("expected_substrings", [])
        ]
        outcomes.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "recall_at_5": recall,
                "reciprocal_rank": reciprocal if expected else None,
                "abstained": result["abstained"],
                "expected_evidence_strings_found": all(checks) if checks else None,
                "latency_ms": result["latency_ms"],
                "chunk_ids": [e["chunk_id"] for e in evidence],
                "usage": result["usage"],
                "estimated_cost_usd": result["estimated_cost_usd"],
            }
        )
    latencies = [o["latency_ms"] for o in outcomes]
    result = {
        "status": "completed",
        "run_at": now(),
        "database": settings.database_url.split(":")[0],
        "embedding_model": identity(),
        "answer_provider": settings.llm_provider,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "corpus": corpus,
        "n": len(outcomes),
        "k": 5,
        "methodology": "Automated page-level relevance labels, not exhaustive chunk-level relevance. Citation metric validates referential integrity, not factual entailment. Dataset authored against official PDF; independent human verification pending.",
        "metrics": {
            "page_recall_at_5": statistics.mean(recalls) if recalls else None,
            "mrr_at_5": statistics.mean(rr) if rr else None,
            "citation_integrity": statistics.mean(citations) if citations else None,
            "unsupported_abstention_rate": statistics.mean(abstentions)
            if abstentions
            else None,
            "mean_latency_ms": statistics.mean(latencies),
            "p95_latency_ms": sorted(latencies)[
                min(len(latencies) - 1, int(0.95 * len(latencies)))
            ],
            "answer_faithfulness": None,
            "human_verified_accuracy": None,
        },
        "outcomes": outcomes,
    }
    path = ROOT / "evaluation/results"
    path.mkdir(parents=True, exist_ok=True)
    stamp = result["run_at"].replace(":", "-")
    (path / (stamp + ".json")).write_text(json.dumps(result, indent=2))
    (path / "latest.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    run()
