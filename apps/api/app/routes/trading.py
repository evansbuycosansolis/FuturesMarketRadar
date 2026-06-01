from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import (
    ArmManagedExitRequest,
    ArmManagedExitResponse,
    CancelAllOrdersRequest,
    CancelAllOrdersResponse,
    DisarmManagedExitResponse,
    ExecutionOrderRequest,
    OrderExecutionResponse,
    RunExitAutomationResponse,
)
from ..services.exit_automation_service import model_to_managed_exit_schema


router = APIRouter(tags=["trading"])


@router.post("/trading/order", response_model=OrderExecutionResponse)
async def place_order(payload: ExecutionOrderRequest, request: Request) -> OrderExecutionResponse:
    risk_service = request.app.state.risk_service
    return await risk_service.execute_order(payload)


@router.post("/trading/cancel-all", response_model=CancelAllOrdersResponse)
async def cancel_all_orders(payload: CancelAllOrdersRequest, request: Request) -> CancelAllOrdersResponse:
    risk_service = request.app.state.risk_service
    await risk_service.cancel_all_orders(payload)
    return CancelAllOrdersResponse(ok=True, symbol=payload.symbol, message=f"Cancel-all submitted for {payload.symbol}.")


@router.post("/trading/managed-exits/arm", response_model=ArmManagedExitResponse)
async def arm_managed_exit(payload: ArmManagedExitRequest, request: Request) -> ArmManagedExitResponse:
    exit_service = request.app.state.exit_automation_service
    plan = await exit_service.arm_existing_position(payload)
    return ArmManagedExitResponse(
        ok=True,
        plan=model_to_managed_exit_schema(plan),
        message=f"Managed exit automation armed for {plan.symbol}.",
    )


@router.post("/trading/managed-exits/{plan_id}/disarm", response_model=DisarmManagedExitResponse)
async def disarm_managed_exit(plan_id: int, request: Request) -> DisarmManagedExitResponse:
    exit_service = request.app.state.exit_automation_service
    plan = exit_service.disarm_plan(plan_id)
    return DisarmManagedExitResponse(
        ok=True,
        plan=model_to_managed_exit_schema(plan),
        message=f"Managed exit automation disarmed for {plan.symbol}.",
    )


@router.post("/trading/managed-exits/run-now", response_model=RunExitAutomationResponse)
async def run_exit_engine_now(request: Request) -> RunExitAutomationResponse:
    exit_service = request.app.state.exit_automation_service
    result = await exit_service.run_once(reason="manual")
    return RunExitAutomationResponse(
        ok=True,
        plans_checked=result.plans_checked,
        triggered=result.triggered,
        message="Managed exit engine cycle completed.",
    )
