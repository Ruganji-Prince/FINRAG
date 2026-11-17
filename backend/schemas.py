from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

ALLOWED_HOSTS = {"www.bnr.rw", "bnr.rw", "statistics.gov.rw", "www.statistics.gov.rw"}


def safe_url(value):
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or p.hostname not in ALLOWED_HOSTS
        or p.username
        or p.password
        or p.port not in (None, 443)
    ):
        raise ValueError("Only HTTPS official BNR/NISR URLs on port 443 are allowed")
    return value


class DocumentMetadata(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    organization: str = Field(pattern="^(BNR|NISR)$")
    publication_date: date
    source_url: str
    document_type: str = Field(min_length=3, max_length=80)
    landing_url: str
    usage_notes: str = Field(min_length=10)

    @field_validator("source_url", "landing_url")
    @classmethod
    def url(cls, v):
        return safe_url(v)

    @field_validator("publication_date")
    @classmethod
    def valid_date(cls, v):
        if v > date.today():
            raise ValueError("Publication date is in the future")
        return v


class Filters(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    organization: str | None = Field(default=None, pattern="^(BNR|NISR)$")
    year: int | None = Field(default=None, ge=1900, le=2100)
    document_type: str | None = Field(default=None, max_length=80)
    document_ids: list[int] | None = Field(default=None, min_length=1, max_length=4)
    document_id: int | None = Field(default=None, ge=1)


class Query(BaseModel):
    retrieval_mode: Literal["keyword", "vector", "hybrid"] = "hybrid"
    question: str = Field(min_length=5, max_length=2000)
    k: int = Field(default=5, ge=1, le=12)
    filters: Filters = Field(default_factory=Filters)

    @field_validator("question")
    @classmethod
    def nonempty(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("Enter a meaningful question")
        return v.strip()


class Compare(BaseModel):
    left_id: int = Field(ge=1)
    right_id: int = Field(ge=1)
    topic: str = Field(default="economic outlook", min_length=3, max_length=300)

    @field_validator("right_id")
    @classmethod
    def different(cls, v, info):
        if info.data.get("left_id") == v:
            raise ValueError("Choose two different reports")
        return v


class Evidence(BaseModel):
    chunk_id: int
    page: int = Field(ge=1)
    section: str
    text: str
    document_id: int
    title: str
    organization: str
    publication_date: str
    source_url: str
    document_type: str
    score: float
    term_coverage: float
    citation_url: str
    semantic_similarity: float | None = None
    retrieval_mode: str = "hybrid"


class AnswerResponse(BaseModel):
    mode: str
    abstained: bool
    answer: str
    evidence: list[Evidence]
    usage: dict | None
    estimated_cost_usd: float | None
    support_assessment: str
    latency_ms: float
    claims: list[dict] = Field(default_factory=list)
    provider: str = "none"
    generation_performed: bool = False


class SearchResponse(BaseModel):
    evidence: list[Evidence]


class ComparisonResponse(BaseModel):
    topic: str
    left: AnswerResponse
    right: AnswerResponse
    interpretation: str
    comparison: AnswerResponse | None = None
