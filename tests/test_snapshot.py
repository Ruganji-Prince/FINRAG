import pytest

from backend.database import documents
from pipelines.snapshot import export, restore


def test_snapshot_roundtrip(indexed, metadata, raw_pdf, isolated, monkeypatch):
    from backend.config import settings
    from backend.database import connection, execute

    with connection() as c:
        execute(
            c,
            "UPDATE documents SET usage_notes='Synthetic test fixture, CC BY 4.0; never official evidence'",
        )
    path = isolated / "snapshot.json"
    export(path)
    monkeypatch.setattr(
        settings, "database_url", "sqlite:///" + str(isolated / "restored.db")
    )
    restore(path)
    restore(path)
    assert len(documents()) == 1


def test_snapshot_license_guard(indexed, isolated):
    with pytest.raises(ValueError, match="licensed"):
        export(isolated / "index.json")
