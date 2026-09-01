from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rwi_bot.ai.client import RwiOpenAIClient
from rwi_bot.config import Settings
from rwi_bot.db.repositories import AuditRepository, DisciplineRepository, UsageRepository
from rwi_bot.db.session import Database
from rwi_bot.services.audit import AuditService
from rwi_bot.services.autonomous_research import (
    AutonomousResearchService,
    AutonomyStateStore,
)
from rwi_bot.services.budget import BudgetGuard
from rwi_bot.services.community import CommunityLoadoutRepository
from rwi_bot.services.community_learning import CommunityClaimRepository
from rwi_bot.services.knowledge import CacheRepository, KnowledgeRepository, TicketRepository
from rwi_bot.services.maintenance import MaintenanceManager
from rwi_bot.services.operations import OperationRepository
from rwi_bot.services.privacy import ProfileRepository
from rwi_bot.services.qa import QuestionAnsweringService
from rwi_bot.services.reference_catalog import Division2ReferenceCatalog
from rwi_bot.services.releases import ReleaseHistoryRepository
from rwi_bot.services.seeding import apply_red_horizon_seed
from rwi_bot.services.video_inspection import VideoInspectionService


@dataclass(slots=True)
class AppServices:
    settings: Settings
    database: Database
    maintenance: MaintenanceManager
    audit: AuditService
    usage: UsageRepository
    budget: BudgetGuard
    knowledge: KnowledgeRepository
    cache: CacheRepository
    tickets: TicketRepository
    discipline: DisciplineRepository
    profiles: ProfileRepository
    community_loadouts: CommunityLoadoutRepository
    community_claims: CommunityClaimRepository
    reference_catalog: Division2ReferenceCatalog
    release_history: ReleaseHistoryRepository
    operations: OperationRepository
    ai: RwiOpenAIClient
    qa: QuestionAnsweringService
    video_inspection: VideoInspectionService
    autonomous_research: AutonomousResearchService


async def build_services(settings: Settings) -> AppServices:
    database = Database(settings.database_url.get_secret_value())
    maintenance = MaintenanceManager(settings.runtime_dir)
    await maintenance.load()

    audit_repository = AuditRepository(database)
    usage = UsageRepository(database)
    audit = AuditService(audit_repository)
    budget = BudgetGuard(
        usage,
        hard_limit=Decimal(str(settings.openai_hard_budget_usd)),
        member_reserve=Decimal(str(settings.member_reserve_usd)),
    )
    knowledge = KnowledgeRepository(database)
    cache = CacheRepository(database)
    tickets = TicketRepository(database)
    discipline = DisciplineRepository(database)
    profiles = ProfileRepository(database)
    community_loadouts = CommunityLoadoutRepository(database)
    community_claims = CommunityClaimRepository(database)
    reference_catalog = Division2ReferenceCatalog.packaged()
    release_history = ReleaseHistoryRepository(database)
    operations = OperationRepository(database)
    await apply_red_horizon_seed(knowledge, actor_id=settings.owner_user_id)
    ai = RwiOpenAIClient(
        api_key=settings.openai_api_key.get_secret_value(),
        maintenance=maintenance,
        budget=budget,
        usage_repository=usage,
        normal_model=settings.model_normal,
        complex_model=settings.model_complex,
        economy_model=settings.model_economy,
        official_domains=settings.official_search_domains,
        official_urls=settings.official_search_urls,
        community_domains=settings.community_search_domains,
    )
    qa = QuestionAnsweringService(
        maintenance=maintenance,
        knowledge=knowledge,
        cache=cache,
        tickets=tickets,
        profiles=profiles,
        community_loadouts=community_loadouts,
        community_claims=community_claims,
        reference_catalog=reference_catalog,
        ai=ai,
        audit=audit,
        web_search_enabled=settings.web_search_enabled,
        current_game_version=settings.current_game_version,
        current_game_version_started_on=settings.current_game_version_started_on,
    )
    video_inspection = VideoInspectionService(
        ai=ai,
        audit=audit,
        enabled=settings.video_inspection_enabled,
        maximum_duration_seconds=settings.video_max_duration_seconds,
        maximum_bytes=settings.video_max_bytes,
        sample_frames=settings.video_sample_frames,
        ffmpeg_binary=settings.ffmpeg_binary,
        ffprobe_binary=settings.ffprobe_binary,
    )
    autonomous_research = AutonomousResearchService(
        ai=ai,
        knowledge=knowledge,
        cache=cache,
        qa=qa,
        audit=audit,
        state_store=AutonomyStateStore(
            settings.runtime_dir / "autonomy-state.json",
            initial_game_version=settings.current_game_version,
            initial_started_on=settings.current_game_version_started_on,
        ),
        owner_user_id=settings.owner_user_id,
        enabled=settings.autonomous_research_enabled,
        full_sweep_hours=settings.autonomous_full_sweep_hours,
        maximum_findings=settings.autonomous_max_findings_per_run,
        auto_promote_official=settings.autonomous_auto_promote_official,
    )
    await autonomous_research.initialize()
    return AppServices(
        settings=settings,
        database=database,
        maintenance=maintenance,
        audit=audit,
        usage=usage,
        budget=budget,
        knowledge=knowledge,
        cache=cache,
        tickets=tickets,
        discipline=discipline,
        profiles=profiles,
        community_loadouts=community_loadouts,
        community_claims=community_claims,
        reference_catalog=reference_catalog,
        release_history=release_history,
        operations=operations,
        ai=ai,
        qa=qa,
        video_inspection=video_inspection,
        autonomous_research=autonomous_research,
    )
