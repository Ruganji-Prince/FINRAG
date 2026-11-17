"""Real PostgreSQL quota checks; requires a dedicated disposable _test database."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import pytest


@pytest.mark.skipif(
    not os.getenv("FINRAG_TEST_PG_URL"), reason="PostgreSQL not configured"
)
def test_atomic_gateway_quota():
    import psycopg

    url = os.environ["FINRAG_TEST_PG_URL"]
    assert urlsplit(url).path.endswith("_test")
    setup = (
        Path(__file__).resolve().parents[1] / "deploy/postgres/gateway-quota.sql"
    ).read_text()
    with psycopg.connect(url) as c:
        c.execute(setup)
        c.execute("TRUNCATE finrag_gateway.counters")
        c.execute("UPDATE finrag_gateway.policy SET daily_queries=20")

    def consume(i):
        with psycopg.connect(url) as c:
            c.execute("SET LOCAL ROLE finrag_gateway")
            return c.execute(
                "SELECT finrag_gateway.consume_quota('query', %s)", [format(i, "064x")]
            ).fetchone()[0]

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(consume, range(32)))
    assert sum(outcomes) == 20
    with psycopg.connect(url) as c:
        c.execute(setup)
        assert (
            c.execute(
                "SELECT n FROM finrag_gateway.counters WHERE key LIKE 'query:d:%'"
            ).fetchone()[0]
            == 20
        )
        c.execute("SET LOCAL ROLE finrag_gateway")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM finrag_gateway.counters")
    with psycopg.connect(url) as c:
        c.execute("SET LOCAL ROLE finrag_gateway")
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            c.execute("SELECT finrag_gateway.consume_quota('invalid','bad')")
