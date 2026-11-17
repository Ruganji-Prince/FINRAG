import json
import sqlite3

import pytest

from backend.config import ROOT, settings
from backend.database import connection, execute, initialize, rows
from backend.rag import search
from backend.schemas import Filters, Query
from pipelines.migrate_sqlite import migrate_source


def test_real_migration_preserves_evidence_and_governance(pg_isolated, tmp_path):
    source = ROOT / "data/backups/finrag-before-rag-upgrade.db"
    # CI uses the bundled legally redistributable index to create a separate source.
    from pipelines.snapshot import restore

    pg_url = settings.database_url
    settings.database_url = "sqlite:///" + str(tmp_path / "source.db")
    try:
        restore(ROOT / "data/prebuilt-index.json")
        initialize()
        import hashlib

        payload = json.dumps({"fixture_registry": True, "steward": "test fixture"})
        with connection() as c:
            execute(
                c,
                "INSERT INTO governance_records(registry_key,payload_json,payload_sha256,recorded_at,owner) VALUES(?,?,?,?,?)",
                (
                    "source_specific",
                    payload,
                    hashlib.sha256(payload.encode()).hexdigest(),
                    "2026-01-01T00:00:00+00:00",
                    "test fixture",
                ),
            )
        source = tmp_path / "source.db"
    finally:
        settings.database_url = pg_url
    before = source.read_bytes()
    first = migrate_source(source)
    second = migrate_source(source)
    assert first["status"] == "migrated" and second["status"] == "unchanged"
    assert source.read_bytes() == before
    with sqlite3.connect(source) as c:
        expected = c.execute("SELECT count(*) FROM chunks").fetchone()[0]
    assert rows("SELECT count(*) AS n FROM chunks")[0]["n"] == expected
    assert rows("SELECT count(*) AS n FROM governance_records")[0]["n"] >= 1
    copied = rows(
        "SELECT payload_json FROM governance_records WHERE registry_key=?",
        ("source_specific",),
    )
    assert copied and copied[0]["payload_json"] == payload
    assert first["copied"]["governance"] == 1
    assert len(rows("SELECT * FROM schema_migrations")) == 2
    assert (
        rows(
            "SELECT count(*) AS n FROM pg_indexes WHERE schemaname=current_schema() AND indexname IN ('chunks_vector','chunks_search')"
        )[0]["n"]
        == 2
    )
    assert search(Query(question="GDP agriculture", retrieval_mode="keyword"))


def test_postgres_persistence_and_readonly(
    pg_isolated, raw_pdf, metadata, monkeypatch, tmp_path
):
    import pipelines.ingest as pipe
    from pipelines.ingest import ingest

    monkeypatch.setattr(settings, "embedding_backend", "hash")
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    result = ingest(metadata, raw_pdf)
    initialize()  # New connection/startup sees committed data.
    assert rows("SELECT id FROM documents WHERE id=?", (result["document_id"],))
    import psycopg

    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        with connection(True) as c:
            execute(c, "DELETE FROM documents")


@pytest.mark.skipif(
    __import__("os").getenv("FINRAG_RUN_MODELS") != "1",
    reason="Real model test explicitly enabled",
)
def test_real_semantic_embeddings_postgres(
    pg_isolated, raw_pdf, metadata, monkeypatch, tmp_path
):
    import pipelines.ingest as pipe
    from backend.embeddings import embed
    from pipelines.ingest import ingest

    monkeypatch.setattr(settings, "embedding_backend", "sentence-transformers")
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    result = ingest(metadata, raw_pdf)
    vector = embed(["price stability and monetary policy"])[0]
    assert len(vector) == 384
    for mode in ["keyword", "vector", "hybrid"]:
        hits = search(
            Query(
                question="inflation monetary policy",
                retrieval_mode=mode,
                filters=Filters(document_id=result["document_id"]),
            ),
            gate=False,
        )
        assert hits and hits[0]["document_id"] == result["document_id"]
    assert rows("SELECT vector_dims(embedding) AS n FROM chunks LIMIT 1")[0]["n"] == 384
