"""Run actual generated answers; no mocked scores or LLM-as-human claims."""

import argparse
import hashlib
import json
import statistics
import time

from backend.config import ROOT, settings
from backend.database import documents, now, rows
from backend.embeddings import identity
from backend.rag import answer
from evaluation.compare_retrieval import load_cases, query_for, relevance


def run(
    limit=None,
    balanced=False,
    api_url=None,
    dataset_path=None,
    output_name="rag-latest",
):
    dataset_path = dataset_path or ROOT / "evaluation/datasets/financial-v2.json"
    available = json.loads(dataset_path.read_text()) if dataset_path else load_cases()
    if balanced:
        factual = [
            c
            for c in available
            if c["category"]
            not in ["unsupported", "cross_report_comparison", "revision_conflict"]
        ]
        unsupported = [c for c in available if c["category"] == "unsupported"]
        comparisons = [
            c
            for c in available
            if c["category"] in ["cross_report_comparison", "revision_conflict"]
        ]
        cases = factual[:16] + factual[-8:] + unsupported[:4] + comparisons
    else:
        cases = available[:limit]

    outcomes = []
    write(outcomes, cases, api_url, dataset_path, output_name)
    for case in cases:
        request_started = time.perf_counter()
        if api_url:
            import httpx

            response = httpx.post(
                api_url.rstrip("/") + "/ask",
                json=query_for(case).model_dump(),
                timeout=180,
            )
            response.raise_for_status()
            result = response.json()
        else:
            result = answer(query_for(case))
        recall, mrr = relevance(case, result["evidence"])
        by_id = {e["chunk_id"]: e for e in result["evidence"]}
        supported = []
        for claim in result["claims"]:
            ev = by_id.get(claim["chunk_id"])
            stored = (
                rows(
                    "SELECT c.text,c.page,d.source_url FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=? AND d.id=?",
                    (claim["chunk_id"], ev["document_id"]),
                )
                if ev
                else []
            )
            supported.append(
                bool(
                    stored
                    and claim["quote"] in " ".join(stored[0]["text"].split())
                    and stored[0]["page"] == ev["page"]
                    and stored[0]["source_url"] == ev["source_url"]
                    and ev["citation_url"]
                    == stored[0]["source_url"].split("#")[0]
                    + "#page="
                    + str(ev["page"])
                )
            )
        quoted = __import__("re").sub(
            r"\s+(?=%)", "", " ".join(c["quote"] for c in result["claims"]).lower()
        )
        anchors = [
            __import__("re").sub(r"\s+(?=%)", "", a.lower())
            for g in case.get("gold_sources", [])
            for a in g.get("anchors", [])
        ]
        outcome = {
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "mode": result["mode"],
            "abstained": result["abstained"],
            "answer": result["answer"],
            "claims": result["claims"],
            "page_recall_at_5": recall,
            "reciprocal_rank": mrr,
            "citation_quote_integrity": all(supported) if supported else None,
            "expected_anchor_coverage": sum(a in quoted for a in anchors) / len(anchors)
            if anchors
            else None,
            "latency_ms": result["latency_ms"],
            "client_round_trip_ms": round(
                (time.perf_counter() - request_started) * 1000, 2
            ),
            "usage": result["usage"],
            "estimated_api_cost_usd": result["estimated_cost_usd"],
        }
        outcomes.append(outcome)
        print(
            json.dumps(
                {
                    "id": case["id"],
                    "mode": result["mode"],
                    "abstained": result["abstained"],
                    "latency_ms": result["latency_ms"],
                    "client_round_trip_ms": round(
                        (time.perf_counter() - request_started) * 1000, 2
                    ),
                }
            ),
            flush=True,
        )
        # Save after each case so interrupted paid/local evaluation retains actual completed work.
        write(outcomes, cases, api_url, dataset_path, output_name)
    return write(outcomes, cases, api_url, dataset_path, output_name)


def write(outcomes, cases, api_url, dataset_path, output_name):
    cited = [
        o["citation_quote_integrity"]
        for o in outcomes
        if o["citation_quote_integrity"] is not None
    ]
    unsupported = [o["abstained"] for o in outcomes if o["category"] == "unsupported"]
    positive = [o for o in outcomes if o["category"] != "unsupported"]
    usage = [o["usage"] for o in outcomes if o["usage"]]
    costs = [
        o["estimated_api_cost_usd"]
        for o in outcomes
        if o["estimated_api_cost_usd"] is not None
    ]
    result = {
        "status": "completed" if len(outcomes) == len(cases) else "running",
        "run_at": now(),
        "context_policy_sha256": hashlib.sha256(
            (ROOT / "docs/query-policy.json").read_bytes()
        ).hexdigest(),
        "backend_source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "backend").glob("*.py"))
        },
        "model_revision": settings.local_llm_revision
        if settings.llm_provider == "local"
        else None,
        "provider": settings.llm_provider,
        "execution_transport": "FastAPI HTTP" if api_url else "in-process",
        "model": settings.local_llm_model
        if settings.llm_provider == "local"
        else settings.llm_model,
        "local_quantization": "dynamic_int8"
        if settings.llm_provider == "local" and settings.local_llm_quantize
        else ("float32" if settings.llm_provider == "local" else None),
        "embedding_model": identity(),
        "database": "postgresql"
        if settings.database_url.startswith("postgresql")
        else "sqlite",
        "n": len(outcomes),
        "planned": len(cases),
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "corpus": [
            {"source_url": d["source_url"], "sha256": d["content_hash"]}
            for d in documents()
        ],
        "methodology": "Real provider inference. Quote/citation correctness and extractive faithfulness are exact-source checks, not independently human-scored semantic relevance. Anchor coverage is a heuristic diagnostic; it does not prove answer correctness. Small local LLM uses evidence-constrained decoding. No free-form unsupported model prose is published.",
        "metrics": {
            "page_recall_at_5": statistics.mean(o["page_recall_at_5"] for o in positive)
            if positive
            else None,
            "mrr_at_5": statistics.mean(o["reciprocal_rank"] for o in positive)
            if positive
            else None,
            "citation_quote_integrity": statistics.mean(cited) if cited else None,
            "extractive_claim_support": statistics.mean(cited) if cited else None,
            "unsupported_abstention_rate": statistics.mean(unsupported)
            if unsupported
            else None,
            "positive_question_abstention_rate": statistics.mean(
                o["abstained"] for o in positive
            )
            if positive
            else None,
            "mean_expected_anchor_coverage": statistics.mean(
                o["expected_anchor_coverage"] for o in positive
            )
            if positive
            else None,
            "mean_latency_ms": statistics.mean(o["latency_ms"] for o in outcomes)
            if outcomes
            else None,
            "mean_client_round_trip_ms": statistics.mean(
                o["client_round_trip_ms"] for o in outcomes
            )
            if outcomes
            else None,
            "prompt_tokens": sum(u.get("prompt_tokens", 0) for u in usage),
            "completion_tokens": sum(u.get("completion_tokens", 0) for u in usage),
            "estimated_api_cost_usd": sum(costs) if costs else None,
            "human_verified_accuracy": None,
            "semantic_entailment_judge": None,
        },
        "outcomes": outcomes,
    }
    folder = ROOT / "evaluation/results"
    checkpoint = folder / (output_name + ".json.tmp")
    checkpoint.write_text(json.dumps(result, indent=2))
    checkpoint.replace(folder / (output_name + ".json"))
    if result["status"] == "completed":
        (
            folder / (result["run_at"].replace(":", "-") + "-" + output_name + ".json")
        ).write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--balanced", action="store_true")
    parser.add_argument("--api-url")
    parser.add_argument("--dataset", type=__import__("pathlib").Path)
    parser.add_argument("--output-name", default="rag-latest")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.limit, args.balanced, args.api_url, args.dataset, args.output_name
            )["metrics"],
            indent=2,
        )
    )
