from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    health_requires_auth: bool = False
    startup_database_check: bool = True
    public_mode: bool = False
    api_access_token: str = ""
    max_request_bytes: int = 32768
    llm_timeout_seconds: float = 60
    llm_max_attempts: int = 2
    local_queue_timeout_seconds: float = 5
    preload_models: bool = False
    auto_migrate: bool = True
    database_url: str = "sqlite:///data/finrag.db"
    query_database_url: str = ""
    onnx_model_dir: str = ""
    embedding_backend: str = "hash"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_revision: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    embedding_batch_size: int = 32
    semantic_min_similarity: float = 0.30
    local_llm_model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    local_llm_revision: str = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
    local_llm_quantize: bool = False
    local_llm_max_context: int = 4096
    llm_base_url: str = "https://api.openai.com/v1"
    llm_max_tokens: int = 1200
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_model: str = ""
    max_download_bytes: int = 25000000
    requests_per_minute: int = 60
    api_url: str = "http://127.0.0.1:8000"
    input_cost_per_million: float = 0
    output_cost_per_million: float = 0


settings = Settings()
