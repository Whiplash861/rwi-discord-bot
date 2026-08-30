from __future__ import annotations

from typing import cast

from rwi_bot.ai.client import RwiOpenAIClient, WebSearchScope, classify_external_source


def test_curated_search_combines_official_live_and_community_domains() -> None:
    client = cast(RwiOpenAIClient, object.__new__(RwiOpenAIClient))
    client.official_domains = ("ubisoft.com",)
    client.official_urls = ("https://trello.com/b/F2RU9ia9/the-division-2-known-issues",)
    client.community_domains = ("wikipedia.org", "reddit.com", "ubisoft.com")

    assert client._search_domains(WebSearchScope.CURATED) == (
        "ubisoft.com",
        "trello.com",
        "wikipedia.org",
        "reddit.com",
    )
    assert client._search_domains(WebSearchScope.OPEN) == ()


def test_external_source_trust_is_classified_by_exact_target() -> None:
    arguments = {
        "official_domains": ("ubisoft.com",),
        "official_urls": ("https://trello.com/b/F2RU9ia9/the-division-2-known-issues",),
        "community_domains": (
            "wikipedia.org",
            "thedivision.fandom.com",
            "reddit.com",
            "gaming.stackexchange.com",
        ),
    }

    assert classify_external_source("https://news.ubisoft.com/test", **arguments) == (
        "official_web",
        True,
    )
    assert classify_external_source(
        "https://trello.com/b/F2RU9ia9/the-division-2-known-issues?filter=open",
        **arguments,
    ) == ("official_live_service", True)
    assert classify_external_source("https://trello.com/b/not-official/other", **arguments) == (
        "external_web",
        False,
    )
    assert classify_external_source("https://en.wikipedia.org/wiki/Test", **arguments) == (
        "community_wiki",
        False,
    )
    assert classify_external_source("https://www.reddit.com/r/thedivision/", **arguments) == (
        "community_forum",
        False,
    )
