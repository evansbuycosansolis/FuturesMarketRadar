from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import (
    RiskPolicyRead,
    RiskPolicyUpdate,
    RiskSummaryResponse,
    RiskSyncResponse,
    TradeCheckRequest,
    TradeCheckResponse,
    TradePlanRequest,
    TradePlanResponse,
)


router = APIRouter(tags=["risk"])


@router.get("/risk/summary", response_model=RiskSummaryResponse)
def risk_summary(request: Request) -> RiskSummaryResponse:
    risk_service = request.app.state.risk_service
    return risk_service.build_summary()


@router.post("/risk/sync-now", response_model=RiskSyncResponse)
async def risk_sync_now(request: Request) -> RiskSyncResponse:
    risk_service = request.app.state.risk_service
    await risk_service.sync_account_state(force=True, raise_on_rate_limit=True)
    return RiskSyncResponse(ok=True, summary=risk_service.build_summary())


@router.get("/risk/policies", response_model=RiskPolicyRead)
def get_risk_policy(request: Request) -> RiskPolicyRead:
    risk_service = request.app.state.risk_service
    return RiskPolicyRead.model_validate(risk_service.get_policy())


@router.put("/risk/policies", response_model=RiskPolicyRead)
def update_risk_policy(payload: RiskPolicyUpdate, request: Request) -> RiskPolicyRead:
    risk_service = request.app.state.risk_service
    return RiskPolicyRead.model_validate(risk_service.update_policy(payload))


@router.post("/risk/check-trade", response_model=TradeCheckResponse)
def check_trade(payload: TradeCheckRequest, request: Request) -> TradeCheckResponse:
    risk_service = request.app.state.risk_service
    return risk_service.check_trade(payload)


@router.post("/risk/plan-trade", response_model=TradePlanResponse)
def plan_trade(payload: TradePlanRequest, request: Request) -> TradePlanResponse:
    risk_service = request.app.state.risk_service
    return risk_service.plan_trade(payload)
