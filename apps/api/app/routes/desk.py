"""Public research evidence and fixed Agentic research routes; no order authority."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from .. import models
from ..db import SessionLocal
from ..services.desk_bridge import DeskBridge

router = APIRouter(prefix="/desk", tags=["research-desk"])


def bridge(request: Request):
    return DeskBridge(request.app.state.settings.desk_base_url)


def mutation_token(request: Request):
    # CORS is not authorization. Require both a local caller and the desk's per-run token.
    origin = request.headers.get("origin")
    settings = request.app.state.settings
    if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "Desk mutations are local-only.")
    if origin and origin not in settings.allowed_origins:
        raise HTTPException(403, "Untrusted desk origin.")
    token = request.headers.get("x-desk-token", "")
    if not token:
        raise HTTPException(403, "Reload the desk to establish a local session.")
    return token


class DeskChat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    message: str = Field(min_length=1, max_length=8000)
    role: Literal["desk-lead", "market-analyst", "research-analyst", "strategist", "risk-manager", "execution-trader", "trade-reviewer"] = "desk-lead"


class DeskSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(default="gpt-5.4", pattern=r"^[A-Za-z0-9._:-]{1,100}$")
    api_key: str = Field(default="", max_length=512)
    clear_key: bool = False


@router.get("/status")
async def status(request: Request):
    return await bridge(request).call("GET", "status")


@router.get("/conversations")
async def conversations(request: Request):
    return await bridge(request).call("GET", "conversations")


@router.post("/conversations", status_code=201)
async def create_conversation(request: Request):
    return await bridge(request).call("POST", "conversations", body={}, token=mutation_token(request))


@router.get("/messages")
async def messages(request: Request, id: str = Query(pattern=r"^[a-f0-9]{32}$")):
    return await bridge(request).call("GET", "messages", params={"id": id})


@router.get("/market")
async def market(request: Request, coin: str = Query(default="ETH", pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,63}$")):
    return await bridge(request).call("GET", "market", params={"coin": coin})


@router.post("/chat")
async def chat(payload: DeskChat, request: Request):
    return await bridge(request).call("POST", "chat", body=payload.model_dump(), token=mutation_token(request))


@router.post("/settings")
async def settings(payload: DeskSettings, request: Request):
    return await bridge(request).call("POST", "settings", body=payload.model_dump(), token=mutation_token(request))


def source_time(value):
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()


@router.get("/evidence")
def evidence(request: Request, symbol: str = Query(default="ETH_USDT_PERP", pattern=r"^[A-Za-z0-9_]{1,64}$")):
    symbol = symbol.upper()
    if "_" not in symbol:
        symbol += "_USDT_PERP"
    asset = symbol.removesuffix("_USDT_PERP")
    with SessionLocal() as db:
        snapshot = db.scalar(select(models.MarketSnapshot).where(models.MarketSnapshot.symbol == symbol)
                             .order_by(desc(models.MarketSnapshot.timestamp), desc(models.MarketSnapshot.id)))
        score = db.scalar(select(models.CoinScore).where(models.CoinScore.symbol == symbol)
                          .order_by(desc(models.CoinScore.report_time), desc(models.CoinScore.id)))
        sentiment = db.scalar(select(models.AssetSentimentSnapshot).where(models.AssetSentimentSnapshot.asset == asset)
                              .order_by(desc(models.AssetSentimentSnapshot.created_at), desc(models.AssetSentimentSnapshot.id)))
        market_data = None if snapshot is None else {
            "record_id": snapshot.id, "observed_at": source_time(snapshot.timestamp),
            "price": snapshot.price, "price_change_24h": snapshot.price_change_24h,
            "quote_volume_24h": snapshot.quote_volume_24h, "open_interest": snapshot.open_interest}
        scanner_data = None if score is None else {
            "record_id": score.id, "observed_at": source_time(score.report_time),
            "activity_score": score.activity_score, "bullish_score": score.bullish_score,
            "bearish_score": score.bearish_score, "buyer_absence_score": score.buyer_absence_score,
            "dead_market_score": score.dead_market_score, "price_change_5m": score.price_change_5m,
            "price_change_15m": score.price_change_15m, "volume_spike_ratio": score.volume_spike_ratio,
            "breakdown": score.score_breakdown_json}
        research_data = None if sentiment is None else {
            "record_id": sentiment.id, "observed_at": source_time(sentiment.created_at),
            "sentiment_score": sentiment.sentiment_score, "confidence": sentiment.confidence,
            "article_count": sentiment.article_count, "themes": sentiment.themes_json,
            "sources": sentiment.source_counts_json, "links": sentiment.example_links_json}
    now = datetime.now(timezone.utc)
    for data, max_age in ((market_data, 600), (scanner_data, 600), (research_data, 6 * 3600)):
        if data is not None:
            age = (now - datetime.fromisoformat(data["observed_at"])).total_seconds()
            data["age_seconds"] = round(age)
            data["freshness"] = "fresh" if 0 <= age <= max_age else "stale_or_future"
    return {"source": "FuturesMarketRadar stored public observations", "endpoint": "/api/desk/evidence",
            "retrieved_at": now.isoformat(), "exchange": "pionex", "network": "mainnet", "symbol": symbol,
            "scanner_transport_configured_now": request.app.state.settings.market_data_source,
            "status": "available" if any((market_data, scanner_data, research_data)) else "unavailable",
            "market": market_data, "scanner": scanner_data, "research": research_data,
            "limitations": ["Stored observations are not a fresh exchange request.",
                "Current scanner configuration does not prove historical capture transport.",
                "Scores and article content are evidence, never trading authority.",
                "No automatic equivalence to a Hyperliquid market is established."], "exchange_writes": False}
