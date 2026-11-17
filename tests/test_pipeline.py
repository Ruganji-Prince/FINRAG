import pytest
from pydantic import ValidationError

from backend.database import connection, documents, rows, stats
from backend.schemas import DocumentMetadata, safe_url
from pipelines.ingest import chunk_pages, extract, ingest


@pytest.mark.parametrize(
    "url",
    [
        "http://www.bnr.rw/a",
        "https://evil.com/a",
        "https://statistics.gov.rw.evil.com/a",
        "https://localhost/a",
        "https://bnr.rw:8080/a",
        "https://user@bnr.rw/a",
        "file:///tmp/a",
        "https://127.0.0.1/a",
    ],
)
def test_reject_unsafe_url(url):
    with pytest.raises(ValueError):
        safe_url(url)


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("publication_date", "2999-01-01"),
        ("organization", "UNKNOWN"),
        ("source_url", "https://evil.com"),
        ("usage_notes", ""),
    ],
)
def test_invalid_metadata(metadata, field, value):
    metadata[field] = value
    with pytest.raises(ValidationError):
        DocumentMetadata(**metadata)


def test_pdf_pages_and_numbers(raw_pdf):
    pages, q = extract(raw_pdf)
    assert len(pages) == 2 and "5.2" in pages[0] and q["empty_pages"] == 0


@pytest.mark.parametrize("raw", [b"<html>error</html>", b"", b"not a pdf"])
def test_reject_bad_format(raw):
    with pytest.raises(ValueError):
        extract(raw)


def test_scanned_flag():
    import io

    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(100, 100)
    out = io.BytesIO()
    w.write(out)
    with pytest.raises(ValueError, match="OCR"):
        extract(out.getvalue())


def test_chunk_pages():
    chunks = chunk_pages(
        ["alpha inflation 5.2 percent " * 60, "beta agriculture output " * 60]
    )
    assert {c["page"] for c in chunks} == {1, 2}
    assert len({c["content_hash"] for c in chunks}) == len(chunks)
    assert all(len(c["text"].split()) <= 160 for c in chunks)


def test_chunk_dedup():
    text = "same repeated report content " * 30
    assert len(chunk_pages([text, text])) == 1


def test_chunk_settings():
    with pytest.raises(ValueError):
        chunk_pages(["a"], size=10, overlap=10)


def test_ingestion_dedup(indexed, metadata, raw_pdf):
    assert ingest(metadata, raw_pdf)["status"] == "duplicate"
    assert len(documents()) == 1 and stats()["duplicate_runs"] == 1
    assert rows("SELECT count(*) AS n FROM chunks")[0]["n"] > 0


def test_error_audit(isolated, metadata):
    with pytest.raises(ValueError):
        ingest(metadata, b"wrong")
    assert stats()["failed_runs"] == 1 and stats()["documents"] == 0


def test_readonly(indexed):
    with pytest.raises(Exception):
        with connection(True) as c:
            c.execute("DELETE FROM documents")
    assert len(documents()) == 1


def test_prebuilt_index_refresh_hydrates_pdf_cache(
    indexed, metadata, raw_pdf, isolated
):
    from pathlib import Path

    from backend.database import connection, documents, execute, rows

    doc = documents()[0]
    cached = isolated / Path(doc["path"])
    cached.unlink()
    with connection() as c:
        execute(c, "UPDATE documents SET path='' WHERE id=?", (doc["id"],))
    original_ids = [r["id"] for r in rows("SELECT id FROM chunks ORDER BY id")]
    result = ingest(metadata, raw_pdf)
    assert result["status"] == "duplicate" and result["cache_restored"]
    assert (
        len(documents()) == 1
        and [r["id"] for r in rows("SELECT id FROM chunks ORDER BY id")] == original_ids
    )
    assert (isolated / documents()[0]["path"]).read_bytes() == raw_pdf
