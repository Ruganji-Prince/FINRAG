"""Build an allowlisted, secret-scanned release without changing repository history."""

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = [
    "web",
    "deploy",
    "backend",
    "app",
    "pipelines",
    "evaluation",
    "tests",
    "scripts",
    "docs",
    ".github",
    ".streamlit",
]
DATA = {
    "manifest.json",
    "README.md",
    "prebuilt-index.json",
    "prebuilt-index-v2.json",
    "prebuilt-semantic-index.json",
    "prebuilt-semantic-index-v3.json",
    "corpus-review.json",
    "corpus-expansion-review.json",
}
EXTENSIONS = {
    ".ts",
    ".tsx",
    ".css",
    ".mjs",
    ".py",
    ".sql",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".sh",
    ".ps1",
    ".png",
    ".xml",
    ".csv",
}


def candidates():
    paths = []
    for name in DIRECTORIES:
        for parent, directories, files in os.walk(ROOT / name):
            directories[:] = [
                d
                for d in directories
                if d
                not in {
                    "node_modules",
                    ".next",
                    ".vercel",
                    "__pycache__",
                    ".git",
                    ".venv",
                    "models",
                }
            ]
            for filename in files:
                p = Path(parent) / filename
                if filename.startswith(".env") and filename != ".env.example":
                    continue
                if p.suffix in EXTENSIONS or filename in {
                    ".env.example",
                    ".vercelignore",
                }:
                    paths.append(p)
    paths += [
        p
        for p in ROOT.iterdir()
        if p.is_file()
        and (
            p.suffix in {".md", ".toml"}
            or p.name.startswith("requirements")
            or p.name
            in {
                "Dockerfile",
                "docker-compose.yml",
                ".env.example",
                ".gitignore",
                ".dockerignore",
                ".gitattributes",
                "LICENSE",
            }
        )
    ]
    paths += [ROOT / "data" / name for name in DATA if (ROOT / "data" / name).exists()]
    return sorted(set(paths))


def build():
    secrets = set()
    for name in [".env", ".env.native-postgres"]:
        for key, value in dotenv_values(ROOT / name).items():
            if not value:
                continue
            if (
                any(x in key for x in ["PASSWORD", "TOKEN", "API_KEY"])
                and len(value) >= 12
            ):
                secrets.add(value)
            if key.endswith("DATABASE_URL"):
                password = urlsplit(value).password
                if password and len(password) >= 12:
                    secrets.add(password)
    secret_path = ROOT / ".runtime/local-secrets.json"
    if secret_path.exists():
        secrets.update(
            v
            for v in json.loads(secret_path.read_text()).values()
            if isinstance(v, str) and len(v) >= 12
        )
    private = ROOT / ".runtime/web-demo-private.json"
    if private.exists():
        secrets.update(
            v
            for k, v in json.loads(private.read_text()).items()
            if k in {"backend_token", "session_secret", "invitation"}
            and isinstance(v, str)
            and len(v) >= 12
        )
    findings = []
    manifest = []
    paths = candidates()
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace") if path.suffix != ".png" else ""
        if any(secret in text for secret in secrets):
            findings.append({"file": relative, "rule": "configured-secret"})
        if re.search(
            r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}",
            text,
        ):
            findings.append({"file": relative, "rule": "credential-pattern"})
        manifest.append(
            {
                "path": relative,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    folder = ROOT / "release"
    folder.mkdir(exist_ok=True)
    report = {
        "status": "passed" if not findings else "failed",
        "files": len(paths),
        "findings": findings,
        "scope": "Allowlisted publication files only; exact configured secrets and credential patterns. Not a guarantee against all sensitive content. Raw PDFs, database files, caches, logs, secrets, runtime and backups excluded.",
    }
    (folder / "secret-scan.json").write_text(json.dumps(report, indent=2))
    if findings:
        raise SystemExit(
            "Publication blocked: review release/secret-scan.json; secret values are never printed."
        )
    with zipfile.ZipFile(
        folder / "FinRAG-Rwanda-Financial-Intelligence.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    build()
