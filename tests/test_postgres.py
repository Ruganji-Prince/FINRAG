"""Optional real pgvector integration check; CI supplies a disposable database."""

import os

import pytest

from backend.config import settings
from backend.database import connection, execute, initialize
from backend.rag import search
from backend.schemas import Filters, Query
from pipelines.ingest import ingest


@pytest.mark.skipif(
    not os.getenv("FINRAG_TEST_PG_URL"), reason="No PostgreSQL service configured"
)
def test_pgvector_roundtrip(monkeypatch, tmp_path, metadata, raw_pdf):
    import pipelines.ingest as pipeline

    monkeypatch.setattr(settings, "database_url", os.environ["FINRAG_TEST_PG_URL"])
    monkeypatch.setattr(settings, "query_database_url", "")
    monkeypatch.setattr(settings, "embedding_backend", "hash")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    initialize()
    doc_id = None
    try:
        result = ingest(metadata, raw_pdf)
        doc_id = result["document_id"]
        hits = search(
            Query(
                question="inflation monetary policy",
                filters=Filters(document_id=doc_id),
            )
        )
        assert hits and hits[0]["page"] == 1
        with connection(True) as c:
            row = execute(
                c,
                "SELECT vector_dims(embedding) AS dim, search IS NOT NULL AS fts FROM chunks WHERE document_id=? LIMIT 1",
                (doc_id,),
            ).fetchone()
            assert row["dim"] == 384 and row["fts"]
            with pytest.raises(Exception):
                execute(c, "UPDATE documents SET title='bad' WHERE id=?", (doc_id,))
    finally:
        if doc_id:
            with connection() as c:
                execute(c, "DELETE FROM chunks WHERE document_id=?", (doc_id,))
                execute(c, "DELETE FROM documents WHERE id=?", (doc_id,))
