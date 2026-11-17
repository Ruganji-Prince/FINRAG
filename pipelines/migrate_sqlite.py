"""Idempotent SQLite -> PostgreSQL copy; source opened read-only and left intact."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from backend.config import ROOT
from backend.database import connection, execute, initialize, is_pg, now


def migrate_source(source):
    if not is_pg():
        raise ValueError("Destination DATABASE_URL must be PostgreSQL")
    source = Path(source).resolve()
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
        src.row_factory = sqlite3.Row
        src.execute("BEGIN")
        docs = [dict(r) for r in src.execute("SELECT * FROM documents ORDER BY id")]
        chunks = [dict(r) for r in src.execute("SELECT * FROM chunks ORDER BY id")]
        logs = [dict(r) for r in src.execute("SELECT * FROM audit ORDER BY id")]
        tables = {
            r[0]
            for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        registry = (
            [dict(r) for r in src.execute("SELECT * FROM governance_records")]
            if "governance_records" in tables
            else []
        )
    payload = {
        "documents": docs,
        "chunks": chunks,
        "audit": logs,
        "governance": registry,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    initialize()
    mapping = {}
    counts = {"documents": 0, "chunks": 0, "audit": 0, "governance": 0}
    with connection() as c:
        c.execute("SELECT pg_advisory_xact_lock(72819342)")
        if execute(
            c, "SELECT 1 FROM data_transfers WHERE source_sha256=?", (fingerprint,)
        ).fetchone():
            return {"status": "unchanged", "source_sha256": fingerprint}
        for d in docs:
            existing = execute(
                c, "SELECT id FROM documents WHERE content_hash=?", (d["content_hash"],)
            ).fetchone()
            if existing:
                mapping[d["id"]] = existing["id"]
                continue
            fields = [
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
            values = {key: d[key] for key in fields}
            keys = list(values)
            mapping[d["id"]] = execute(
                c,
                "INSERT INTO documents("
                + ",".join(keys)
                + ") VALUES("
                + ",".join("?" for _ in keys)
                + ") RETURNING id",
                tuple(values.values()),
            ).fetchone()["id"]
            counts["documents"] += 1
        for chunk in chunks:
            target = mapping[chunk["document_id"]]
            existing = execute(
                c,
                "SELECT text,page FROM chunks WHERE document_id=? AND content_hash=?",
                (target, chunk["content_hash"]),
            ).fetchone()
            if existing:
                if (
                    existing["text"] != chunk["text"]
                    or existing["page"] != chunk["page"]
                ):
                    raise ValueError("Source/destination passage conflict")
                continue
            execute(
                c,
                "INSERT INTO chunks(document_id,page,section,text,content_hash,embedding) VALUES(?,?,?,?,?,?)",
                (
                    target,
                    chunk["page"],
                    chunk["section"],
                    chunk["text"],
                    chunk["content_hash"],
                    chunk["embedding"],
                ),
            )
            counts["chunks"] += 1
        for log in logs:
            values = tuple(
                log[k] for k in ["occurred_at", "source_url", "status", "detail"]
            )
            if not execute(
                c,
                "SELECT 1 FROM audit WHERE occurred_at=? AND source_url=? AND status=? AND detail=?",
                values,
            ).fetchone():
                execute(
                    c,
                    "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
                    values,
                )
                counts["audit"] += 1
        for record in registry:
            if (
                hashlib.sha256(record["payload_json"].encode()).hexdigest()
                != record["payload_sha256"]
            ):
                raise ValueError("Corrupt source governance record")
            old = execute(
                c,
                "SELECT payload_sha256 FROM governance_records WHERE registry_key=?",
                (record["registry_key"],),
            ).fetchone()
            if old and old["payload_sha256"] != record["payload_sha256"]:
                raise ValueError(
                    "Governance conflict; reconcile manually before migration"
                )
            if not old:
                keys = [
                    "registry_key",
                    "payload_json",
                    "payload_sha256",
                    "recorded_at",
                    "owner",
                ]
                execute(
                    c,
                    "INSERT INTO governance_records("
                    + ",".join(keys)
                    + ") VALUES("
                    + ",".join("?" for _ in keys)
                    + ")",
                    tuple(record[key] for key in keys),
                )
                counts["governance"] += 1
        # Every original passage is checked in-transaction, including page and bytes.
        for chunk in chunks:
            r = execute(
                c,
                "SELECT text,page FROM chunks WHERE document_id=? AND content_hash=?",
                (mapping[chunk["document_id"]], chunk["content_hash"]),
            ).fetchone()
            if not r or r["text"] != chunk["text"] or r["page"] != chunk["page"]:
                raise ValueError("Migration verification failed")
        detail = {
            "copied": counts,
            "verified_source_documents": len(docs),
            "verified_source_chunks": len(chunks),
            "document_id_mapping": mapping,
        }
        execute(
            c,
            "INSERT INTO data_transfers(source_sha256,source_kind,completed_at,detail_json) VALUES(?,?,?,?)",
            (fingerprint, "sqlite", now(), json.dumps(detail)),
        )
    return {"status": "migrated", "source_sha256": fingerprint, **detail}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "data/finrag.db")
    args = parser.parse_args()
    print(json.dumps(migrate_source(args.source), indent=2))


if __name__ == "__main__":
    main()
