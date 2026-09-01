from __future__ import annotations

from datetime import date
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
    official_search_urls: Annotated[tuple[str, ...], NoDecode] = (
        "https://trello.com/b/F2RU9ia9/the-division-2-known-issues",
    )
    community_search_domains: Annotated[tuple[str, ...], NoDecode] = (
        "wikipedia.org",
        "thedivision.fandom.com",
        "reddit.com",
        "gaming.stackexchange.com",
        "gamefaqs.gamespot.com",
        "steamcommunity.com",
        "thedivisionforums.com",
        "prototrack.gg",
        "when.shd.support",
        "divisiontimers.com",
        "thedivisiondispatch.com",
        "siriusarc7.github.io",
        "github.com",
        "raw.githubusercontent.com",
        "rubenalamina.mx",
        "youtube.com",
        "youtu.be",
    )
    current_game_version: str = "Y8S3 Red Horizon"
    current_game_version_started_on: date = date(2026, 8, 27)
    community_loadout_indexing_enabled: bool = True

    video_inspection_enabled: bool = True
    video_max_duration_seconds: int = Field(default=30, ge=1, le=60)
    video_max_bytes: int = Field(default=50_000_000, ge=1_000_000, le=100_000_000)
    video_sample_frames: int = Field(default=12, ge=4, le=20)
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"

    autonomous_research_enabled: bool = True
    autonomous_research_interval_hours: int = Field(default=6, ge=1, le=168)
    autonomous_full_sweep_hours: int = Field(default=24, ge=6, le=720)
    autonomous_max_findings_per_run: int = Field(default=20, ge=1, le=50)
    autonomous_auto_promote_official: bool = True

    rotation_updates_enabled: bool = True
    rotation_refresh_minutes: int = Field(default=60, ge=15, le=1440)
    rotation_web_refresh_hours: int = Field(default=6, ge=1, le=48)
    rotation_escalation_url: str = "https://hi-dep.github.io/division2/data/event/index.json"
    rotation_calendar_url: str = "https://when.shd.support/api/v1/calendar/"

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

    @field_validator(
        "official_search_domains",
        "official_search_urls",
        "community_search_domains",
        mode="before",
    )
    @classmethod
    def split_domains(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("official_search_urls")
    @classmethod
    def valid_official_search_urls(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.startswith("https://") for item in value):
            raise ValueError("official search URLs must use HTTPS")
        return value

    @field_validator("rotation_escalation_url", "rotation_calendar_url")
    @classmethod
    def valid_rotation_urls(cls, value: str) -> str:
        if not value.startswith("https://") or len(value) > 500:
            raise ValueError("rotation feed URLs must be bounded HTTPS URLs")
        return value

    @field_validator("openai_hard_budget_usd", "member_reserve_usd")
    @classmethod
    def nonnegative_money(cls, value: float) -> float:
        if value < 0:
            raise ValueError("budget values cannot be negative")
        return value

    @field_validator("current_game_version")
    @classmethod
    def valid_current_game_version(cls, value: str) -> str:
        clean = " ".join(value.split())
        if not clean or len(clean) > 80:
            raise ValueError("current game version must contain 1 to 80 characters")
        return clean

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
    def autonomy_intervals_are_ordered(self) -> Settings:
        if self.autonomous_full_sweep_hours < self.autonomous_research_interval_hours:
            raise ValueError("autonomous full sweep interval cannot be below check interval")
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
