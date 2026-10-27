from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Стройкомплекс"
    database_url: str = "sqlite:///./stroykompleks.sqlite3"
    admin_email: str = "admin@example.com"
    admin_password: str = "demo-admin-password"
    session_secret: str = "demo-session-secret-change-before-public-use"
    cookie_secure: bool = False
    llm_mode: str = "demo"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 25
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parents[3] / ".env", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
