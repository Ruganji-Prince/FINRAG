"""Run reproducible baseline or improved evaluation without overwriting old evidence."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from backend.config import ROOT
from evaluation import evaluate_rag


def baseline():
    path = ROOT / "evaluation/baselines/rag_v1.py"
    spec = importlib.util.spec_from_file_location("backend.reliability_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SELECT = module.SELECT.replace(
        "FROM chunks c",
        "FROM (SELECT * FROM chunks WHERE section NOT IN ('sentence-window-v2','table-layout-v2')) c",
    )
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output")
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    if (ROOT / "evaluation/results" / f"{args.output}.json").exists():
        raise SystemExit(
            "Output exists; preserve completed evidence and choose a new run name"
        )
    if args.baseline:
        module = baseline()
        evaluate_rag.answer = module.answer
    result = evaluate_rag.run(dataset_path=args.dataset, output_name=args.output)
    result["implementation"] = (
        "original 839-chunk-era ranking/context, original chunks only"
        if args.baseline
        else "reliability-v2"
    )
    result["baseline_source_sha256"] = hashlib.sha256(
        (ROOT / "evaluation/baselines/rag_v1.py").read_bytes()
    ).hexdigest()
    (ROOT / "evaluation/results" / f"{args.output}.json").write_text(
        json.dumps(result, indent=2)
    )
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
