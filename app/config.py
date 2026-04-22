from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = Field(default="dev-secret-change-me")
    database_url: str = Field(default="sqlite:///library.db")

    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    admin_emails: List[str] = Field(default_factory=list)

    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.0-flash")
    ai_provider: str = Field(default="gemini_api")  # "gemini_api" | "vertex_ai"
    vertex_project_id: str = Field(default="")
    vertex_location: str = Field(default="us-central1")

    app_base_url: str = Field(default="http://localhost:8000")

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _split_admin_emails(cls, v):
        if isinstance(v, str):
            return [e.strip().lower() for e in v.split(",") if e.strip()]
        if isinstance(v, list):
            return [str(e).strip().lower() for e in v if str(e).strip()]
        return []

    @property
    def google_sso_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def gemini_enabled(self) -> bool:
        provider = (self.ai_provider or "gemini_api").strip().lower()
        if provider == "vertex_ai":
            return bool(self.vertex_project_id and self.vertex_location)
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
