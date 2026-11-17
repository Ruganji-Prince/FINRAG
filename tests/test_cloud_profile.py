import hashlib
import json
from types import SimpleNamespace

import pytest

from backend.cloud_config import validate_cloud
from backend.config import settings
from backend.embeddings import identity


def cloud(**updates):
    values = dict(
        public_mode=True,
        health_requires_auth=True,
        startup_database_check=False,
        preload_models=False,
        api_access_token="test-only-bearer-" * 4,
        auto_migrate=False,
        llm_provider="gemini",
        llm_api_key="test-only-provider",
        llm_model="fixture-model",
        embedding_backend="onnx",
        embedding_batch_size=8,
        database_url="postgresql://finrag_reader:test-only@database.example/finrag?sslmode=require",
        query_database_url="",
    )
    values.update(updates)
    return SimpleNamespace(**values)


def test_secure_cloud_profile_accepts_hosted_reader():
    validate_cloud(cloud())


@pytest.mark.parametrize(
    "updates",
    [
        {"public_mode": False},
        {"health_requires_auth": False},
        {"startup_database_check": True},
        {"preload_models": True},
        {"api_access_token": "short"},
        {"auto_migrate": True},
        {"llm_provider": "local"},
        {"llm_api_key": ""},
        {"embedding_backend": "hash"},
        {"embedding_batch_size": 32},
        {"database_url": "sqlite:///demo.db"},
        {
            "database_url": "postgresql://neondb_owner:fixture@database.example/db?sslmode=require"
        },
        {
            "database_url": "postgresql://finrag_reader:fixture@database.example/db?sslmode=disable"
        },
        {
            "query_database_url": "postgresql://finrag_reader:fixture@localhost/db?sslmode=require"
        },
    ],
)
def test_unsafe_cloud_configuration_is_rejected(updates):
    with pytest.raises(ValueError):
        validate_cloud(cloud(**updates))


def test_onnx_identity_preserves_pinned_index_compatibility(monkeypatch):
    monkeypatch.setattr(settings, "embedding_backend", "sentence-transformers")
    expected = identity()
    monkeypatch.setattr(settings, "embedding_backend", "onnx")
    assert identity() == expected and "@" in expected


def test_corrupt_onnx_assets_fail_before_runtime_initialization(tmp_path, monkeypatch):
    from backend import onnx_embeddings

    (tmp_path / "model.onnx").write_bytes(b"TEST FIXTURE ONLY")
    (tmp_path / "tokenizer.json").write_text("{}")
    manifest = {
        "repository": settings.embedding_model,
        "revision": settings.embedding_revision,
        "sha256": {
            "model.onnx": "invalid",
            "tokenizer.json": hashlib.sha256(b"{}").hexdigest(),
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(settings, "onnx_model_dir", str(tmp_path))
    monkeypatch.setattr(onnx_embeddings, "_INSTANCE", None)
    onnx_embeddings.model.cache_clear()
    with pytest.raises(ValueError, match="checksum"):
        onnx_embeddings.model()
    onnx_embeddings.model.cache_clear()


def test_cloud_health_rejects_unauthorized_calls_before_database_work(
    isolated, monkeypatch
):
    from fastapi.testclient import TestClient

    import backend.main as service

    for key, value in dict(
        public_mode=True,
        api_access_token="test-only-health-key-" * 3,
        health_requires_auth=True,
        startup_database_check=False,
        auto_migrate=False,
        preload_models=False,
    ).items():
        monkeypatch.setattr(settings, key, value)

    def unexpected(*args, **kwargs):
        raise AssertionError("Unauthorized cold request touched the database")

    monkeypatch.setattr(service, "rows", unexpected)
    with TestClient(service.app) as client:
        assert client.get("/health").status_code == 401
        assert client.get("/documents").status_code == 401


def test_onnx_inference_has_bounded_backpressure(monkeypatch):
    from backend import onnx_embeddings

    monkeypatch.setattr(settings, "local_queue_timeout_seconds", 0.01)
    monkeypatch.setattr(onnx_embeddings, "_encode", lambda texts: [[0.0] * 384])
    with onnx_embeddings._RUN_LOCK:
        with pytest.raises(TimeoutError, match="capacity"):
            onnx_embeddings.encode(["fixture"])
    assert len(onnx_embeddings.encode(["fixture"])[0]) == 384
