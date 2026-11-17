"""Explicit writer-only governance updates with immutable previous payload records."""

import argparse
import hashlib
import json
from pathlib import Path

from backend.database import connection, execute, initialize, now


def sync(key, path):
    initialize()
    payload = json.dumps(
        json.loads(Path(path).read_text(encoding="utf-8")), sort_keys=True
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    timestamp = now()
    with connection() as c:
        previous = execute(
            c, "SELECT * FROM governance_records WHERE registry_key=?", (key,)
        ).fetchone()
        if previous and previous["payload_sha256"] == digest:
            return {"status": "unchanged", "key": key, "sha256": digest}
        if previous:
            execute(
                c,
                "INSERT INTO governance_records(registry_key,payload_json,payload_sha256,recorded_at,owner) VALUES(?,?,?,?,?) ON CONFLICT(registry_key) DO NOTHING",
                (
                    key + "@" + previous["payload_sha256"],
                    previous["payload_json"],
                    previous["payload_sha256"],
                    previous["recorded_at"],
                    previous["owner"],
                ),
            )
        execute(
            c,
            "INSERT INTO governance_records(registry_key,payload_json,payload_sha256,recorded_at,owner) VALUES(?,?,?,?,?) ON CONFLICT(registry_key) DO UPDATE SET payload_json=excluded.payload_json,payload_sha256=excluded.payload_sha256,recorded_at=excluded.recorded_at,owner=excluded.owner",
            (key, payload, digest, timestamp, "Repository maintainer"),
        )
        execute(
            c,
            "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
            (
                timestamp,
                "operator:governance",
                "governance_updated",
                json.dumps(
                    {
                        "registry_key": key,
                        "new_sha256": digest,
                        "previous_sha256": previous["payload_sha256"]
                        if previous
                        else None,
                    }
                ),
            ),
        )
    return {"status": "updated", "key": key, "sha256": digest}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("key")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(sync(args.key, args.path)))
