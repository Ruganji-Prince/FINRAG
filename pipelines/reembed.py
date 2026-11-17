"""Re-embed selected index transactionally, preserving IDs, text, provenance and hashes."""

import json
import uuid

from backend.database import connection, execute, initialize, now, rows
from backend.embeddings import embed, identity


def reembed():
    initialize()
    chunks = rows(
        "SELECT c.id,c.document_id,c.text,c.content_hash,d.embedding_model FROM chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.id"
    )
    selected = [c for c in chunks if c["embedding_model"] != identity()]
    if not selected:
        return {"status": "unchanged", "chunks": 0}
    started = now()
    vectors = embed([c["text"] for c in selected])
    run_id = str(uuid.uuid4())
    if len(vectors) != len(selected):
        raise ValueError("Embedding count mismatch")
    with connection() as c:
        from backend.database import is_pg

        if is_pg():
            c.execute("SELECT pg_advisory_xact_lock(72819343)")
        current = {
            row["id"]: row
            for row in execute(
                c,
                "SELECT c.id,c.content_hash,d.embedding_model FROM chunks c JOIN documents d ON d.id=c.document_id",
            ).fetchall()
        }
        if any(
            item["id"] not in current
            or current[item["id"]]["content_hash"] != item["content_hash"]
            or current[item["id"]]["embedding_model"] != item["embedding_model"]
            for item in selected
        ):
            raise ValueError(
                "Corpus/model changed while encoding; no vectors published"
            )
        for item, vector in zip(selected, vectors, strict=True):
            result = execute(
                c,
                "UPDATE chunks SET embedding=? WHERE id=? AND content_hash=?",
                (json.dumps(vector), item["id"], item["content_hash"]),
            )
            if result.rowcount != 1:
                raise ValueError("Corpus changed during embedding; retry")
        # An atomic publication switches complete documents to the new model identity.
        for doc_id in {item["document_id"] for item in selected}:
            execute(
                c,
                "UPDATE documents SET embedding_model=? WHERE id=?",
                (identity(), doc_id),
            )
        execute(
            c,
            "INSERT INTO embedding_runs(run_id,model_id,started_at,completed_at,chunk_count,status) VALUES(?,?,?,?,?,?)",
            (run_id, identity(), started, now(), len(selected), "completed"),
        )
        execute(
            c,
            "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
            (
                now(),
                "operator:reembed",
                "reembedded",
                json.dumps(
                    {"run_id": run_id, "model": identity(), "chunks": len(selected)}
                ),
            ),
        )
    return {"status": "reembedded", "chunks": len(selected), "model": identity()}


if __name__ == "__main__":
    print(json.dumps(reembed(), indent=2))
