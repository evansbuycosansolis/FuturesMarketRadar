from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request

from ..schemas import SimulatorAnalyzeRequest, SimulatorAnalyzeResponse
from ..services.binance_futures_client import BinanceFuturesClientError
from ..services.simulator_coach_service import SimulatorCoachService


router = APIRouter(tags=["simulator"])


@router.post("/simulator/analyze", response_model=SimulatorAnalyzeResponse)
async def analyze_simulator_setup(payload: SimulatorAnalyzeRequest, request: Request) -> SimulatorAnalyzeResponse:
    service = SimulatorCoachService(request.app.state.settings)
    try:
        result = await service.analyze(payload)
    except BinanceFuturesClientError as exc:
        raise HTTPException(status_code=502, detail=f"Market candles unavailable for simulator analysis: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:400] if exc.response is not None else str(exc)
        raise HTTPException(status_code=502, detail=f"OpenAI analysis request failed: {detail}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI analysis request failed: {exc}") from exc

    return SimulatorAnalyzeResponse(
        symbol=payload.symbol,
        model=request.app.state.settings.openai_model,
        used_ai=result.used_ai,
        analysis=result.analysis,
        warnings=result.warnings,
    )
