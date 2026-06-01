from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routes import automation, copilot, exchanges, health, intelligence, market, reports, risk, trading, webhooks
from .services.automation_service import AutomationService
from .services.ai_report_agent import AiReportAgent
from .services.exit_automation_service import ExitAutomationService
from .services.market_intelligence_service import MarketIntelligenceService
from .services.pionex_client import PionexClient
from .services.pionex_stream_service import PionexStreamService
from .services.private_pionex_client import PrivatePionexClient
from .services.report_service import ReportService
from .services.risk_policy_service import RiskPolicyService
from .services.risk_service import RiskService
from .services.scanner import RadarScanner


settings = get_settings()
logger = logging.getLogger(__name__)


def _spawn_background_task(coro, *, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)

    def _log_result(completed_task: asyncio.Task) -> None:
        with suppress(asyncio.CancelledError):
            exc = completed_task.exception()
            if exc is not None:
                logger.exception("Background task %s failed", completed_task.get_name(), exc_info=exc)

    task.add_done_callback(_log_result)
    return task


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    pionex_client = PionexClient(settings)
    private_pionex_client = PrivatePionexClient(settings)
    scanner = RadarScanner(settings, pionex_client)
    report_service = ReportService(settings, AiReportAgent(settings))
    market_intelligence_service = MarketIntelligenceService(settings)
    risk_policy_service = RiskPolicyService(settings)
    risk_service = RiskService(settings, private_pionex_client, risk_policy_service)
    exit_automation_service = ExitAutomationService(settings, private_pionex_client)
    stream_service = PionexStreamService(settings, private_pionex_client)
    automation_service = AutomationService(settings, private_pionex_client)
    risk_service.set_exit_automation_service(exit_automation_service)
    risk_service.set_automation_service(automation_service)
    automation_service.set_risk_service(risk_service)
    automation_service.set_exit_automation_service(exit_automation_service)
    automation_service.set_stream_service(stream_service)
    stream_service.set_exit_automation_service(exit_automation_service)
    scheduler = AsyncIOScheduler(timezone=settings.report_timezone)
    scheduler.add_job(
        scanner.run_scan,
        "interval",
        minutes=settings.scan_interval_minutes,
        kwargs={"reason": "scheduled"},
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    if settings.enable_private_api and settings.private_api_configured:
        scheduler.add_job(
            risk_service.sync_account_state,
            "interval",
            minutes=settings.risk_sync_interval_minutes,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30,
        )
    if settings.enable_exit_automation and settings.enable_private_api and settings.private_api_configured:
        scheduler.add_job(
            exit_automation_service.run_once,
            "interval",
            seconds=settings.exit_automation_poll_seconds,
            kwargs={"reason": "scheduled"},
            max_instances=1,
            coalesce=True,
            misfire_grace_time=max(settings.exit_automation_poll_seconds, 5),
        )
    scheduler.add_job(
        automation_service.run_watchdog,
        "interval",
        seconds=settings.automation_watchdog_interval_seconds,
        kwargs={"reason": "scheduled"},
        max_instances=1,
        coalesce=True,
        misfire_grace_time=max(settings.automation_watchdog_interval_seconds, 5),
    )
    if settings.enable_market_intelligence:
        scheduler.add_job(
            market_intelligence_service.run_scan,
            "interval",
            minutes=settings.market_intelligence_interval_minutes,
            kwargs={"reason": "scheduled"},
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
    if settings.enable_private_api and settings.private_api_configured:
        scheduler.add_job(
            automation_service.reconcile_state,
            "interval",
            seconds=settings.automation_reconcile_interval_seconds,
            kwargs={"reason": "scheduled"},
            max_instances=1,
            coalesce=True,
            misfire_grace_time=max(settings.automation_reconcile_interval_seconds, 5),
        )
    scheduler.start()
    await stream_service.start()

    app.state.pionex_client = pionex_client
    app.state.private_pionex_client = private_pionex_client
    app.state.settings = settings
    app.state.scanner = scanner
    app.state.scheduler = scheduler
    app.state.report_service = report_service
    app.state.market_intelligence_service = market_intelligence_service
    app.state.risk_policy_service = risk_policy_service
    app.state.risk_service = risk_service
    app.state.exit_automation_service = exit_automation_service
    app.state.stream_service = stream_service
    app.state.automation_service = automation_service

    if settings.run_initial_scan:
        _spawn_background_task(scanner.run_scan(reason="startup"), name="startup-scan")
    if settings.enable_market_intelligence and settings.run_initial_market_intelligence:
        _spawn_background_task(market_intelligence_service.run_scan(reason="startup"), name="startup-market-intelligence")
    if settings.enable_private_api and settings.private_api_configured:
        _spawn_background_task(risk_service.sync_account_state(), name="startup-risk-sync")
    if settings.enable_exit_automation and settings.enable_private_api and settings.private_api_configured:
        _spawn_background_task(exit_automation_service.run_once(reason="startup"), name="startup-exit-automation")
    _spawn_background_task(automation_service.reconcile_state(reason="startup"), name="startup-reconcile")
    _spawn_background_task(automation_service.run_watchdog(reason="startup"), name="startup-watchdog")

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await stream_service.stop()
        await private_pionex_client.close()
        await pionex_client.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(copilot.router, prefix=settings.api_prefix)
app.include_router(exchanges.router, prefix=settings.api_prefix)
app.include_router(intelligence.router, prefix=settings.api_prefix)
app.include_router(market.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(risk.router, prefix=settings.api_prefix)
app.include_router(trading.router, prefix=settings.api_prefix)
app.include_router(automation.router, prefix=settings.api_prefix)
app.include_router(webhooks.router, prefix=settings.api_prefix)
