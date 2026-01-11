from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = Field(default="redis://localhost:6379/0")

    ark_base_url: str = Field(default="https://ark.cn-beijing.volces.com/api/v3")
    ark_api_key: str | None = Field(default=None)
    ark_model: str = Field(default="doubao-seed-1-8-251228")

    stage_summary_min_interval_s: int = Field(default=120)
    stage_summary_min_chars: int = Field(default=1200)
    stage_summary_max_utterances: int = Field(default=120)


settings = Settings()

