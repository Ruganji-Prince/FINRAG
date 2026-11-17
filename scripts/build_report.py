# Build project documentation from measured artifacts, without fabricating missing results.
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / name
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def fmt(value, digits=4):
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "Not measured"


def main():
    if (ROOT / "docs/FINAL_PROJECT_COMPLETION_REPORT.md").exists():
        raise SystemExit(
            "This legacy development-report builder is preserved for history. Current results are documented in docs/FINAL_PROJECT_COMPLETION_REPORT.md; it will not overwrite them."
        )
    database = load("evaluation/results/database-verification.json")
    retrieval = load("evaluation/results/retrieval-comparison.json")
    rag = load("evaluation/results/rag-latest.json")
    calibration = load("evaluation/results/local-rag-calibration.json")
    api = load("evaluation/results/api-verification.json")
    browser = load("docs/screenshots/verification.json")
    refresh = load("evaluation/results/incremental-ingestion.json")
    tests = {key: 0 for key in ["tests", "failures", "errors", "skipped"]}
    path = ROOT / "evaluation/results/final-tests.xml"
    if path.exists():
        for suite in ET.parse(path).getroot().iter("testsuite"):
            for key in tests:
                tests[key] += int(suite.attrib.get(key, 0))
    metrics = rag.get("metrics", {})
    state = f"{rag.get('status', 'not_run')} ({rag.get('n', 0)}/{rag.get('planned', 0)} cases)"
    if rag.get("status") != "completed":
        state += " - incomplete; not a completed evaluation"
    retrieval_rows = []
    for mode in ["keyword", "vector", "hybrid"]:
        row = retrieval.get("metrics", {}).get(mode, {})
        retrieval_rows.append(
            "| "
            + mode
            + " | "
            + fmt(row.get("page_recall_at_5"))
            + " | "
            + fmt(row.get("mrr_at_5"))
            + " |"
        )
    failures = [
        outcome
        for outcome in rag.get("outcomes", [])
        if (
            outcome.get("category") != "unsupported"
            and (
                outcome.get("abstained")
                or (outcome.get("expected_anchor_coverage") or 0) < 1
            )
        )
        or (outcome.get("category") == "unsupported" and not outcome.get("abstained"))
    ]
    (ROOT / "evaluation/results/failure-cases.json").write_text(
        json.dumps(
            {
                "evaluation_status": rag.get("status", "not_run"),
                "method": "Anchor/abstention diagnostics, not independently human-adjudicated errors. All observed failures retained.",
                "cases": failures,
            },
            indent=2,
        )
    )
    report = {
        "implemented": [
            "Versioned transactional PostgreSQL/SQLite schema migrations and indexes",
            "Source-preserving verified SQLite-to-PostgreSQL transfer",
            "Pinned real semantic embeddings and keyword/vector/RRF-hybrid retrieval",
            "Scope/frequency-aware context, actual local LLM, exact-source validation and abstention",
            "Configurable Gemini/OpenAI adapters",
            "15-report NISR corpus, incremental ingestion and preserved lightweight snapshots",
            "Existing six Streamlit pages, APIs and version-preserving governance records",
        ],
        "tested": {
            "documents": database.get("documents"),
            "passages": database.get("passages"),
            "tests": tests,
            "actual_local_factual_calibration": calibration.get("passed"),
            "http_rag": api.get("status"),
            "browser": browser.get("status"),
            "browser_provider": browser.get("provider"),
            "incremental_unchanged": refresh.get("all_sources_unchanged"),
            "retrieval_comparison": retrieval.get("metrics"),
            "generated_evaluation_status": rag.get("status", "not_run"),
            "generated_evaluation_cases": rag.get("n", 0),
            "generated_metrics": metrics,
        },
        "incomplete": [
            "Docker runtime execution: Docker/WSL absent; native PostgreSQL tested instead",
            "Live cloud provider and billing verification: no credentials supplied; mocked adapter tests only",
            "BNR corpus inclusion: reviewed candidates remain pending rights clarification",
            "Independent human answer adjudication and semantic-entailment assessment",
            "Public production deployment, authentication/TLS, isolated PDF workers and load testing",
        ],
        "scope": "Production-oriented research demonstration, not a production-ready bank decision system. Actual extractive RAG publishes validated source quotations rather than unsupported free-form synthesis.",
    }
    (ROOT / "docs/final-report.json").write_text(json.dumps(report, indent=2))
    substitutions = {
        "@DOCS@": str(database.get("documents", "unverified")),
        "@PASSAGES@": str(database.get("passages", "unverified")),
        "@TESTS@": str(tests["tests"]),
        "@FAILURES@": str(tests["failures"]),
        "@SKIPPED@": str(tests["skipped"]),
        "@RAG_STATE@": state,
        "@RETRIEVAL@": "\n".join(retrieval_rows),
        "@INTEGRITY@": fmt(metrics.get("citation_quote_integrity")),
        "@SUPPORT@": fmt(metrics.get("extractive_claim_support")),
        "@ABSTENTION@": fmt(metrics.get("unsupported_abstention_rate")),
        "@POS_ABSTENTION@": fmt(metrics.get("positive_question_abstention_rate")),
        "@ANCHORS@": fmt(metrics.get("mean_expected_anchor_coverage")),
        "@LATENCY@": fmt(metrics.get("mean_latency_ms"), 2),
        "@COST@": fmt(metrics.get("estimated_api_cost_usd")),
    }
    for template, target in [
        ("docs/README.template.md", "README.md"),
        ("docs/report.template.md", "docs/final-report.md"),
    ]:
        content = (ROOT / template).read_text(encoding="utf-8-sig")
        for key, value in substitutions.items():
            content = content.replace(key, value)
        (ROOT / target).write_text(content, encoding="utf-8")
    (ROOT / "docs/acceptance.md").write_text(
        "# Acceptance status\n\nSee [the current final report](final-report.md) for implemented, tested and incomplete functionality. The original MVP README and source backup are preserved. Full production acceptance is not claimed; runtime and evaluation statements follow saved evidence.\n"
    )
    print("Documentation generated from saved evidence. RAG evaluation:", state)


if __name__ == "__main__":
    main()
