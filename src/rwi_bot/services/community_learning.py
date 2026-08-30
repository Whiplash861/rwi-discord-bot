from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from rwi_bot.db.models import CommunityClaim, CommunityClaimStatus
from rwi_bot.db.session import Database
from rwi_bot.services.language import normalize_text

REUSABLE_CLAIM_STATUSES = frozenset(
    {CommunityClaimStatus.VERIFIED.value, CommunityClaimStatus.QUALIFIED.value}
)

_SEARCH_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "be",
        "bonus",
        "bonuses",
        "can",
        "could",
        "do",
        "does",
        "for",
        "how",
        "i",
        "in",
        "is",
        "it",
        "know",
        "me",
        "of",
        "on",
        "or",
        "please",
        "set",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "work",
        "works",
        "would",
        "you",
        "your",
    }
)


@dataclass(frozen=True, slots=True)
class CommunityClaimProposal:
    claim_text: str
    risk_flag: str | None = None


@dataclass(frozen=True, slots=True)
class CommunityClaimHit:
    claim: CommunityClaim
    similarity: float


@dataclass(frozen=True, slots=True)
class ClaimReviewDecision:
    status: CommunityClaimStatus
    note: str | None


class ClaimStateConflictError(RuntimeError):
    def __init__(self, actual: str) -> None:
        self.actual = actual
        super().__init__(f"Community claim is already {actual}.")


_ASSERTION = re.compile(
    r"\b(?:i|you|we|it|this|that|which|they|the\s+[a-z0-9'-]+)\s+"
    r"(?:can|cannot|can't|allows?|gives?|grants?|must|requires?|needs?|works?|"
    r"does(?:n't|\s+not)|won't|will\s+not|only\s+works?|has|uses?)\b|"
    r"\b(?:actually|instead|in\s+fact|the\s+fastest\s+way\s+is|"
    r"i\s+(?:tested|confirmed|found|noticed))\b",
    re.IGNORECASE,
)
_QUESTION_ONLY = re.compile(
    r"^\s*(?:can|could|should|would|is|are|does|do|did|will|why|how|what|when|where)\b"
    r"[^.!]*\?\s*$",
    re.IGNORECASE,
)
_RISK = re.compile(r"\b(?:bug|glitch|exploit|cheese|unintended)\b", re.IGNORECASE)
_CLAIM_FOOTER = re.compile(
    r"^Community claim ([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def infer_community_claim(text: str) -> CommunityClaimProposal | None:
    """Find substantial factual follow-ups without deciding whether they are true."""

    clean = " ".join(text.strip().split())
    words = re.findall(r"[a-z0-9][a-z0-9'-]*", clean.casefold())
    if len(clean) < 45 or len(words) < 8:
        return None
    if _QUESTION_ONLY.fullmatch(clean) or _ASSERTION.search(clean) is None:
        return None
    return CommunityClaimProposal(
        claim_text=clean[:2000],
        risk_flag="possible_bug_or_exploit" if _RISK.search(clean) else None,
    )


def infer_claim_review_reply(text: str) -> ClaimReviewDecision | None:
    clean = " ".join(text.strip().split())
    folded = clean.casefold()
    if re.fullmatch(r"yes[.!]?", folded):
        return ClaimReviewDecision(CommunityClaimStatus.VERIFIED, None)
    if match := re.match(r"^yes\s*[,;:-]?\s*(?:but\s+)?(.+)$", clean, re.IGNORECASE):
        note = match.group(1).strip(" .")
        if len(note) >= 8:
            return ClaimReviewDecision(CommunityClaimStatus.QUALIFIED, note)
    if match := re.match(r"^(?:no|incorrect)\s*[,;:-]?\s*(.+)$", clean, re.IGNORECASE):
        note = match.group(1).strip(" .")
        if len(note) < 8:
            return None
        if re.search(r"\bexploit\b", note, re.IGNORECASE):
            status = CommunityClaimStatus.EXPLOIT
        elif re.search(r"\b(?:bug|glitch|unintended)\b", note, re.IGNORECASE):
            status = CommunityClaimStatus.BUG
        else:
            status = CommunityClaimStatus.INCORRECT
        return ClaimReviewDecision(status, note)
    return None


def claim_id_from_footer(text: str | None) -> UUID | None:
    if text is None or (match := _CLAIM_FOOTER.fullmatch(text.strip())) is None:
        return None
    return UUID(match.group(1))


class CommunityClaimRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_pending(
        self,
        *,
        guild_id: int,
        source_channel_id: int,
        source_message_id: int,
        submitter_user_id: int,
        member_label: str,
        source_question: str,
        prior_answer_excerpt: str,
        proposal: CommunityClaimProposal,
        source_url: str,
        game_version: str,
    ) -> CommunityClaim | None:
        clean_label = " ".join(member_label.split())[:80] or "Member"
        clean_question = " ".join(source_question.split())[:1200]
        clean_answer = " ".join(prior_answer_excerpt.split())[:1200]
        clean_claim = " ".join(proposal.claim_text.split())[:2000]
        clean_version = " ".join(game_version.split())[:80]
        if not clean_question or not clean_claim or not clean_version:
            raise ValueError("A community claim needs context, content, and a game version.")
        if not source_url.startswith("https://discord.com/channels/"):
            raise ValueError("A community claim needs a Discord source message.")
        now = datetime.now(UTC)
        claim = CommunityClaim(
            guild_id=guild_id,
            source_channel_id=source_channel_id,
            source_message_id=source_message_id,
            submitter_user_id=submitter_user_id,
            member_label=clean_label,
            source_question=clean_question,
            prior_answer_excerpt=clean_answer,
            claim_text=clean_claim,
            search_text=community_claim_search_text(
                question=clean_question,
                claim=clean_claim,
                qualification=None,
                game_version=clean_version,
            ),
            source_url=source_url,
            game_version=clean_version,
            risk_flag=proposal.risk_flag,
            status=CommunityClaimStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self.database.session() as session:
                session.add(claim)
                await session.flush()
        except IntegrityError:
            return None
        return claim

    async def set_review_message(self, claim_id: UUID, message_id: int) -> None:
        async with self.database.session() as session:
            claim = await session.get(CommunityClaim, claim_id, with_for_update=True)
            if claim is None:
                raise KeyError(f"Community claim {claim_id} does not exist.")
            if claim.status != CommunityClaimStatus.PENDING.value:
                raise ClaimStateConflictError(claim.status)
            claim.review_message_id = message_id

    async def get(self, claim_id: UUID) -> CommunityClaim | None:
        async with self.database.session() as session:
            return await session.get(CommunityClaim, claim_id)

    async def review(
        self,
        claim_id: UUID,
        *,
        status: CommunityClaimStatus,
        reviewer_user_id: int,
        note: str | None,
    ) -> CommunityClaim:
        if status is CommunityClaimStatus.PENDING:
            raise ValueError("A review must resolve the pending claim.")
        clean_note = " ".join((note or "").split())[:2000] or None
        if status is not CommunityClaimStatus.VERIFIED and clean_note is None:
            raise ValueError(
                "Qualified, incorrect, bug, and exploit decisions need an explanation."
            )
        async with self.database.session() as session:
            claim = await session.get(CommunityClaim, claim_id, with_for_update=True)
            if claim is None:
                raise KeyError(f"Community claim {claim_id} does not exist.")
            if claim.status != CommunityClaimStatus.PENDING.value:
                raise ClaimStateConflictError(claim.status)
            claim.status = status.value
            claim.reviewed_by_user_id = reviewer_user_id
            claim.review_note = clean_note
            claim.reviewed_at = datetime.now(UTC)
            claim.search_text = community_claim_search_text(
                question=claim.source_question,
                claim=claim.claim_text,
                qualification=clean_note if status is CommunityClaimStatus.QUALIFIED else None,
                game_version=claim.game_version,
            )
            await session.flush()
            return claim

    async def search(
        self,
        query: str,
        *,
        guild_id: int,
        game_version: str,
        limit: int = 5,
    ) -> list[CommunityClaimHit]:
        if not 1 <= limit <= 10:
            raise ValueError("Community claim search limit must be between 1 and 10.")
        normalized = normalize_text(query)
        if not normalized:
            return []
        similarity = func.word_similarity(normalized, CommunityClaim.search_text)
        statement = (
            select(CommunityClaim, similarity.label("score"))
            .where(CommunityClaim.guild_id == guild_id)
            .where(CommunityClaim.game_version == game_version)
            .where(CommunityClaim.status.in_(REUSABLE_CLAIM_STATUSES))
            .where(similarity >= 0.24)
            .order_by(similarity.desc(), CommunityClaim.reviewed_at.desc().nullslast())
            .limit(min(limit * 4, 40))
        )
        async with self.database.session() as session:
            rows = (await session.execute(statement)).all()
        anchored = [
            CommunityClaimHit(claim=cast(CommunityClaim, row[0]), similarity=float(row[1]))
            for row in rows
            if community_claim_has_query_anchor(
                normalized, cast(CommunityClaim, row[0]).search_text
            )
        ]
        return anchored[:limit]

    async def by_submitter(self, user_id: int) -> list[CommunityClaim]:
        async with self.database.session() as session:
            return list(
                await session.scalars(
                    select(CommunityClaim)
                    .where(CommunityClaim.submitter_user_id == user_id)
                    .order_by(CommunityClaim.created_at.asc())
                )
            )

    async def remove_or_anonymize_by_submitter(self, user_id: int) -> tuple[int, int]:
        async with self.database.session() as session:
            deleted = await session.execute(
                delete(CommunityClaim)
                .where(CommunityClaim.submitter_user_id == user_id)
                .where(CommunityClaim.status == CommunityClaimStatus.PENDING.value)
            )
            anonymized = await session.execute(
                update(CommunityClaim)
                .where(CommunityClaim.submitter_user_id == user_id)
                .values(submitter_user_id=None, member_label="Former member")
            )
            return _rowcount(deleted), _rowcount(anonymized)


def community_claim_search_text(
    *, question: str, claim: str, qualification: str | None, game_version: str
) -> str:
    return normalize_text(" ".join((question, claim, qualification or "", game_version)))


def community_claim_has_query_anchor(query: str, claim_search_text: str) -> bool:
    """Require a meaningful shared term before fuzzy claim retrieval can suppress web search."""

    query_terms = _search_anchor_terms(query)
    if not query_terms:
        return False
    return bool(query_terms & _search_anchor_terms(claim_search_text))


def _search_anchor_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9'-]*", normalize_text(text))
        if len(token) >= 3 and token not in _SEARCH_STOPWORDS
    }


def community_claim_context(hits: list[CommunityClaimHit]) -> str:
    if not hits:
        return ""
    blocks: list[str] = []
    for hit in hits:
        claim = hit.claim
        lines = [
            f"Reviewed community claim ({claim.game_version}, status={claim.status}):",
            f"Claim: {claim.claim_text}",
        ]
        if claim.status == CommunityClaimStatus.QUALIFIED.value and claim.review_note:
            lines.append(f"Controlling reviewer qualification: {claim.review_note}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _rowcount(result: Any) -> int:
    return int(cast(Any, result).rowcount or 0)
