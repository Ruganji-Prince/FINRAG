"""Generated deployment entrypoint; never loads the multi-GB local LLM."""

import os
from pathlib import Path

os.environ.setdefault("EMBEDDING_BACKEND", "onnx")
os.environ.setdefault("EMBEDDING_BATCH_SIZE", "8")
os.environ.setdefault("ONNX_MODEL_DIR", str(Path(__file__).parent / "models/minilm"))
os.environ.setdefault("AUTO_MIGRATE", "false")
os.environ.setdefault("PRELOAD_MODELS", "false")
os.environ.setdefault("STARTUP_DATABASE_CHECK", "false")
os.environ.setdefault("HEALTH_REQUIRES_AUTH", "true")
from backend.cloud_config import validate_cloud
from backend.config import settings

validate_cloud(settings)
from backend.main import app  # noqa: E402,F401
