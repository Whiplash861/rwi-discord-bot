from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    official_search_domains: tuple[str, ...] = ("ubisoft.com",)

    log_level: str = "INFO"
    runtime_dir: Path = Path("/data/runtime")
    auto_bootstrap_server: bool = False
    sync_commands: bool = True

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

    @field_validator("runtime_dir")
    @classmethod
    def absolute_runtime_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
