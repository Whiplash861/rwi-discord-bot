from __future__ import annotations

import hashlib
from datetime import date, timedelta

from rwi_bot.domain.schemas import GameResearchFinding, SourceCitation

IMPORTANT_ANNOUNCEMENTS = frozenset(
    {"patch", "maintenance", "outage", "fix", "balance", "season", "dlc"}
)


def announcement_key(
    finding: GameResearchFinding, citations: tuple[SourceCitation, ...], *, today: date
) -> str | None:
    if (
        not finding.material_change
        or finding.evidence_class != "official"
        or finding.confidence < 0.9
        or finding.context.get("announcement_type") not in IMPORTANT_ANNOUNCEMENTS
    ):
        return None
    try:
        published = date.fromisoformat(str(finding.context.get("published_on", "")))
    except ValueError:
        return None
    if not today - timedelta(days=7) <= published <= today:
        return None
    official = {str(c.url).rstrip("/") for c in citations if c.official}
    sources = sorted({str(url).rstrip("/") for url in finding.source_urls})
    if not sources or any(url not in official for url in sources):
        return None
    # Stable across summary paraphrases; same post/card can announce a later dated change.
    return hashlib.sha256(
        f"{sources}:{published}:{finding.context['announcement_type']}".encode()
    ).hexdigest()[:24]
