from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rwi_bot.config import Settings


def valid_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "discord_token": "discord-placeholder",
        "discord_application_id": 1,
        "discord_guild_id": 2,
        "owner_user_id": 3,
        "database_url": "postgresql+asyncpg://user:password@localhost/database",
        "OPENAI_API_KEY": "openai-placeholder",
        "runtime_dir": Path("runtime-test"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_require_deployment_identifiers() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            discord_token="discord-placeholder",  # noqa: S106 - inert test value
            database_url="postgresql+asyncpg://user:password@localhost/database",
            OPENAI_API_KEY="openai-placeholder",
        )


def test_settings_reject_blank_secrets() -> None:
    with pytest.raises(ValidationError, match="cannot be blank"):
        valid_settings(discord_token="   ")  # noqa: S106 - validation fixture


def test_settings_reject_reserve_above_budget() -> None:
    with pytest.raises(ValidationError, match="reserve cannot exceed"):
        valid_settings(openai_hard_budget_usd=5, member_reserve_usd=6)


def test_settings_reject_inverted_spam_thresholds() -> None:
    with pytest.raises(ValidationError, match="spam severe threshold"):
        valid_settings(spam_burst_messages=10, spam_severe_messages=9)


def test_settings_repr_does_not_reveal_secrets() -> None:
    settings = valid_settings()

    rendered = repr(settings)

    assert "discord-placeholder" not in rendered
    assert "openai-placeholder" not in rendered
    assert "user:password" not in rendered


def test_settings_parse_comma_separated_domains_from_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "RWI_DISCORD_TOKEN=discord-placeholder",
                "RWI_DISCORD_APPLICATION_ID=1",
                "RWI_DISCORD_GUILD_ID=2",
                "RWI_OWNER_USER_ID=3",
                "RWI_DATABASE_URL=postgresql+asyncpg://user:password@localhost/database",
                "OPENAI_API_KEY=openai-placeholder",
                "RWI_OFFICIAL_SEARCH_DOMAINS=ubisoft.com, example.com",
                "RWI_OFFICIAL_SEARCH_URLS=https://trello.com/b/example, https://example.com/live",
                "RWI_COMMUNITY_SEARCH_DOMAINS=wikipedia.org, reddit.com",
            )
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.official_search_domains == ("ubisoft.com", "example.com")
    assert settings.official_search_urls == (
        "https://trello.com/b/example",
        "https://example.com/live",
    )
    assert settings.community_search_domains == ("wikipedia.org", "reddit.com")
