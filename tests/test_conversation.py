from __future__ import annotations

from rwi_bot.cogs.conversation import split_discord_message


def test_discord_message_split_preserves_content() -> None:
    text = "alpha " * 800

    chunks = split_discord_message(text, limit=200)

    assert all(len(chunk) <= 200 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()
