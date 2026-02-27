from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../deploy/.env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Orion Range Core"
    app_version: str = "0.1.0"
    app_description: str = "Open-source Cyber Range Orchestrator (Core)"
    orion_env: str = Field(default="dev", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Application log level")


settings = Settings()
