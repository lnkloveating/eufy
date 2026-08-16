"""Runtime configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "eufy Future Product Forecaster"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'data' / 'app.db').as_posix()}"
    evidence_path: Path = BACKEND_ROOT / "data" / "evidence"
    competitor_evidence_path: Path = BACKEND_ROOT / "data" / "competitors"
    llm_api_key: str = Field(default="", repr=False)
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 6_000
    stage_timeout_seconds: float = 75.0
    workflow_timeout_seconds: float = 900.0
    feishu_app_id: str = ""
    feishu_app_secret: str = Field(default="", repr=False)
    feishu_bitable_app_token: str = ""
    feishu_wiki_node_token: str = ""
    feishu_bitable_table_id: str = ""
    feishu_bitable_view_id: str = ""
    feishu_bitable_url: str = ""
    feishu_api_base_url: str = "https://open.feishu.cn/open-apis"
    feishu_timeout_seconds: float = 20.0
    public_app_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", BACKEND_ROOT / ".env.feishu"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
