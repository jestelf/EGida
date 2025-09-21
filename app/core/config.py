from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    project_name: str = Field(
        default="EGida",
        alias="PROJECT_NAME",
        validation_alias=AliasChoices("PROJECT_NAME", "project_name"),
    )
    environment: str = Field(
        default="local",
        alias="ENVIRONMENT",
        validation_alias=AliasChoices("ENVIRONMENT", "environment"),
    )
    debug: bool = Field(default=True, alias="DEBUG", validation_alias=AliasChoices("DEBUG", "debug"))
    secret_key: str = Field(
        default="change-me",
        alias="SECRET_KEY",
        validation_alias=AliasChoices("SECRET_KEY", "secret_key"),
    )
    algorithm: str = Field(
        default="HS256",
        alias="ALGORITHM",
        validation_alias=AliasChoices("ALGORITHM", "algorithm"),
    )
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes"),
    )
    refresh_token_expire_minutes: int = Field(
        default=60 * 24 * 14,
        alias="REFRESH_TOKEN_EXPIRE_MINUTES",
        validation_alias=AliasChoices("REFRESH_TOKEN_EXPIRE_MINUTES", "refresh_token_expire_minutes"),
    )
    app_base_url: str = Field(
        default="http://localhost:8000",
        alias="APP_BASE_URL",
        validation_alias=AliasChoices("APP_BASE_URL", "app_base_url"),
    )
    sqlite_echo: bool = Field(
        default=False,
        alias="SQLITE_ECHO",
        validation_alias=AliasChoices("SQLITE_ECHO", "sqlite_echo"),
    )
    sqlite_journal_mode: str = Field(
        default="WAL",
        alias="SQLITE_JOURNAL_MODE",
        validation_alias=AliasChoices("SQLITE_JOURNAL_MODE", "sqlite_journal_mode"),
    )
    cors_origins: List[str] = Field(
        default_factory=list,
        alias="CORS_ORIGINS",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )
    database_path: Path = Field(
        default=PROJECT_ROOT / "data" / "app.db",
        alias="DATABASE_PATH",
        validation_alias=AliasChoices("DATABASE_PATH", "database_path"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, str):
            try:
                import json

                decoded = json.loads(value)
                if isinstance(decoded, list):
                    return [str(origin).strip() for origin in decoded if str(origin).strip()]
            except json.JSONDecodeError:
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        return []

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    @property
    def data_directory(self) -> Path:
        return self.database_path.parent


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
