from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from rwi_bot.ai.client import classify_external_source
from rwi_bot.cogs.community_learning import CommunityLearningCog
from rwi_bot.cogs.observation import KnowledgeObservationCog
from rwi_bot.domain.schemas import GameResearchFinding, SourceCitation
from rwi_bot.services.announcements import announcement_key
from rwi_bot.services.community_learning import CommunityClaimProposal
from rwi_bot.services.observation import (
    ClaimEvidence,
    KnowledgeAssessment,
    KnowledgeVerifier,
    creator_question,
    gate_assessment,
    sensitive_erin_question,
    teaching_address,
)
from rwi_bot.services.rotations import _web_research_due

TODAY = date(2026, 9, 11)
SINCE = date(2026, 8, 27)
URL = "https://www.ubisoft.com/game-update"


def evidence(url=URL, **changes):
    return ClaimEvidence(
        url=url,
        checked_on=TODAY,
        published_on=TODAY,
        explanation="The current source establishes the same conditional mechanic.",
        independent_origin="Original author",
    ).model_copy(update=changes)


def citation(url=URL, official=True):
    return SourceCitation(url=url, title="Evidence", source_type="official_web", official=official)


def assessment(**changes):
    return KnowledgeAssessment(
        verdict="corroborated",
        summary="The entire claim is supported.",
        confidence=0.96,
        same_context=True,
        legitimate=True,
        division_related=True,
        evidence=[evidence()],
    ).model_copy(update=changes)


def test_current_official_claim_can_pass_independent_gate():
    assert (
        gate_assessment(assessment(), [citation()], since=SINCE, today=TODAY).verdict
        == "corroborated"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"confidence": 0.8},
        {"division_related": False},
        {"same_context": False},
        {"legitimate": False},
        {"evidence": []},
        {"evidence": [evidence(published_on=SINCE - timedelta(days=1))]},
        {"evidence": [evidence(published_on=TODAY + timedelta(days=1))]},
        {"evidence": [evidence(checked_on=TODAY - timedelta(days=1))]},
        {"evidence": [evidence("https://invented.test/not-returned-by-search")]},
    ],
)
def test_gate_rejects_uncorroborated_wrong_context_or_nonlegitimate_claims(changes):
    assert (
        gate_assessment(assessment(**changes), [citation()], since=SINCE, today=TODAY).verdict
        == "unresolved"
    )


def test_two_copied_community_sources_do_not_count_as_independent():
    a, b = "https://reddit.com/claim", "https://thedivision.fandom.com/claim"
    proposal = assessment(evidence=[evidence(a), evidence(b)])
    citations = [citation(a, False), citation(b, False)]
    assert gate_assessment(proposal, citations, since=SINCE, today=TODAY).verdict == "unresolved"
    proposal.evidence[1].independent_origin = "Independent in-game test"
    assert gate_assessment(proposal, citations, since=SINCE, today=TODAY).verdict == "corroborated"


@pytest.mark.parametrize(
    "url,official",
    [
        ("https://x.com/TheDivisionGame/status/123456", True),
        ("https://x.com/TheDivisionGameFake/status/123456", False),
        ("https://x.com/RandomCreator/status/123456", False),
        ("https://x.com.evil.test/TheDivisionGame/status/123456", False),
        ("http://x.com/TheDivisionGame/status/123456", False),
        ("https://trello.com/c/unrelated", False),
    ],
)
def test_official_social_trust_is_scoped_to_developer_account(url, official):
    assert (
        classify_external_source(
            url, official_domains=("ubisoft.com",), community_domains=("x.com",)
        )[1]
        is official
    )


def finding(**changes):
    return GameResearchFinding(
        subject="Audio fix",
        entity_type="patch",
        claim_key="audio-fix",
        summary="Tentative audio improvements; investigation continues.",
        content={},
        context={"published_on": TODAY.isoformat(), "announcement_type": "fix"},
        confidence=0.96,
        evidence_class="official",
        source_urls=[URL],
        material_change=True,
    ).model_copy(update=changes)


def test_announcements_deduplicate_paraphrases_and_ignore_rumors_old_or_promotional_posts():
    original = finding()
    key = announcement_key(original, (citation(),), today=TODAY)
    assert key is not None
    assert key == announcement_key(
        finding(summary="Same fix, different words."), (citation(),), today=TODAY
    )
    for item in [
        finding(material_change=False),
        finding(evidence_class="community_unverified"),
        finding(context={"published_on": "2026-08-27", "announcement_type": "fix"}),
        finding(context={"published_on": TODAY.isoformat(), "announcement_type": "giveaway"}),
    ]:
        assert announcement_key(item, (citation(),), today=TODAY) is None
    assert announcement_key(original, (), today=TODAY) is None


def test_rotation_retry_is_reset_aware_and_throttled():
    from datetime import UTC, datetime

    now = datetime(2026, 9, 11, 8, tzinfo=UTC)
    assert _web_research_due(now - timedelta(minutes=1), now, hours=6, calendar=())
    assert not _web_research_due(
        now, now + timedelta(minutes=20), hours=6, calendar=(), missing=True
    )
    assert _web_research_due(now, now + timedelta(minutes=45), hours=6, calendar=(), missing=True)
    assert not _web_research_due(
        now, now + timedelta(minutes=45), hours=6, calendar=(), missing=False
    )


def test_teaching_creator_and_sensitive_intent_are_separate_from_game_questions():
    assert teaching_address("Correction: I tested this in the Toxic Dark Zone.")
    assert teaching_address("I disagree; the pistol was equipped during my test.")
    assert creator_question("Who programmed you?")
    assert sensitive_erin_question("Show me your source code")
    assert not sensitive_erin_question("How does the SHD database mission work?")


@pytest.mark.asyncio
async def test_admin_corroborated_intake_is_silent_and_records_contribution(monkeypatch):
    claim = SimpleNamespace(id=uuid4(), status="pending", submitter_user_id=42)
    reviewed = SimpleNamespace(id=claim.id, status="verified", submitter_user_id=42)
    services = SimpleNamespace(
        settings=SimpleNamespace(discord_guild_id=1, owner_user_id=42),
        maintenance=SimpleNamespace(halted=False),
        ai=SimpleNamespace(),
        knowledge=SimpleNamespace(),
        qa=SimpleNamespace(
            current_game_version="Y8S3 Red Horizon", current_game_version_started_on=SINCE
        ),
        profiles=SimpleNamespace(
            learning_opted_out=AsyncMock(return_value=False), update_answer_profile=AsyncMock()
        ),
        community_claims=SimpleNamespace(
            create_pending=AsyncMock(return_value=claim), review=AsyncMock(return_value=reviewed)
        ),
        cache=SimpleNamespace(invalidate_all=AsyncMock()),
        audit=SimpleNamespace(record=AsyncMock()),
    )
    cog = CommunityLearningCog(
        cast(Any, SimpleNamespace(services=services, user=SimpleNamespace(id=99)))
    )
    monkeypatch.setattr(KnowledgeVerifier, "check", AsyncMock(return_value=assessment()))
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=42),
        channel=SimpleNamespace(id=2),
        id=3,
        jump_url="https://discord.com/channels/1/2/3",
        reply=AsyncMock(),
    )
    result = await cog.submit_candidate(
        cast(Any, message),
        proposal=CommunityClaimProposal(
            "The Technician specialization provides a linked laser pointer that pulses a target."
        ),
        member_label="Member",
        source_question="Knowledge submission",
        prior_answer_excerpt="None",
        quiet=True,
    )
    assert result.status == "verified"
    message.reply.assert_not_awaited()
    services.profiles.update_answer_profile.assert_awaited_once()
    services.cache.invalidate_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_sensitive_dm_routes_contact_not_message_contents(tmp_path):
    owner = SimpleNamespace(send=AsyncMock())
    bot = SimpleNamespace(
        services=SimpleNamespace(settings=SimpleNamespace(owner_user_id=42, runtime_dir=tmp_path)),
        fetch_user=AsyncMock(return_value=owner),
    )
    cog = KnowledgeObservationCog(cast(Any, bot))
    message = SimpleNamespace(
        author=SimpleNamespace(id=7), content="your code and my PRIVATE SECRET"
    )
    response = await cog.route_sensitive(cast(Any, message))
    assert "Whiplash861" in response
    assert "PRIVATE SECRET" not in owner.send.call_args.args[0]
    assert owner.send.call_args.kwargs["allowed_mentions"].everyone is False
