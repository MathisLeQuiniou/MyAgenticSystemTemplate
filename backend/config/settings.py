"""
Centralised application settings.

Values come from environment variables (and the `.env` file at the repo root).
Model profiles and MCP servers live in YAML files next to this module so they
can be edited without touching code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
CONFIG_DIR = BACKEND_DIR / "config"
PROMPTS_DIR = BACKEND_DIR / "prompts"
SKILLS_DIR = BACKEND_DIR / "skills"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    app_name: str = "MyAgenticSystem"
    app_env: str = "dev"
    log_level: str = "INFO"

    # --- API ---------------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    # --- Database ----------------------------------------------------------
    database_url: str = ""
    db_schema: str = "app"
    checkpoint_schema: str = "langgraph"
    db_echo: bool = False

    # --- LLM ---------------------------------------------------------------
    models_config_path: Path = CONFIG_DIR / "models.yaml"
    default_model_profile: str | None = None

    # --- Tools -------------------------------------------------------------
    mcp_config_path: Path = CONFIG_DIR / "mcp_servers.yaml"

    # --- Skills ------------------------------------------------------------
    skills_dir: Path = SKILLS_DIR
    skill_max_file_chars: int = 50_000  # max size returned by load_skill / read_skill_file

    # --- Graph execution -----------------------------------------------------
    graph_recursion_limit: int = 50
    run_timeout_seconds: float = 300
    trace_max_payload_chars: int = 20_000  # truncate large payloads stored in events
    stream_llm_tokens: bool = True  # push token events over SSE (never persisted)

    @property
    def checkpoint_database_url(self) -> str:
        """psycopg-compatible URL derived from `database_url`."""
        url = self.database_url
        for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql://" + url[len(prefix):]
        return url

@lru_cache
def get_settings() -> Settings:
    return Settings()
