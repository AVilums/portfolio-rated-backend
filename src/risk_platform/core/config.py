from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Market Risk Control Platform"
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://risk:risk@localhost:5432/risk"
    market_data_max_age_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
