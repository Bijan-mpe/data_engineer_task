from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All application settings.
    Pydantic-settings reads these from environment variables automatically.
    Variable names are case-insensitive: POSTGRES_HOST == postgres_host
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "scope_ratings"
    postgres_user: str = "scope"
    postgres_password: str

    # App
    data_dir: Path = Path("./data")
    log_level: str = "INFO"
    environment: Literal["development", "staging", "production"] = "development"

    @computed_field
    @property
    def database_url(self) -> str:
        """
        Build the full database URL from individual parts.
        Used by SQLAlchemy to connect.
        Example: postgresql://scope:pass@localhost:5432/scope_ratings
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

settings = Settings()
