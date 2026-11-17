import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import pipelines.ingest as pipeline
from backend import database
from backend.config import settings


@pytest.fixture
def raw_pdf():
    writer = PdfWriter()
    for text in [
        "TEST FIXTURE ONLY. Inflation was 5.2 percent. Monetary policy discusses price stability. "
        * 12,
        "TEST FIXTURE ONLY. Agriculture output and financial sector risks were discussed. "
        * 12,
    ]:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font)}
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 12 Tf 20 700 Td (" + text + ") Tj ET").encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def metadata():
    return {
        "title": "TEST FIXTURE - monetary report",
        "organization": "BNR",
        "publication_date": "2024-01-01",
        "source_url": "https://www.bnr.rw/test-fixture.pdf",
        "document_type": "test report",
        "landing_url": "https://www.bnr.rw/Publications",
        "usage_notes": "Synthetic test fixture; not real institutional evidence.",
    }


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "auto_migrate", True)
    monkeypatch.setattr(settings, "query_database_url", "")
    monkeypatch.setattr(
        settings, "database_url", "sqlite:///" + str(tmp_path / "test.db")
    )
    monkeypatch.setattr(settings, "embedding_backend", "hash")
    monkeypatch.setattr(settings, "llm_provider", "none")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    database.initialize()
    return tmp_path


@pytest.fixture
def indexed(isolated, metadata, raw_pdf):
    return pipeline.ingest(metadata, raw_pdf)


@pytest.fixture
def pg_isolated(monkeypatch):
    import os
    import uuid
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    url = os.getenv("FINRAG_TEST_PG_URL")
    if not url:
        pytest.skip("No PostgreSQL test database configured")
    if not urlsplit(url).path.endswith("_test"):
        raise ValueError("A dedicated _test database is required")
    import psycopg
    from psycopg import sql

    schema = "finrag_test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query))
    params["options"] = "-csearch_path=" + schema + ",public"
    monkeypatch.setattr(settings, "embedding_backend", "hash")
    monkeypatch.setattr(settings, "llm_provider", "none")
    monkeypatch.setattr(settings, "preload_models", False)
    scoped = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment)
    )
    monkeypatch.setattr(settings, "database_url", scoped)
    monkeypatch.setattr(settings, "query_database_url", "")
    try:
        database.initialize()
        yield schema
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
