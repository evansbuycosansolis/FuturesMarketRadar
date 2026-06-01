from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, Request
from sqlalchemy import desc, select

from .. import models
from ..db import SessionLocal
from ..schemas import (
    AutomationSignalRead,
    CopilotSignalRead,
    CopilotLogRead,
    CopilotOverviewResponse,
    ManualSignalRequest,
    PaperCloseRequest,
    PaperOrderRequest,
    PaperSummaryResponse,
    PaperTradeResponse,
    SignalHeatmapResponse,
    SignalHeatmapRowRead,
    TradingViewWebhookResponse,
)
from ..services.paper_trading_service import PaperTradingService
from ..services.signal_engine import SignalEngine


router = APIRouter(tags=["copilot"])

DEFAULT_SYMBOLS = ["BTC_USDT_PERP", "ETH_USDT_PERP", "XRP_USDT_PERP", "SOL_USDT_PERP", "DOGE_USDT_PERP", "BNB_USDT_PERP"]
TIMEFRAME_MAP = {
    "1m": "1M",
    "5m": "5M",
    "15m": "15M",
    "1h": "60M",
    "4h": "4H",
    "1d": "1D",
}


def _fallback_signal(symbol: str, timeframe: str, reason: str) -> CopilotSignalRead:
    with SessionLocal() as db:
        latest_time = db.scalar(select(models.CoinScore.report_time).order_by(desc(models.CoinScore.report_time)))
        score = None
        if latest_time is not None:
            score = db.scalar(
                select(models.CoinScore)
                .where(models.CoinScore.symbol == symbol)
                .where(models.CoinScore.report_time == latest_time)
            )

    if score is None:
        return CopilotSignalRead(
            symbol=symbol,
            timeframe=timeframe,
            direction="NEUTRAL",
            confidence=0.0,
            reasons=[f"Live Pionex data unavailable and no stored scanner score exists: {reason}"],
            invalidation_level=None,
            suggested_stop_loss=None,
            suggested_take_profit=None,
            risk_reward_ratio=None,
            indicators=[],
        )

    if score.bullish_score >= score.bearish_score and score.bullish_score >= 55:
        direction = "LONG"
        confidence = score.bullish_score
    elif score.bearish_score > score.bullish_score and score.bearish_score >= 55:
        direction = "SHORT"
        confidence = score.bearish_score
    else:
        direction = "NEUTRAL"
        confidence = max(score.activity_score, score.bullish_score, score.bearish_score)

    return CopilotSignalRead(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        confidence=round(confidence, 2),
        reasons=[f"Fallback from latest stored scanner score because live klines were unavailable: {reason}"],
        invalidation_level=None,
        suggested_stop_loss=None,
        suggested_take_profit=None,
        risk_reward_ratio=None,
        indicators=[],
    )


@router.get("/copilot/overview", response_model=CopilotOverviewResponse)
def copilot_overview(request: Request) -> CopilotOverviewResponse:
    risk_service = request.app.state.risk_service
    automation_service = request.app.state.automation_service
    risk = risk_service.build_summary()
    automation = automation_service.build_summary()
    paper = PaperTradingService(request.app.state.settings).summary()

    latest_report = None
    with SessionLocal() as db:
        latest_report = db.scalar(select(models.Report).order_by(desc(models.Report.created_at)))

    best_coin = None
    worst_coin = None
    if latest_report is not None:
        if latest_report.top_bullish_json:
            best_coin = latest_report.top_bullish_json[0].get("symbol")
        elif latest_report.top_active_json:
            best_coin = latest_report.top_active_json[0].get("symbol")
        if latest_report.top_bearish_json:
            worst_coin = latest_report.top_bearish_json[0].get("symbol")

    warnings: list[str] = []
    if not risk.private_api_configured:
        warnings.append("Pionex private API is not configured; live account sync is unavailable.")
    if automation.control.kill_switch_enabled:
        warnings.append(f"Circuit breaker is triggered: {automation.control.kill_switch_reason or 'manual stop'}")
    if risk.last_sync_error:
        warnings.append(f"Latest account sync error: {risk.last_sync_error}")

    mode = automation.control.mode
    account_value = risk.account_equity if risk.account_equity > 0 else paper.account.equity
    buying_power = risk.available_margin if risk.available_margin > 0 else paper.account.cash_balance

    return CopilotOverviewResponse(
        app_name="Evans' Futures Trading Copilot",
        mode=mode,
        live_mode_locked=not (request.app.state.settings.enable_trading and risk.private_api_configured),
        ai_signals_running=True,
        trader_engine_running=not automation.control.kill_switch_enabled,
        circuit_breaker_ok=not automation.control.kill_switch_enabled,
        total_account_value=account_value,
        buying_power=buying_power,
        holdings_margin_used=risk.total_initial_margin if risk.total_initial_margin > 0 else sum(p.margin_used for p in paper.open_positions),
        unrealized_pnl=risk.unrealized_pnl if risk.account_equity > 0 else paper.account.unrealized_pnl,
        realized_pnl=paper.account.realized_pnl,
        today_pnl=risk.daily_pnl if risk.account_equity > 0 else paper.account.realized_pnl,
        win_rate=paper.win_rate,
        number_of_trades=paper.trade_count,
        best_coin=best_coin,
        worst_coin=worst_coin,
        average_hold_minutes=paper.average_hold_minutes,
        open_positions=risk.open_position_count if risk.account_equity > 0 else len(paper.open_positions),
        warnings=warnings,
    )


@router.get("/copilot/signal-heatmap", response_model=SignalHeatmapResponse)
async def signal_heatmap(
    request: Request,
    symbols: str = Query(default=",".join(DEFAULT_SYMBOLS)),
    live: bool = Query(default=False),
) -> SignalHeatmapResponse:
    pionex_client = request.app.state.pionex_client
    engine = SignalEngine()
    requested_symbols = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    timeframes = list(TIMEFRAME_MAP.keys())
    semaphore = asyncio.Semaphore(4)

    async def analyze(symbol: str, display_timeframe: str):
        async with semaphore:
            try:
                candles = await pionex_client.get_klines(symbol, interval=TIMEFRAME_MAP[display_timeframe], limit=120)
                return engine.analyze(symbol, display_timeframe, candles)
            except Exception as exc:
                with SessionLocal() as db:
                    db.add(
                        models.CopilotLog(
                            category="api_error",
                            severity="warning",
                            message=f"Pionex kline request failed for {symbol} {display_timeframe}; using stored scanner fallback.",
                            payload_json={"error": str(exc), "symbol": symbol, "timeframe": display_timeframe},
                        )
                    )
                    db.commit()
                return _fallback_signal(symbol, display_timeframe, str(exc))

    rows: list[SignalHeatmapRowRead] = []
    for symbol in requested_symbols:
        if live:
            cells = await asyncio.gather(*(analyze(symbol, timeframe) for timeframe in timeframes))
        else:
            cells = [
                _fallback_signal(symbol, timeframe, "Using latest stored scanner score; live kline refresh was not requested.")
                for timeframe in timeframes
            ]
        long_count = sum(1 for cell in cells if cell.direction == "LONG")
        short_count = sum(1 for cell in cells if cell.direction == "SHORT")
        dominant = "LONG" if long_count >= short_count else "SHORT"
        dominant_count = max(long_count, short_count)
        confidence = round(sum(cell.confidence for cell in cells) / len(cells), 2) if cells else 0.0
        rows.append(
            SignalHeatmapRowRead(
                symbol=symbol,
                cells=list(cells),
                summary=f"{dominant_count}/{len(cells)} {dominant}, {confidence:.0f}% confidence",
                confidence=confidence,
            )
        )

    return SignalHeatmapResponse(symbols=requested_symbols, timeframes=timeframes, rows=rows)


@router.post("/copilot/manual-signal", response_model=TradingViewWebhookResponse)
async def manual_signal(payload: ManualSignalRequest, request: Request) -> TradingViewWebhookResponse:
    settings = request.app.state.settings
    automation_service = request.app.state.automation_service
    paper_service = PaperTradingService(settings)
    webhook_payload = {
        "id": f"manual-{payload.symbol}-{payload.side}-{models.utc_now().timestamp()}",
        "strategy": payload.strategy,
        "symbol": payload.symbol.upper(),
        "action": payload.side,
        "order_type": payload.order_type,
        "size": payload.size,
        "entry_price": payload.entry_price,
        "stop_price": payload.stop_price,
        "take_profit_price": payload.take_profit_price,
        "planned_leverage": payload.planned_leverage,
        "position_side": payload.position_side,
        "reduce_only": payload.reduce_only,
    }
    with SessionLocal() as db:
        control = automation_service.ensure_control(db)
        if control.kill_switch_enabled:
            signal = models.AutomationSignal(
                source="manual_ticket",
                source_signal_id=webhook_payload["id"],
                strategy_name=payload.strategy,
                symbol=payload.symbol.upper(),
                side=payload.side,
                mode_at_receipt=control.mode,
                status="blocked",
                status_reason=control.kill_switch_reason or "Circuit breaker is engaged.",
                requested_order_type=payload.order_type,
                requested_size=payload.size,
                requested_entry_price=payload.entry_price,
                requested_stop_price=payload.stop_price or 0.0,
                requested_take_profit_price=payload.take_profit_price or 0.0,
                raw_payload_json=webhook_payload,
            )
            db.add(signal)
            db.add(
                models.CopilotLog(
                    category="risk_rejection",
                    severity="warning",
                    message=f"Manual {payload.side} signal blocked by circuit breaker.",
                    payload_json=webhook_payload,
                )
            )
            db.commit()
            db.refresh(signal)
            return TradingViewWebhookResponse(
                ok=True,
                signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
                message="Manual signal blocked by the circuit breaker.",
            )

        if control.mode == "paper":
            position = paper_service.open_position(
                PaperOrderRequest(
                    symbol=payload.symbol,
                    side="LONG" if payload.side == "BUY" else "SHORT",
                    entry_price=payload.entry_price,
                    size=payload.size,
                    leverage=payload.planned_leverage,
                    stop_loss=payload.stop_price,
                    take_profit=payload.take_profit_price,
                )
            ).position
            signal = models.AutomationSignal(
                source="manual_ticket",
                source_signal_id=webhook_payload["id"],
                strategy_name=payload.strategy,
                symbol=payload.symbol.upper(),
                side=payload.side,
                mode_at_receipt=control.mode,
                status="paper_executed",
                status_reason=f"Paper {position.side.lower()} position opened from manual ticket.",
                requested_order_type=payload.order_type,
                requested_size=payload.size,
                requested_entry_price=payload.entry_price,
                requested_stop_price=payload.stop_price or 0.0,
                requested_take_profit_price=payload.take_profit_price or 0.0,
                planned_order_json=webhook_payload,
                execution_result_json={"paper_position_id": position.id, "paper": True},
                raw_payload_json=webhook_payload,
            )
            db.add(signal)
            db.add(
                models.CopilotLog(
                    category="paper_trade",
                    severity="info",
                    message=f"Manual paper {position.side} opened for {payload.symbol}.",
                    payload_json={"paper_position_id": position.id, **webhook_payload},
                )
            )
            db.commit()
            db.refresh(signal)
            return TradingViewWebhookResponse(
                ok=True,
                signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
                message="Manual ticket opened a paper position.",
            )

    with SessionLocal() as db:
        db.add(
            models.CopilotLog(
                category="user_action",
                severity="info",
                message=f"Manual {payload.side} signal submitted for {payload.symbol}.",
                payload_json=webhook_payload,
            )
        )
        db.commit()
    return await automation_service.handle_tradingview_webhook(
        webhook_payload,
        header_secret=settings.tradingview_webhook_secret,
    )


@router.get("/paper/summary", response_model=PaperSummaryResponse)
def paper_summary(request: Request) -> PaperSummaryResponse:
    return PaperTradingService(request.app.state.settings).summary()


@router.post("/paper/positions", response_model=PaperTradeResponse)
def open_paper_position(payload: PaperOrderRequest, request: Request) -> PaperTradeResponse:
    return PaperTradingService(request.app.state.settings).open_position(payload)


@router.post("/paper/positions/{position_id}/close", response_model=PaperTradeResponse)
def close_paper_position(position_id: int, payload: PaperCloseRequest, request: Request) -> PaperTradeResponse:
    return PaperTradingService(request.app.state.settings).close_position(position_id, payload)


@router.get("/copilot/logs", response_model=list[CopilotLogRead])
def copilot_logs(limit: int = Query(default=100, ge=1, le=500)) -> list[CopilotLogRead]:
    with SessionLocal() as db:
        logs = db.scalars(select(models.CopilotLog).order_by(desc(models.CopilotLog.created_at)).limit(limit)).all()
        return [CopilotLogRead.model_validate(log, from_attributes=True) for log in logs]
