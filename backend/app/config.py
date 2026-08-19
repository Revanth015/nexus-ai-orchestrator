from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NEXUS"
    env: str = "development"
    free_only: bool = True
    background_execution: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = "sqlite:///./nexus.db"
    ollama_base_url: str = "http://127.0.0.1:11434"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
