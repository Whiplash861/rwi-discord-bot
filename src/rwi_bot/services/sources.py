from __future__ import annotations

import re
from urllib.parse import urlparse

from rwi_bot.domain.schemas import SourceCitation

_SOURCE_REQUESTS = (
    re.compile(r"(?:sources?|citations?|references?)", re.IGNORECASE),
    re.compile(r"(?:what\s+are\s+)?(?:your|the)?\s*sources?", re.IGNORECASE),
    re.compile(r"(?:show|give|send|list)\s+(?:your|the)?\s*sources?", re.IGNORECASE),
    re.compile(r"(?:show|give|send|list)\s+me\s+(?:your|the)?\s*sources?", re.IGNORECASE),
    re.compile(
        r"(?:can|could|would)\s+(?:i|you)\s+(?:see|share|show|give)\s+"
        r"(?:me\s+)?(?:your|the)?\s*(?:sources?|citations?|references?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"where\s+did\s+you\s+get\s+(?:that|this|the\s+information|the\s+info)", re.IGNORECASE
    ),
    re.compile(r"what\s+did\s+you\s+base\s+that\s+on", re.IGNORECASE),
    re.compile(r"(?:sources?|citations?|references?)\s+(?:please|pls)", re.IGNORECASE),
)

_LEADING_THANKS = re.compile(r"^\s*(?:thanks|thank\s+you)[,!\s-]*", re.IGNORECASE)
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", re.IGNORECASE)
_ANGLE_URL = re.compile(r"<https?://[^>\s]+>", re.IGNORECASE)
_BARE_URL = re.compile(r"https?://[^\s)>]+", re.IGNORECASE)


def is_source_request(text: str) -> bool:
    """Recognize source-only follow-ups that can be answered from conversation memory."""

    clean = _LEADING_THANKS.sub("", " ".join(text.strip().split()))
    clean = clean.strip(" .!?,-")
    return any(pattern.fullmatch(clean) for pattern in _SOURCE_REQUESTS)


def hide_source_links(text: str, citations: tuple[SourceCitation, ...] = ()) -> str:
    """Remove explicit links while preserving useful descriptive link labels."""

    def replace_link(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        hostname = (urlparse(match.group(2)).hostname or "").removeprefix("www.")
        label_key = label.casefold().strip("() ").removeprefix("www.")
        if hostname and (
            label_key == hostname.casefold() or ("." in label_key and " " not in label_key)
        ):
            return ""
        return label

    clean = _MARKDOWN_LINK.sub(replace_link, text)
    clean = _ANGLE_URL.sub("", clean)
    clean = _BARE_URL.sub("", clean)
    for citation in citations:
        hostname = (urlparse(str(citation.url)).hostname or "").removeprefix("www.")
        if hostname:
            clean = re.sub(
                rf"\(?\b(?:www\.)?{re.escape(hostname)}\b\)?",
                "",
                clean,
                flags=re.IGNORECASE,
            )
    clean = re.sub(r"\(\s*\)", "", clean)
    clean = re.sub(r"[ \t]+\n", "\n", clean)
    clean = re.sub(r" {2,}", " ", clean)
    return clean.strip()


def render_sources(citations: tuple[SourceCitation, ...]) -> str:
    if not citations:
        return (
            "I don't have a stored citation for my previous answer. That means I can't "
            "give you a source for it without researching the question again."
        )

    lines = ["Sources for my previous answer:"]
    for citation in citations[:8]:
        label = "Official" if citation.official else _source_label(citation.source_type)
        lines.append(f"- [{citation.title}]({citation.url}) — {label}")
    return "\n".join(lines)


def _source_label(source_type: str) -> str:
    labels = {
        "community_wiki": "Community Wiki",
        "community_reference": "Community Reference",
        "community_forum": "Community / Q&A",
        "community_loadout": "Community Loadout",
        "external_web": "External Web",
        "official_web": "Official",
    }
    return labels.get(source_type, source_type.replace("_", " ").title())
