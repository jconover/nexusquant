"""Service and Alpaca settings.

Two BaseSettings classes live here. Service settings instantiate at
module load (all have defaults). AlpacaSettings is instantiated on
demand in the FastAPI lifespan so tests can monkeypatch env vars
without triggering eager validation at import time.

The AlpacaSettings validators are binding per the alpaca-paper skill:
any non-paper configuration crashes the service at startup. The
validators deliberately duplicate what CI greps for -- belt and braces.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIGNAL_", extra="ignore")

    service_name: str = "signal"
    log_level: str = "INFO"


class AlpacaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ALPACA_",
        env_file=".env",
        extra="ignore",
    )

    api_key_id: str = Field(..., min_length=1)
    api_secret_key: str = Field(..., min_length=1)
    paper: bool = True
    base_url: str = "https://paper-api.alpaca.markets"
    data_feed: str = "iex"

    @field_validator("paper")
    @classmethod
    def must_be_paper(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("ALPACA_PAPER must be true. Live trading is not supported.")
        return v

    @field_validator("base_url")
    @classmethod
    def must_be_paper_url(cls, v: str) -> str:
        if v.startswith("https://api.alpaca.markets"):
            raise ValueError("Live trading URL is banned in this codebase.")
        if "paper-api.alpaca.markets" not in v:
            raise ValueError(f"ALPACA_BASE_URL must point to paper-api.alpaca.markets, got: {v}")
        return v


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        extra="ignore",
    )

    host: str = "postgres"
    port: int = 5432
    user: str = "nexusquant"
    password: str = "nexusquant"
    db: str = "nexusquant"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


settings = Settings()
