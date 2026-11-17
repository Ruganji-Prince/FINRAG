"""Transactional, checksummed schema upgrades; no destructive automatic downgrades."""

import hashlib
import json

from backend.config import ROOT


def migrate():
    from backend.database import connection, execute, is_pg, now

    dialect = "postgres" if is_pg() else "sqlite"
    with connection() as conn:
        if is_pg():
            conn.execute("SELECT pg_advisory_xact_lock(72819341)")
        else:
            conn.execute("BEGIN IMMEDIATE")
        execute(
            conn,
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY,sha256 TEXT NOT NULL,applied_at TEXT NOT NULL)",
        )
        for path in sorted((ROOT / "backend/migrations").glob("*_" + dialect + ".sql")):
            version = path.name.split("_")[0]
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            previous = execute(
                conn, "SELECT sha256 FROM schema_migrations WHERE version=?", (version,)
            ).fetchone()
            if previous:
                if previous["sha256"] != checksum:
                    raise ValueError("Applied migration checksum changed: " + version)
                continue
            for statement in path.read_text().split(";"):
                if statement.strip():
                    execute(conn, statement)
            execute(
                conn,
                "INSERT INTO schema_migrations(version,sha256,applied_at) VALUES(?,?,?)",
                (version, checksum, now()),
            )
        registry = ROOT / "docs/governance.json"
        if registry.exists():
            payload = json.dumps(
                json.loads(registry.read_text(encoding="utf-8")), sort_keys=True
            )
            execute(
                conn,
                "INSERT INTO governance_records(registry_key,payload_json,payload_sha256,recorded_at,owner) VALUES(?,?,?,?,?) ON CONFLICT(registry_key) DO NOTHING",
                (
                    "project_registry",
                    payload,
                    hashlib.sha256(payload.encode()).hexdigest(),
                    now(),
                    "Repository maintainer",
                ),
            )


if __name__ == "__main__":
    migrate()
