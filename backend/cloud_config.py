"""Fail-closed serverless profile; local application defaults remain separate."""

from urllib.parse import parse_qs, urlsplit


def validate_cloud(settings):
    if not settings.public_mode or len(settings.api_access_token) < 32:
        raise ValueError("Cloud API requires public-mode bearer authentication")
    if (
        not settings.health_requires_auth
        or settings.startup_database_check
        or settings.preload_models
    ):
        raise ValueError(
            "Cloud API must defer expensive work until authenticated requests"
        )
    if settings.auto_migrate or settings.llm_provider not in {"gemini", "openai"}:
        raise ValueError("Cloud API requires disabled DDL and an explicit hosted LLM")
    if not settings.llm_api_key or not settings.llm_model:
        raise ValueError("Hosted LLM credentials/model are missing")
    if not 1 <= settings.embedding_batch_size <= 8:
        raise ValueError(
            "Cloud embedding batches must remain within the resource budget"
        )
    if settings.embedding_backend != "onnx":
        raise ValueError(
            "Serverless profile requires the bounded ONNX embedding runtime"
        )
    for value in {
        settings.database_url,
        settings.query_database_url or settings.database_url,
    }:
        url = urlsplit(value)
        if (
            url.scheme != "postgresql"
            or url.username != "finrag_reader"
            or not url.hostname
            or url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError(
                "Cloud API requires a hosted finrag_reader database connection"
            )
        if parse_qs(url.query).get("sslmode", [""])[0] not in {
            "require",
            "verify-ca",
            "verify-full",
        }:
            raise ValueError("Cloud database connections must require TLS")
