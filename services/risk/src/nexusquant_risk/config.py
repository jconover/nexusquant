from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RISK_", extra="ignore")

    service_name: str = "risk"
    log_level: str = "INFO"


settings = Settings()
