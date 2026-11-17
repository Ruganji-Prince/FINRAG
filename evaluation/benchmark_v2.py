"""Build versioned labels and verify every positive anchor against original PDF pages."""

import hashlib
import json

from pypdf import PdfReader

from backend.config import ROOT
from backend.database import documents, now


def build():
    docs = documents()
    by_title = {d["title"]: d for d in docs}
    cases = json.loads((ROOT / "evaluation/datasets/benchmark.json").read_text())
    # Preserve the original benchmark and label provenance; add financial/inflation coverage.
    for c in cases:
        if c.get("source_url"):
            c["gold_sources"] = [
                {
                    "source_url": c["source_url"],
                    "pages": c["pages"],
                    "anchors": c.get("expected_substrings", []),
                }
            ]
    extras = [
        (
            "October 2026",
            "What was the urban CPI annual increase in October 2026?",
            4,
            "19.5 percent",
        ),
        (
            "October 2026",
            "What was the rural CPI annual increase in October 2026?",
            4,
            "31.3 percent",
        ),
        (
            "October 2026",
            "What was the overall Rwanda CPI annual increase in October 2026?",
            4,
            "26.5 percent",
        ),
        (
            "October 2026",
            "What was the monthly urban CPI change in October 2026?",
            4,
            "3.3 percent",
        ),
        (
            "September 2026",
            "What was the urban CPI annual increase in September 2026?",
            4,
            "17.2 percent",
        ),
        (
            "September 2026",
            "What was the rural CPI annual increase in September 2026?",
            4,
            "22 percent",
        ),
        (
            "August 2026",
            "What was the urban CPI annual increase in August 2026?",
            4,
            "15.7 percent",
        ),
        (
            "August 2026",
            "What was the monthly urban CPI change in August 2026?",
            4,
            "1.8 percent",
        ),
    ]
    for month, question, page, anchor in extras:
        doc = next(
            d for d in docs if d["title"] == "Consumer Price Index (CPI) - " + month
        )
        cases.append(
            {
                "id": "cpi-" + str(len(cases) + 1),
                "category": "financial_factual",
                "question": question,
                "title": doc["title"],
                "gold_sources": [
                    {
                        "source_url": doc["source_url"],
                        "pages": [page],
                        "anchors": [anchor],
                    }
                ],
            }
        )
    for measure, anchors in [
        ("urban CPI annual increase", ["17.2 percent", "19.5 percent"]),
        ("rural CPI annual increase", ["22 percent", "31.3 percent"]),
        ("overall Rwanda CPI annual increase", ["20 percent", "26.5 percent"]),
    ]:
        selected = [
            by_title["Consumer Price Index (CPI) - " + month]
            for month in ["September 2026", "October 2026"]
        ]
        cases.append(
            {
                "id": "cross-" + str(len(cases) + 1),
                "category": "cross_report_comparison",
                "question": "Compare "
                + measure
                + " in September 2026 and October 2026.",
                "document_titles": [d["title"] for d in selected],
                "gold_sources": [
                    {"source_url": d["source_url"], "pages": [4], "anchors": [anchor]}
                    for d, anchor in zip(selected, anchors, strict=True)
                ],
            }
        )
    # Revision/contradiction-sensitive comparison: original reports disagree on 2024 nominal GDP.
    selected = [
        by_title["GDP National Accounts, 2024"],
        by_title["GDP National Accounts 2025"],
    ]
    cases.append(
        {
            "id": "revision-cross",
            "category": "revision_conflict",
            "question": "Compare the reported 2024 GDP estimates in the 2024 and 2025 GDP reports. Do they report the same value?",
            "document_titles": [d["title"] for d in selected],
            "gold_sources": [
                {
                    "source_url": selected[0]["source_url"],
                    "pages": [1],
                    "anchors": ["18,785"],
                },
                {
                    "source_url": selected[1]["source_url"],
                    "pages": [3],
                    "anchors": ["19,918"],
                },
            ],
            "review_note": "Different publication vintages/base years; do not silently reconcile or assert a cause beyond the source.",
        }
    )
    checks = []
    for case in cases:
        for gold in case.get("gold_sources", []):
            doc = next(d for d in docs if d["source_url"] == gold["source_url"])
            raw = ROOT / doc["path"]
            if hashlib.sha256(raw.read_bytes()).hexdigest() != doc["content_hash"]:
                raise ValueError("Original PDF hash mismatch")
            reader = PdfReader(raw)
            texts = [
                " ".join((reader.pages[p - 1].extract_text() or "").split())
                for p in gold["pages"]
            ]
            joined = __import__("re").sub(r"\s+(?=%)", "", " ".join(texts).lower())
            for anchor in gold["anchors"]:
                if __import__("re").sub(r"\s+(?=%)", "", anchor.lower()) not in joined:
                    raise ValueError(
                        f"Unverified benchmark anchor: {case['id']}: {anchor}"
                    )
            checks.append(
                {
                    "case_id": case["id"],
                    "source_url": gold["source_url"],
                    "pages": gold["pages"],
                    "pdf_sha256": doc["content_hash"],
                    "anchors": gold["anchors"],
                    "status": "matched_original_pdf",
                }
            )
    output = ROOT / "evaluation/datasets/financial-v2.json"
    output.write_text(json.dumps(cases, indent=2))
    (ROOT / "evaluation/results/benchmark-verification.json").write_text(
        json.dumps(
            {
                "checked_at": now(),
                "n_questions": len(cases),
                "verification": "Automated original-PDF hash/page/anchor verification; independent human relevance adjudication not performed.",
                "checks": checks,
            },
            indent=2,
        )
    )
    print(f"Verified {len(checks)} gold-source page labels for {len(cases)} questions")


if __name__ == "__main__":
    build()
