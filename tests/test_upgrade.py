import hashlib
import json
import sqlite3

import pytest

from backend.database import initialize, rows
from backend.rag import validate_claims


def test_migrations_are_idempotent(isolated):
    initialize()
    initialize()
    assert len(rows("SELECT * FROM schema_migrations")) == 2
    record = rows("SELECT * FROM governance_records")[0]
    assert (
        hashlib.sha256(record["payload_json"].encode()).hexdigest()
        == record["payload_sha256"]
    )


def test_schema_failure_rolls_back(isolated, monkeypatch, tmp_path):
    import backend.migrate as module

    folder = tmp_path / "backend/migrations"
    folder.mkdir(parents=True)
    (folder / "003_sqlite.sql").write_text(
        "CREATE TABLE should_rollback(id INTEGER); INVALID SQL;"
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    with pytest.raises(sqlite3.Error):
        module.migrate()
    assert not rows("SELECT name FROM sqlite_master WHERE name='should_rollback'")


def evidence():
    return [
        {
            "chunk_id": 1,
            "text": "In 2025, GDP grew by 9.4 percent and agriculture grew by 7 percent.",
        }
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "abstained": False,
            "claims": [{"chunk_id": 999, "quote": "GDP grew by 9.4 percent"}],
        },
        {
            "abstained": False,
            "claims": [{"chunk_id": 1, "quote": "GDP grew by 99 percent"}],
        },
        {"abstained": False, "claims": []},
        {
            "abstained": True,
            "claims": [{"chunk_id": 1, "quote": "GDP grew by 9.4 percent"}],
        },
        {
            "abstained": False,
            "claims": [{"chunk_id": True, "quote": "GDP grew by 9.4 percent"}],
        },
        {"abstained": "false", "claims": []},
    ],
)
def test_unsupported_claims_rejected(payload):
    with pytest.raises(ValueError):
        validate_claims(payload, evidence())


def test_exact_quote_supported():
    result = validate_claims(
        {
            "abstained": False,
            "claims": [{"chunk_id": 1, "quote": "GDP grew by 9.4 percent"}],
        },
        evidence(),
    )
    assert result[0]["quote"] == "GDP grew by 9.4 percent"


def test_free_form_unverified_answer_not_published(monkeypatch):
    from backend.rag import generate

    monkeypatch.setattr(
        "backend.providers.complete",
        lambda *args: (
            json.dumps(
                {
                    "abstained": False,
                    "answer": "The rate is 12345 percent [1]",
                    "claims": [{"chunk_id": 1, "quote": "GDP grew by 9.4 percent"}],
                }
            ),
            {"prompt_tokens": 10, "completion_tokens": 20},
            None,
        ),
    )
    ev = [
        {
            "chunk_id": 1,
            "text": evidence()[0]["text"],
            "title": "Test",
            "publication_date": "2026-01-01",
            "page": 3,
        }
    ]
    result = generate("GDP growth?", ev)
    assert "12345" not in result["answer"] and "[1]" in result["answer"]


@pytest.mark.parametrize(
    "question",
    [
        "Should I buy bank stocks?",
        "Please invest my savings",
        "Give personalized investment instructions",
    ],
)
def test_personalized_decision_refusal(indexed, question):
    from backend.rag import answer
    from backend.schemas import Query

    result = answer(Query(question=question))
    assert result["abstained"] and not result["evidence"]


def test_unknown_sentence_selection_is_rejected(monkeypatch):
    from backend.rag import generate

    monkeypatch.setattr(
        "backend.providers.complete",
        lambda *args: ('{"abstained":false,"selections":["9999:0"]}', {}, None),
    )
    ev = [
        {
            "chunk_id": 1,
            "text": "GDP grew by 9.4 percent.",
            "title": "Test",
            "publication_date": "2026-01-01",
            "page": 3,
        }
    ]
    with pytest.raises(ValueError, match="sentence"):
        generate("GDP growth?", ev)


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_cloud_provider_success_is_source_validated(indexed, monkeypatch, provider):
    import httpx

    from backend.config import settings
    from backend.rag import answer, search
    from backend.schemas import Query

    query = Query(question="inflation monetary policy")
    hit = search(query)[0]
    payload = {
        "abstained": False,
        "claims": [
            {"chunk_id": hit["chunk_id"], "quote": "Inflation was 5.2 percent."}
        ],
    }

    def post(self, url, **kwargs):
        if provider == "gemini":
            assert "systemInstruction" in kwargs["json"]
            data = {
                "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
            }
        else:
            data = {
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        return httpx.Response(200, json=data, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "llm_provider", provider)
    monkeypatch.setattr(settings, "llm_api_key", "fixture-only-key")
    monkeypatch.setattr(settings, "llm_model", "fixture-model")
    monkeypatch.setattr(httpx.Client, "post", post)
    result = answer(query)
    assert result["mode"] == "llm" and not result["abstained"]
    assert result["claims"][0]["quote"] == "Inflation was 5.2 percent."
    assert result["usage"]["completion_tokens"] == 20


@pytest.mark.parametrize(
    "question,required,forbidden",
    [
        (
            "What was urban CPI annual increase?",
            "Urban CPI increased by 19.5 percent on annual basis.",
            "monthly",
        ),
        (
            "What was rural CPI annual increase?",
            "Rural CPI increased by 31.3 percent on annual basis.",
            "Urban",
        ),
    ],
)
def test_scope_and_frequency_context(question, required, forbidden, isolated):
    from backend.rag import sentence_context

    text = "Urban CPI increased by 19.5 percent on annual basis. Urban CPI increased by 3.3 percent on monthly basis. Rural CPI increased by 31.3 percent on annual basis."
    ev = [
        {
            "chunk_id": 1,
            "text": text,
            "title": "CPI",
            "publication_date": "2026-11-10",
            "page": 4,
        }
    ]
    context, lookup = sentence_context(ev, question)
    assert any(required == entry["quote"] for entry in lookup.values())
    assert all(forbidden not in entry["quote"] for entry in lookup.values())


def test_real_gdp_growth_not_confused_with_deflator(isolated):
    from backend.rag import sentence_context

    ev = [
        {
            "chunk_id": 1,
            "text": "GDP grew by 9.4 percent. GDP deflator increased by 7 percent. Agriculture increased by 7 percent.",
            "title": "GDP report",
            "publication_date": "2026-03-01",
            "page": 3,
        }
    ]
    context, lookup = sentence_context(ev, "What was GDP growth?")
    assert lookup and all("deflator" not in e["quote"] for e in lookup.values())
    assert any("9.4" in e["quote"] for e in lookup.values())


def test_governance_history_preserved(isolated, tmp_path):
    from pipelines.sync_governance import sync

    path = tmp_path / "policy.json"
    path.write_text('{"rule":"original"}')
    first = sync("test_policy", path)
    path.write_text('{"rule":"updated"}')
    second = sync("test_policy", path)
    assert first["sha256"] != second["sha256"]
    assert rows(
        "SELECT payload_json FROM governance_records WHERE registry_key=?",
        ("test_policy@" + first["sha256"],),
    )
    assert sync("test_policy", path)["status"] == "unchanged"


@pytest.mark.parametrize(
    "question,required,forbidden",
    [
        ("What share did services contribute to GDP?", "contributed", "grew"),
        ("What was first quarter GDP growth?", "first quarter", "9.4"),
        ("Compare nominal GDP estimates", "market prices", "per head"),
    ],
)
def test_financial_measure_context_is_not_interchangeable(
    isolated, question, required, forbidden
):
    from backend.rag import sentence_context

    text = "Services contributed 52 percent to GDP. Services grew by 9 percent. GDP grew by 9.4 percent. GDP grew by 6.5 percent in the first quarter. GDP at current market prices was estimated at 23,387 billion. GDP per head was estimated at 1,156."
    ev = [
        {
            "chunk_id": 1,
            "text": text,
            "title": "Annual GDP report",
            "publication_date": "2026-03-01",
            "page": 3,
        }
    ]
    _, lookup = sentence_context(ev, question)
    assert lookup and any(required in c["quote"] for c in lookup.values())
    assert all(forbidden not in c["quote"] for c in lookup.values())
