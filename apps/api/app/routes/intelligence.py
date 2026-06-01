from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import MarketIntelligenceRunResponse, MarketIntelligenceSummaryResponse
from ..services.market_intelligence_service import MarketIntelligenceService


router = APIRouter(tags=["market-intelligence"])


@router.get("/intelligence/summary", response_model=MarketIntelligenceSummaryResponse)
def intelligence_summary(request: Request) -> MarketIntelligenceSummaryResponse:
    service: MarketIntelligenceService = request.app.state.market_intelligence_service
    return service.summary()


@router.post("/intelligence/run-now", response_model=MarketIntelligenceRunResponse)
async def run_intelligence_now(request: Request) -> MarketIntelligenceRunResponse:
    service: MarketIntelligenceService = request.app.state.market_intelligence_service
    run = await service.run_scan(reason="manual")
    summary = service.summary()
    return MarketIntelligenceRunResponse(
        ok=True,
        run=summary.latest_run or service._run_schema(run),
        assets=summary.assets,
        message="Market intelligence sentiment scan completed. Decision support only; no trades were placed.",
    )
