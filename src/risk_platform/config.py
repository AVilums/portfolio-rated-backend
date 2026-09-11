from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://risk:risk@localhost:5432/risk"
    app_env: Literal["local", "test", "production"] = "production"
    session_hours: int = 12
    alpha_vantage_api_key: SecretStr | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
