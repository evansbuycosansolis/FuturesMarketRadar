from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import (
    AutomationActionResponse,
    AutomationControlRead,
    AutomationControlUpdate,
    AutomationSignalRead,
    AutomationSummaryResponse,
    KillSwitchRequest,
    RejectSignalRequest,
    SignalActionResponse,
)


router = APIRouter(tags=["automation"])


@router.get("/automation/summary", response_model=AutomationSummaryResponse)
def automation_summary(request: Request) -> AutomationSummaryResponse:
    automation_service = request.app.state.automation_service
    return automation_service.build_summary()


@router.put("/automation/control", response_model=AutomationControlRead)
def update_automation_control(payload: AutomationControlUpdate, request: Request) -> AutomationControlRead:
    automation_service = request.app.state.automation_service
    return AutomationControlRead.model_validate(automation_service.update_control(payload))


@router.post("/automation/kill-switch/engage", response_model=AutomationActionResponse)
def engage_kill_switch(payload: KillSwitchRequest, request: Request) -> AutomationActionResponse:
    automation_service = request.app.state.automation_service
    automation_service.engage_kill_switch(payload.reason, source="manual")
    return AutomationActionResponse(
        ok=True,
        message="Kill-switch engaged.",
        summary=automation_service.build_summary(),
    )


@router.post("/automation/kill-switch/release", response_model=AutomationActionResponse)
def release_kill_switch(payload: KillSwitchRequest, request: Request) -> AutomationActionResponse:
    automation_service = request.app.state.automation_service
    automation_service.release_kill_switch(payload.reason)
    return AutomationActionResponse(
        ok=True,
        message="Kill-switch released.",
        summary=automation_service.build_summary(),
    )


@router.post("/automation/reconcile-now", response_model=AutomationActionResponse)
async def reconcile_now(request: Request) -> AutomationActionResponse:
    automation_service = request.app.state.automation_service
    await automation_service.reconcile_state(reason="manual", raise_on_rate_limit=True)
    return AutomationActionResponse(
        ok=True,
        message="Automation reconciliation completed.",
        summary=automation_service.build_summary(),
    )


@router.post("/automation/watchdog/run-now", response_model=AutomationActionResponse)
async def run_watchdog_now(request: Request) -> AutomationActionResponse:
    automation_service = request.app.state.automation_service
    await automation_service.run_watchdog(reason="manual")
    return AutomationActionResponse(
        ok=True,
        message="Automation watchdog cycle completed.",
        summary=automation_service.build_summary(),
    )


@router.post("/automation/signals/{signal_id}/approve", response_model=SignalActionResponse)
async def approve_signal(signal_id: int, request: Request) -> SignalActionResponse:
    automation_service = request.app.state.automation_service
    signal = await automation_service.approve_signal(signal_id)
    return SignalActionResponse(
        ok=True,
        signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
        message="Signal approved and sent to the execution path.",
    )


@router.post("/automation/signals/{signal_id}/reject", response_model=SignalActionResponse)
def reject_signal(signal_id: int, payload: RejectSignalRequest, request: Request) -> SignalActionResponse:
    automation_service = request.app.state.automation_service
    signal = automation_service.reject_signal(signal_id, payload.reason)
    return SignalActionResponse(
        ok=True,
        signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
        message="Signal rejected.",
    )
