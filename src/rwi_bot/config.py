from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration loaded only from the host environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RWI_",
        case_sensitive=False,
        extra="ignore",
    )

    discord_token: SecretStr
    discord_application_id: int = Field(gt=0)
    discord_guild_id: int = Field(gt=0)
    owner_user_id: int = Field(gt=0)
    database_url: SecretStr
    openai_api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")

    model_normal: str = "gpt-5.6-terra"
    model_complex: str = "gpt-5.6"
    model_economy: str = "gpt-5.6-luna"
    embedding_model: str = "text-embedding-3-small"

    openai_hard_budget_usd: float = 25.0
    member_reserve_usd: float = 5.0
    web_search_enabled: bool = True
    official_search_domains: Annotated[tuple[str, ...], NoDecode] = ("ubisoft.com",)

    log_level: str = "INFO"
    runtime_dir: Path = Path("/data/runtime")
    auto_bootstrap_server: bool = False
    sync_commands: bool = True

    spam_detection_enabled: bool = True
    spam_repeated_messages: int = Field(default=3, ge=2, le=20)
    spam_burst_messages: int = Field(default=7, ge=3, le=50)
    spam_severe_messages: int = Field(default=12, ge=3, le=100)
    spam_window_seconds: int = Field(default=10, ge=2, le=120)
    spam_incident_cooldown_seconds: int = Field(default=4, ge=0, le=120)
    spam_history_hours: int = Field(default=24, ge=1, le=720)
    spam_timeout_minutes: int = Field(default=10, ge=1, le=10080)

    @field_validator("official_search_domains", mode="before")
    @classmethod
    def split_domains(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("openai_hard_budget_usd", "member_reserve_usd")
    @classmethod
    def nonnegative_money(cls, value: float) -> float:
        if value < 0:
            raise ValueError("budget values cannot be negative")
        return value

    @field_validator("discord_token", "database_url", "openai_api_key")
    @classmethod
    def nonempty_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("required secret values cannot be blank")
        return value

    @model_validator(mode="after")
    def reserve_fits_budget(self) -> Settings:
        if self.member_reserve_usd > self.openai_hard_budget_usd:
            raise ValueError("member reserve cannot exceed the hard budget")
        return self

    @model_validator(mode="after")
    def spam_thresholds_are_ordered(self) -> Settings:
        if self.spam_burst_messages < self.spam_repeated_messages:
            raise ValueError("spam burst threshold cannot be below repeated threshold")
        if self.spam_severe_messages < self.spam_burst_messages:
            raise ValueError("spam severe threshold cannot be below burst threshold")
        return self

    @field_validator("runtime_dir")
    @classmethod
    def absolute_runtime_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
