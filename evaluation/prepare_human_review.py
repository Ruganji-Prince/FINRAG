"""Build honest blinded review packets from the completed holdout, not fabricated ratings."""

import csv
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = json.loads((ROOT / "evaluation/results/holdout-rag.json").read_text())
    if result["status"] != "completed":
        raise SystemExit("Complete the holdout before preparing reviewer packets")
    cases = {
        c["id"]: c
        for c in json.loads((ROOT / "evaluation/datasets/holdout-v1.json").read_text())
    }
    outcomes = result["outcomes"].copy()
    random.Random(20261117).shuffle(outcomes)
    folder = ROOT / "evaluation/human-review"
    folder.mkdir(exist_ok=True)
    packets = []
    key = []
    failures = []
    for i, outcome in enumerate(outcomes, 1):
        case = cases[outcome["id"]]
        review_id = f"R{i:03}"
        packets.append(
            {
                "review_id": review_id,
                "question": case["question"],
                "answer": outcome["answer"],
                "claims": outcome["claims"],
                "reference_evidence": case["gold_sources"],
                "reference_policy": "Expected refusal: outside corpus or prohibited request"
                if case["category"] == "unsupported"
                else "Judge answer against reference period, measure, units and quoted source. Exact quotation alone does not prove relevance.",
            }
        )
        key.append({"review_id": review_id, "case_id": case["id"]})
        if (case["category"] == "unsupported" and not outcome["abstained"]) or (
            case["category"] != "unsupported"
            and (outcome["abstained"] or outcome["expected_anchor_coverage"] < 1)
        ):
            failures.append(
                {
                    "case_id": case["id"],
                    "question": case["question"],
                    "answer": outcome["answer"],
                    "abstained": outcome["abstained"],
                    "anchor_coverage": outcome["expected_anchor_coverage"],
                    "classification": "automated diagnostic; human adjudication pending",
                }
            )
    (folder / "reviewer-packets.json").write_text(json.dumps(packets, indent=2))
    (folder / "blinding-key.json").write_text(json.dumps(key, indent=2))
    with (folder / "ratings-template.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "review_id",
                "reviewer_id",
                "correctness_0_2",
                "relevance_0_2",
                "completeness_0_2",
                "citation_0_2",
                "abstention_0_2",
                "critical_error_yes_no",
                "notes",
            ]
        )
        writer.writerows([[p["review_id"]] + [""] * 8 for p in packets])
    (folder / "README.md").write_text("""# Independent review pending

No human ratings have been collected. These packets were authored and source-checked by the development agent; this is not an independently human-authored benchmark.

Give reviewer-packets.json and a copy of ratings-template.csv to two independent financial researchers. Keep blinding-key.json and provider/evaluation metadata separate until scoring is complete. Answers are shuffled and stripped of provider names, generation modes, timings and automated scores.

Open the linked official PDFs at the stated PDF page, check reference period, urban/rural or sector scope, annual/monthly frequency, units, denominator, and publication vintage. Reference page text and original PDF hashes are supplied for reproducibility. Do not treat an anchor match as full correctness. Table flattening may require visual inspection of the original PDF. Questions with no reference evidence require abstention under the stated corpus/policy scope.

Score each dimension 0 (wrong/unsupported), 1 (partly supported/incomplete), or 2 (fully correct and relevant). Citation scoring requires document, exact page, quotation and claim to agree. Score abstention 2 when correctly calibrated, 0 when an unsupported answer is given or a supported answer is unnecessarily refused; use 1 for ambiguous coverage. Mark any invented statistic/citation, wrong period or unsupported regulatory assertion as a critical error. Leave uncertain cases for adjudication and explain in notes.

Record reviewer identity and the date in a separately maintained review log. Reconcile disagreements only after independent scoring, preserve both original ratings and adjudication, and report inter-rater agreement plus denominators. Never overwrite the blank template or label automated results as human review. Current human-reviewed count: 0.
""")
    (ROOT / "evaluation/results/holdout-failure-cases.json").write_text(
        json.dumps(
            {
                "method": "No tuning after holdout; automated anchor/abstention diagnostics only",
                "cases": failures,
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "packets": len(packets),
                "human_reviewed": 0,
                "diagnostic_failures": len(failures),
                "packets_sha256": hashlib.sha256(
                    (folder / "reviewer-packets.json").read_bytes()
                ).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
