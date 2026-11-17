"""Build a minimal Vercel API staging directory from the existing backend.
Private environment files, databases, raw PDFs and local LLM weights never enter it.
"""

import hashlib
import json
import shutil
from pathlib import Path

from backend.config import ROOT
from scripts.prepare_onnx import prepare


def build(destination=None):
    destination = Path(destination) if destination else ROOT / "release/vercel-api"
    if not destination.resolve().is_relative_to((ROOT / "release").resolve()):
        raise ValueError("Staging must remain under the ignored release directory")
    assets = ROOT / ".models/minilm-onnx"
    prepare(assets)
    destination.mkdir(parents=True, exist_ok=True)
    sources = [
        p
        for p in (ROOT / "backend").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".sql"}
    ]
    for path in sources:
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for name in ["cloud_entry.py", "vercel.json"]:
        shutil.copy2(ROOT / "deploy/vercel-api" / name, destination / name)
    pins = [
        line
        for line in (ROOT / "requirements-serverless.txt").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    config = (
        (ROOT / "deploy/vercel-api/pyproject.toml")
        .read_text()
        .replace(
            "[tool.vercel]",
            "dependencies = " + json.dumps(pins, indent=2) + "\n\n[tool.vercel]",
        )
    )
    (destination / "pyproject.toml").write_text(config)
    (destination / "requirements.txt").write_text("\n".join(pins) + "\n")
    (destination / ".python-version").write_text("3.14\n")
    (destination / ".vercelignore").write_text(
        ".env*\n.git\n.venv\n__pycache__\n*.pyc\n"
    )
    for name in ["governance.json", "query-policy.json"]:
        target = destination / "docs" / name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(ROOT / "docs" / name, target)
    for name in ["rag-latest.json", "retrieval-comparison.json", "holdout-rag.json"]:
        target = destination / "evaluation/results" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "evaluation/results" / name, target)
    target = destination / "models/minilm"
    target.mkdir(parents=True, exist_ok=True)
    for name in ["model.onnx", "tokenizer.json", "manifest.json"]:
        shutil.copy2(assets / name, target / name)
    manifest = []
    for p in destination.rglob("*"):
        if not p.is_file():
            continue
        relative = p.relative_to(destination)
        if ".vercel" in relative.parts:
            continue
        if (
            p.suffix in {".db", ".pdf", ".safetensors"}
            or p.name.startswith(".env")
            or "__pycache__" in relative.parts
        ):
            raise ValueError("Private or unexpected asset in staging")
        if p.name == "build-manifest.json":
            continue
        manifest.append(
            {
                "path": relative.as_posix(),
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
        )
    report = {
        "profile": "Vercel Python API + unquantized pinned MiniLM ONNX; hosted LLM required",
        "files": manifest,
        "source_and_assets_bytes": sum(p["bytes"] for p in manifest),
        "runtime_dependencies_size": "Measure installed Linux dependency size in CI; deployment build not yet verified.",
    }
    (destination / "build-manifest.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "destination": str(destination),
                "source_files": len(manifest),
                "source_and_assets_bytes": report["source_and_assets_bytes"],
            }
        )
    )
    return report


if __name__ == "__main__":
    build()
