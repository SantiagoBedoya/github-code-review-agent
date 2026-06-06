from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    webhook_secret: str = ""

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://localhost:5432/github_code_review"

    # Bandit algorithm params
    bandit_epsilon: float = 0.3
    bandit_alpha: float = 0.2
    bandit_beta: float = 0.1
    bandit_epsilon_decay: float = 0.95
    bandit_epsilon_min: float = 0.05
    bandit_decay_interval: int = 10

    # File filtering
    max_changed_lines: int = 300


settings = Settings()
