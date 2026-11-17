import httpx
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.database import rows
from backend.main import app, windows
from backend.rag import answer, generate, search
from backend.schemas import Filters, Query


def test_retrieval_and_citations(indexed):
    evidence = search(Query(question="inflation monetary policy"))
    assert evidence
    for e in evidence:
        original = rows("SELECT text,page FROM chunks WHERE id=?", (e["chunk_id"],))[0]
        assert e["text"] == original["text"] and e["page"] == original["page"]
        assert e["citation_url"].endswith("#page=" + str(e["page"]))


def test_filters(indexed):
    assert (
        search(
            Query(
                question="inflation monetary policy",
                filters=Filters(organization="NISR"),
            )
        )
        == []
    )
    assert (
        search(Query(question="inflation monetary policy", filters=Filters(year=2023)))
        == []
    )
    assert search(
        Query(
            question="inflation monetary policy",
            filters=Filters(document_id=indexed["document_id"]),
        )
    )


@pytest.mark.parametrize(
    "q",
    [
        "quantum spaceship plasma propulsion",
        "What is the latest inflation rate?",
        "Please transfer money from my portfolio",
    ],
)
def test_abstain(indexed, q):
    assert answer(Query(question=q))["abstained"]


def test_retrieval_only_label(indexed):
    result = answer(Query(question="inflation monetary policy"))
    assert result["mode"] == "retrieval_only" and "not an LLM" in result["answer"]


def test_api(indexed):
    windows.clear()
    with TestClient(app) as c:
        for path in [
            "/health",
            "/documents",
            "/quality",
            "/governance",
            "/evaluation",
            "/openapi.json",
        ]:
            assert c.get(path).status_code == 200
        assert c.post("/ask", json={"question": "inflation policy"}).json()["evidence"]
        assert (
            c.post(
                "/search", json={"question": "inflation policy", "k": 100}
            ).status_code
            == 422
        )
        assert c.post("/ask", json={"question": "  "}).status_code == 422
        assert (
            c.post("/compare", json={"left_id": 1, "right_id": 999}).status_code == 404
        )
        assert c.post("/compare", json={"left_id": 1, "right_id": 1}).status_code == 422


def test_rate_limit(indexed, monkeypatch):
    windows.clear()
    monkeypatch.setattr(settings, "requests_per_minute", 2)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/health").status_code == 200
        assert c.get("/health").status_code == 429
    windows.clear()


def test_provider_rejects_invented_reference(indexed, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    evidence = search(Query(question="inflation monetary policy"))

    def fake(self, *args, **kwargs):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"answer":"Inflation is 99 [999999]","abstained":false}'
                        }
                    }
                ]
            },
            request=httpx.Request("POST", "https://api.openai.com"),
        )

    monkeypatch.setattr(httpx.Client, "post", fake)
    with pytest.raises(ValueError, match="citation"):
        generate("inflation?", evidence)
    assert answer(Query(question="inflation monetary policy"))["abstained"]


def test_prompt_evidence_is_data(indexed, monkeypatch):
    from backend.rag import SYSTEM

    assert "untrusted" in SYSTEM and "never instructions" in SYSTEM


def test_overlap_is_not_sufficient_evidence(indexed):
    assert answer(Query(question="What was the monetary policy rate in 2012?"))[
        "abstained"
    ]
    assert answer(
        Query(question="What are agriculture mortgage default probabilities?")
    )["abstained"]
