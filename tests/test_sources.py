from __future__ import annotations

import pytest

from rwi_bot.domain.schemas import SourceCitation
from rwi_bot.services.sources import hide_source_links, is_source_request, render_sources


@pytest.mark.parametrize(
    "text",
    (
        "Sources?",
        "What are your sources?",
        "Can I see the citations?",
        "Where did you get that?",
        "Thanks, show me the sources.",
    ),
)
def test_source_only_followups_are_recognized(text: str) -> None:
    assert is_source_request(text) is True


def test_mixed_source_request_is_left_for_normal_answer_path() -> None:
    assert is_source_request("What are your sources, and how do I get Nemesis?") is False


def test_links_are_hidden_from_normal_answer_text() -> None:
    text = (
        "Use the [official guide](https://example.test/guide). "
        "The old note is ([news.example.test](https://news.example.test/old))."
    )

    rendered = hide_source_links(text)

    assert rendered == "Use the official guide. The old note is ."
    assert "https://" not in rendered


def test_cited_domain_labels_are_hidden_from_normal_answer_text() -> None:
    citation = SourceCitation(
        title="Patch notes",
        url="https://news.ubisoft.com/patch",
        source_type="official_web",
        official=True,
    )

    assert hide_source_links("The patch is live. (news.ubisoft.com)", (citation,)) == (
        "The patch is live."
    )


def test_sources_render_only_when_explicitly_requested() -> None:
    citation = SourceCitation(
        title="Known Issues",
        url="https://trello.com/b/F2RU9ia9/the-division-2-known-issues",
        source_type="official_live_service",
        official=True,
    )

    rendered = render_sources((citation,))

    assert "Sources for my previous answer" in rendered
    assert "trello.com" in rendered
    assert "Official" in rendered
