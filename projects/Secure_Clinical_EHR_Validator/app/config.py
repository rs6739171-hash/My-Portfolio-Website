from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or None
    llm_api_base: str | None = os.getenv("LLM_API_BASE") or None
    llm_model: str | None = os.getenv("LLM_MODEL") or None
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
    max_llm_calls_per_hour: int = int(os.getenv("MAX_LLM_CALLS_PER_HOUR", "20"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "320"))
    api_url: str = os.getenv("API_URL", "http://127.0.0.1:8000")
    app_password: str | None = os.getenv("APP_PASSWORD") or None

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_base and self.llm_model)


settings = Settings()
