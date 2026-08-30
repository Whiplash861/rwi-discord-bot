from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rwi_bot.ai.client import RwiOpenAIClient
from rwi_bot.config import Settings
from rwi_bot.db.repositories import AuditRepository, DisciplineRepository, UsageRepository
from rwi_bot.db.session import Database
from rwi_bot.services.audit import AuditService
from rwi_bot.services.budget import BudgetGuard
from rwi_bot.services.community import CommunityLoadoutRepository
from rwi_bot.services.knowledge import CacheRepository, KnowledgeRepository, TicketRepository
from rwi_bot.services.maintenance import MaintenanceManager
from rwi_bot.services.privacy import ProfileRepository
from rwi_bot.services.qa import QuestionAnsweringService
from rwi_bot.services.releases import ReleaseHistoryRepository


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
    release_history: ReleaseHistoryRepository
    ai: RwiOpenAIClient
    qa: QuestionAnsweringService


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
    release_history = ReleaseHistoryRepository(database)
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
        ai=ai,
        audit=audit,
        web_search_enabled=settings.web_search_enabled,
        current_game_version=settings.current_game_version,
        current_game_version_started_on=settings.current_game_version_started_on,
    )
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
        release_history=release_history,
        ai=ai,
        qa=qa,
    )
