"""Download pinned, publisher-checksummed embedding assets for offline cloud packaging."""

import argparse
import hashlib
import json
from pathlib import Path

import httpx

from backend.config import ROOT, settings


def prepare(folder):
    repository = settings.embedding_model
    revision = settings.embedding_revision
    response = httpx.get(
        f"https://huggingface.co/api/models/{repository}/tree/{revision}?recursive=true",
        timeout=30,
    )
    response.raise_for_status()
    metadata = {item["path"]: item for item in response.json()}
    folder.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for source, target in [
        ("onnx/model.onnx", "model.onnx"),
        ("tokenizer.json", "tokenizer.json"),
    ]:
        item = metadata[source]
        path = folder / target

        def valid(raw):
            if item.get("lfs"):
                return hashlib.sha256(raw).hexdigest() == item["lfs"]["oid"]
            return (
                hashlib.sha1(
                    b"blob " + str(len(raw)).encode() + b"\0" + raw
                ).hexdigest()
                == item["oid"]
            )

        if not path.exists() or not valid(path.read_bytes()):
            raw = bytearray()
            with httpx.stream(
                "GET",
                f"https://huggingface.co/{repository}/resolve/{revision}/{source}",
                follow_redirects=True,
                timeout=60,
            ) as r:
                r.raise_for_status()
                for part in r.iter_bytes():
                    raw.extend(part)
                    if len(raw) > 150_000_000:
                        raise ValueError("Model asset exceeds limit")
            if not valid(raw):
                raise ValueError("Publisher model asset checksum mismatch")
            path.write_bytes(raw)
        hashes[target] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(
            json.dumps(
                {
                    "asset": target,
                    "bytes": path.stat().st_size,
                    "publisher_digest_verified": True,
                }
            ),
            flush=True,
        )
    manifest = {
        "repository": repository,
        "revision": revision,
        "license": "Apache-2.0, publisher model card",
        "dimensions": 384,
        "max_tokens": 256,
        "pooling": "attention-mask mean pooling, L2 normalized",
        "sha256": hashes,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--directory", type=Path, default=ROOT / ".models/minilm-onnx")
    args = p.parse_args()
    prepare(args.directory)
