import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from backend.config import ROOT, settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, organization TEXT NOT NULL,
 publication_date TEXT NOT NULL, source_url TEXT NOT NULL, document_type TEXT NOT NULL,
 landing_url TEXT NOT NULL, usage_notes TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
 retrieved_at TEXT NOT NULL, status TEXT NOT NULL, embedding_model TEXT NOT NULL,
 quality_json TEXT NOT NULL, path TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (
 id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
 page INTEGER NOT NULL, section TEXT NOT NULL, text TEXT NOT NULL, content_hash TEXT NOT NULL,
 embedding TEXT NOT NULL, UNIQUE(document_id, content_hash));
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, source_url TEXT NOT NULL,
 status TEXT NOT NULL, detail TEXT NOT NULL);
"""


def now():
    return datetime.now(UTC).isoformat()


def is_pg():
    return settings.database_url.startswith("postgresql")


def sqlite_path():
    p = Path(settings.database_url.removeprefix("sqlite:///"))
    return p if p.is_absolute() else ROOT / p


@contextmanager
def connection(readonly=False):
    if is_pg():
        import psycopg
        from psycopg.rows import dict_row

        url = (
            (settings.query_database_url or settings.database_url)
            if readonly
            else settings.database_url
        )
        conn = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
        if readonly:
            conn.execute("SET TRANSACTION READ ONLY")
    else:
        p = sqlite_path()
        if readonly:
            conn = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(p)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        if readonly:
            conn.execute("PRAGMA query_only=ON")
    try:
        yield conn
        if not readonly:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(c, sql, args=()):
    return c.execute(sql.replace("?", "%s") if is_pg() else sql, args)


def initialize():
    from backend.migrate import migrate

    migrate()


def rows(sql, args=()):
    with connection(True) as c:
        return [dict(x) for x in execute(c, sql, args).fetchall()]


def audit(url, status, detail):
    with connection() as c:
        execute(
            c,
            "INSERT INTO audit(occurred_at,source_url,status,detail) VALUES(?,?,?,?)",
            (now(), url, status, detail[:1000]),
        )


def documents():
    return rows("SELECT * FROM documents ORDER BY publication_date DESC")


def stats():
    docs = documents()
    logs = rows("SELECT * FROM audit ORDER BY id DESC LIMIT 100")
    return {
        "documents": len(docs),
        "chunks": rows("SELECT count(*) AS n FROM chunks")[0]["n"],
        "failed_runs": rows("SELECT count(*) AS n FROM audit WHERE status='failed'")[0][
            "n"
        ],
        "duplicate_runs": rows(
            "SELECT count(*) AS n FROM audit WHERE status='duplicate'"
        )[0]["n"],
        "last_success": next(
            (x["occurred_at"] for x in logs if x["status"] == "indexed"), None
        ),
        "quality": [
            {"id": d["id"], "title": d["title"], **json.loads(d["quality_json"])}
            for d in docs
        ],
        "audit": logs,
        "database": "PostgreSQL / pgvector" if is_pg() else "SQLite demonstration",
        "lineage": "official URL -> bounded download -> SHA256 -> page extraction -> quality -> chunks -> embedding -> index",
    }
