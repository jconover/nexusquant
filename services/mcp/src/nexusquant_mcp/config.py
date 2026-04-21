from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", extra="ignore")

    service_name: str = "mcp"
    log_level: str = "INFO"


settings = Settings()
