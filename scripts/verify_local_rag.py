"""Verify real model answers against obvious reference facts before promoting the profile."""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    load_dotenv(ROOT / ".env.native-postgres", override=True)
    from backend.config import settings

    settings.llm_provider = "local"
    from backend.database import documents
    from backend.rag import answer
    from backend.schemas import Filters, Query

    by_title = {d["title"]: d["id"] for d in documents()}
    cases = [
        (
            "What was GDP growth in 2025?",
            by_title["GDP National Accounts 2025"],
            "9.4%",
        ),
        (
            "What was urban CPI annual increase in October 2026?",
            by_title["Consumer Price Index (CPI) - October 2026"],
            "19.5 percent",
        ),
    ]
    results = []
    for question, doc_id, anchor in cases:
        result = answer(
            Query(question=question, k=2, filters=Filters(document_id=doc_id))
        )
        results.append(
            {
                "question": question,
                "expected_anchor": anchor,
                "anchor_found": anchor in result["answer"],
                "result": result,
            }
        )
        print(
            json.dumps({k: v for k, v in result.items() if k != "evidence"}), flush=True
        )
    report = {
        "provider": settings.llm_provider,
        "model": settings.local_llm_model,
        "revision": settings.local_llm_revision,
        "quantization": "dynamic_int8" if settings.local_llm_quantize else "float32",
        "cases": results,
        "passed": all(
            x["result"]["mode"] == "llm"
            and not x["result"]["abstained"]
            and x["anchor_found"]
            for x in results
        ),
    }
    (ROOT / "evaluation/results/local-rag-calibration.json").write_text(
        json.dumps(report, indent=2)
    )
    if not report["passed"]:
        raise SystemExit(
            "Model did not pass factual calibration; do not claim reliable generated answers."
        )
    print(
        "Actual PostgreSQL semantic retrieval -> LLM -> source-validated factual answers passed."
    )


if __name__ == "__main__":
    main()
