from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from ..db import SessionLocal
from .. import models
from ..schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(request: Request) -> HealthResponse:
    scanner = request.app.state.scanner
    scheduler = request.app.state.scheduler
    automation_service = request.app.state.automation_service

    with SessionLocal() as db:
        latest_report_at = db.scalar(select(func.max(models.Report.created_at)))
        tracked_symbol_count = db.scalar(select(func.count(models.Symbol.id))) or 0
        control = automation_service.ensure_control(db)

    return HealthResponse(
        status="ok",
        scheduler_running=bool(getattr(scheduler, "running", False)),
        scanner_running=scanner.status.running,
        last_run_started_at=scanner.status.last_run_started_at,
        last_run_completed_at=scanner.status.last_run_completed_at,
        last_error=scanner.status.last_error,
        latest_report_at=latest_report_at,
        tracked_symbol_count=int(tracked_symbol_count),
        automation_mode=control.mode,
        kill_switch_enabled=control.kill_switch_enabled,
        watchdog_last_run_at=control.last_watchdog_at,
        last_private_stream_event_at=control.last_private_stream_event_at,
        last_public_stream_event_at=control.last_public_stream_event_at,
    )
