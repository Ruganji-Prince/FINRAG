"""Export/restore a curated CC BY corpus index for offline demonstrations.
Usage: python -m pipelines.snapshot export|restore [path]
"""

import argparse
import hashlib
import json
import math

from backend.config import ROOT
from backend.database import connection, execute, initialize, now, rows
from backend.embeddings import DIM, identity
from backend.schemas import DocumentMetadata


def export(path):
    docs = rows("SELECT * FROM documents")
    if any("CC BY 4.0" not in d["usage_notes"] for d in docs):
        raise ValueError("Only explicitly licensed reports may be exported")
    chunks = rows("SELECT * FROM chunks")
    for c in chunks:
        if isinstance(c["embedding"], str):
            c["embedding"] = json.loads(c["embedding"])
    for d in docs:
        d["path"] = ""
    payload = {
        "format": "finrag-index-v1",
        "embedding_model": identity(),
        "attribution": "National Institute of Statistics of Rwanda (NISR), publications listed in documents. CC BY 4.0 for data and analysis. Extracted passages and vectors are derived from original publications; see each title, source URL and usage_notes. Images and third-party logos are not included.",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "documents": docs,
        "chunks": chunks,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Exported {len(docs)} documents and {len(chunks)} passages to {path}")


def restore(path):
    if path.stat().st_size > 25000000:
        raise ValueError("Snapshot too large")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload["format"] != "finrag-index-v1"
        or payload["embedding_model"] != identity()
    ):
        raise ValueError("Snapshot model/format mismatch; reingest for this model")
    initialize()
    mapping = {}
    with connection() as c:
        for d in payload["documents"]:
            DocumentMetadata.model_validate(d)
            if "CC BY 4.0" not in d["usage_notes"]:
                raise ValueError("Missing redistribution license")
            existing = execute(
                c, "SELECT id FROM documents WHERE content_hash=?", (d["content_hash"],)
            ).fetchone()
            if existing:
                mapping[d["id"]] = (existing["id"], False)
                continue
            original = d["id"]
            allowed = [
                "title",
                "organization",
                "publication_date",
                "source_url",
                "document_type",
                "landing_url",
                "usage_notes",
                "content_hash",
                "retrieved_at",
                "status",
                "embedding_model",
                "quality_json",
                "path",
            ]
            values = {k: d[k] for k in allowed}
            if values["embedding_model"] != identity():
                raise ValueError("Document model mismatch")
            keys = list(values)
            new_id = execute(
                c,
                "INSERT INTO documents ("
                + ",".join(keys)
                + ") VALUES ("
                + ",".join("?" for _ in keys)
                + ") RETURNING id",
                tuple(values.values()),
            ).fetchone()["id"]
            mapping[original] = (new_id, True)
        for chunk in payload["chunks"]:
            doc_id, is_new = mapping[chunk["document_id"]]
            if not is_new:
                continue
            vector = chunk["embedding"]
            if len(vector) != DIM or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in vector
            ):
                raise ValueError("Invalid embedding")
            if (
                hashlib.sha256(chunk["text"].encode()).hexdigest()
                != chunk["content_hash"]
                or chunk["page"] < 1
            ):
                raise ValueError("Corrupt chunk")
            execute(
                c,
                "INSERT INTO chunks(document_id,page,section,text,content_hash,embedding) VALUES(?,?,?,?,?,?)",
                (
                    doc_id,
                    chunk["page"],
                    chunk["section"],
                    chunk["text"],
                    chunk["content_hash"],
                    json.dumps(vector),
                ),
            )
        execute(
            c,
            "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
            (
                now(),
                "offline:curated-index",
                "restored",
                "Restored licensed derived index; original retrieval timestamps preserved.",
            ),
        )
    print("Restored snapshot without duplicating existing document hashes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export", "restore"])
    parser.add_argument(
        "path", nargs="?", default=str(ROOT / "data/prebuilt-index.json")
    )
    args = parser.parse_args()
    path = __import__("pathlib").Path(args.path)
    (export if args.action == "export" else restore)(path)


if __name__ == "__main__":
    main()
