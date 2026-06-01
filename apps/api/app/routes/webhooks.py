from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, Request

from ..schemas import TradingViewWebhookResponse


router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/tradingview", response_model=TradingViewWebhookResponse)
async def tradingview_webhook(
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
    x_fmr_webhook_secret: str | None = Header(default=None, alias="X-FMR-Webhook-Secret"),
) -> TradingViewWebhookResponse:
    automation_service = request.app.state.automation_service
    return await automation_service.handle_tradingview_webhook(
        payload,
        header_secret=x_fmr_webhook_secret,
    )
