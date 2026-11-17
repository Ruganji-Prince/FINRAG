"""Verify genuine HTTP RAG and two-source comparisons against the running services."""

import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    base = "http://127.0.0.1:8000"
    deadline = time.monotonic() + 240
    while True:
        try:
            r = httpx.get(base + "/health", timeout=5)
            r.raise_for_status()
            health = r.json()
            break
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)
    print("Backend ready:", json.dumps(health), flush=True)
    with httpx.Client(timeout=180) as client:
        docs = client.get(base + "/documents")
        docs.raise_for_status()
        docs = docs.json()
        quality = client.get(base + "/quality")
        quality.raise_for_status()
        quality = quality.json()
        manifest = json.loads((ROOT / "data/manifest.json").read_text())
        assert len(docs) == len(manifest) == 30
        assert quality["chunks"] == 839
        by_title = {d["title"]: d["id"] for d in docs}
        gdp_id = by_title["GDP National Accounts 2025"]
        october_id = by_title["Consumer Price Index (CPI) - October 2026"]
        september_id = by_title["Consumer Price Index (CPI) - September 2026"]
        question = {
            "question": "What was GDP growth in 2025?",
            "k": 2,
            "filters": {"document_id": gdp_id},
        }
        r = client.post(base + "/ask", json=question)
        r.raise_for_status()
        answer = r.json()
        assert (
            answer["mode"] == "llm"
            and not answer["abstained"]
            and "9.4%" in answer["answer"]
        )
        assert answer["claims"] and all(
            e["citation_url"].endswith("#page=" + str(e["page"]))
            for e in answer["evidence"]
        )
        print("Live cited GDP answer passed", flush=True)
        r = client.post(
            base + "/ask",
            json={"question": "What is the latest central bank policy rate?"},
        )
        r.raise_for_status()
        unsupported = r.json()
        assert unsupported["abstained"] and not unsupported["claims"]
        r = client.post(
            base + "/compare",
            json={
                "left_id": october_id,
                "right_id": september_id,
                "topic": "urban CPI annual increase",
            },
        )
        r.raise_for_status()
        comparison = r.json()
        combined = comparison["comparison"]
        assert combined and combined["mode"] == "llm" and not combined["abstained"]
        assert (
            "19.5 percent" in combined["answer"]
            and "17.2 percent" in combined["answer"]
        )
        ids = {c["chunk_id"] for c in combined["claims"]}
        covered = {
            e["document_id"] for e in combined["evidence"] if e["chunk_id"] in ids
        }
        assert covered == {october_id, september_id}
        governance = client.get(base + "/governance")
        governance.raise_for_status()
    result = {
        "status": "passed",
        "health": health,
        "indexed_documents": len(docs),
        "indexed_passages": quality["chunks"],
        "answer": answer,
        "unsupported": unsupported,
        "comparison": comparison,
        "governance_record_keys": [
            x["registry_key"] for x in governance.json()["records"]
        ],
    }
    (ROOT / "evaluation/results/api-verification.json").write_text(
        json.dumps(result, indent=2)
    )
    print(
        "Genuine HTTP RAG, unsupported abstention and two-report cited comparison passed.",
        flush=True,
    )


if __name__ == "__main__":
    main()
