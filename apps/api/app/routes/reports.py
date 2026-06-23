from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select

from ..db import SessionLocal
from .. import models
from ..schemas import ReportHistoryResponse, ReportRead, RunScanResponse
from ..services.report_service import ReportService


router = APIRouter(tags=["reports"])


@router.get("/reports/latest", response_model=ReportRead)
def latest_report(request: Request) -> ReportRead:
    report_service: ReportService = request.app.state.report_service
    with SessionLocal() as db:
        report = db.scalar(select(models.Report).order_by(desc(models.Report.created_at), desc(models.Report.id)))
        if report is None:
            raise HTTPException(status_code=404, detail="No reports are available yet.")
    return report_service.as_report_schema(report)


@router.get("/reports/history", response_model=ReportHistoryResponse)
def report_history(request: Request, limit: int = 20) -> ReportHistoryResponse:
    report_service: ReportService = request.app.state.report_service
    with SessionLocal() as db:
        reports = db.scalars(
            select(models.Report).order_by(desc(models.Report.created_at), desc(models.Report.id)).limit(limit)
        ).all()
    return ReportHistoryResponse(items=[report_service.as_report_schema(report) for report in reports])


@router.post("/scanner/run-now", response_model=RunScanResponse)
async def run_now(request: Request) -> RunScanResponse:
    scanner = request.app.state.scanner
    report_service: ReportService = request.app.state.report_service
    report = await scanner.run_scan(reason="manual", raise_on_rate_limit=True)
    if report is None:
        return RunScanResponse(ok=True, report=None, message="Market snapshots were refreshed, but no scored report was produced.")
    return RunScanResponse(ok=True, report=report_service.as_report_schema(report))
