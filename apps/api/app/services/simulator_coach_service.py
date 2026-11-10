from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

import httpx

from ..config import Settings
from ..schemas import SimulatorAnalyzeRequest
from .binance_futures_client import BinanceFuturesClient, pionex_perp_to_binance_symbol
from .pionex_client import PionexKline


@dataclass(frozen=True, slots=True)
class CoachAnalysis:
    analysis: str
    used_ai: bool
    warnings: list[str]


def _binance_symbol_from_tradingview(symbol: str) -> str | None:
    normalized = symbol.strip().upper()
    if normalized.startswith("BINANCE:"):
        normalized = normalized.replace("BINANCE:", "")
    normalized = normalized.replace(".P", "").replace("/", "").replace("_", "")
    return normalized if normalized.endswith("USDT") else None


def _candle_change_pct(candle: PionexKline) -> float:
    return ((candle.close - candle.open) / candle.open) * 100 if candle.open > 0 else 0.0


def _candle_range_pct(candle: PionexKline) -> float:
    return ((candle.high - candle.low) / candle.close) * 100 if candle.close > 0 else 0.0


def _summarize_candles(candles: list[PionexKline]) -> dict[str, float]:
    completed = candles[:-1] if len(candles) > 2 else candles
    recent = completed[-24:]
    if not recent:
        return {
            "last_close": 0.0,
            "change_24_candles_pct": 0.0,
            "avg_range_pct": 0.0,
            "latest_range_pct": 0.0,
            "latest_volume_ratio": 0.0,
            "swing_high": 0.0,
            "swing_low": 0.0,
        }

    first_open = recent[0].open
    last = recent[-1]
    volumes = [candle.volume for candle in recent[:-1] if candle.volume > 0]
    avg_volume = mean(volumes) if volumes else 0.0
    return {
        "last_close": last.close,
        "change_24_candles_pct": ((last.close - first_open) / first_open) * 100 if first_open > 0 else 0.0,
        "avg_range_pct": mean([_candle_range_pct(candle) for candle in recent]),
        "latest_range_pct": _candle_range_pct(last),
        "latest_change_pct": _candle_change_pct(last),
        "latest_volume_ratio": last.volume / avg_volume if avg_volume > 0 else 0.0,
        "swing_high": max(candle.high for candle in recent),
        "swing_low": min(candle.low for candle in recent),
    }


def _risk_warnings(payload: SimulatorAnalyzeRequest) -> list[str]:
    warnings: list[str] = []
    notional = max(payload.margin, 0) * max(payload.leverage, 0)
    if payload.leverage > 10:
        warnings.append("Leverage is above 10x; liquidation distance can become very narrow.")
    if payload.stop_loss is None or payload.stop_loss <= 0:
        warnings.append("No stop loss is set. This setup should be treated as incomplete.")
    if payload.mark_price > 0 and payload.stop_loss and payload.stop_loss > 0:
        stop_distance = abs(payload.mark_price - payload.stop_loss) / payload.mark_price * 100
        if stop_distance < 0.25:
            warnings.append("Stop loss is extremely close to current price and may be vulnerable to normal noise.")
    if notional <= 0:
        warnings.append("Position value is zero; enter margin and leverage before using the plan.")
    return warnings


def _fallback_analysis(payload: SimulatorAnalyzeRequest, summary_15m: dict[str, float], summary_1h: dict[str, float], warnings: list[str]) -> str:
    direction = "long" if payload.side == "long" else "short"
    invalidation = payload.stop_loss if payload.stop_loss and payload.stop_loss > 0 else summary_15m["swing_low" if payload.side == "long" else "swing_high"]
    target = payload.take_profit if payload.take_profit and payload.take_profit > 0 else summary_15m["swing_high" if payload.side == "long" else "swing_low"]
    return (
        f"Decision-support coach summary for {payload.symbol}\n\n"
        f"Market read:\n"
        f"- 15m recent change: {summary_15m['change_24_candles_pct']:+.2f}% with latest volume at {summary_15m['latest_volume_ratio']:.2f}x its recent baseline.\n"
        f"- 1h recent change: {summary_1h['change_24_candles_pct']:+.2f}% with latest volume at {summary_1h['latest_volume_ratio']:.2f}x its recent baseline.\n"
        f"- Recent 15m range is {summary_15m['swing_low']:.8g} to {summary_15m['swing_high']:.8g}.\n\n"
        f"Possible {direction} plan:\n"
        f"- Entry reference: {payload.entry_price:.8g} ({payload.entry_type}).\n"
        f"- Invalidation: near {invalidation:.8g}.\n"
        f"- First target/reference: near {target:.8g}.\n"
        f"- Avoid forcing the trade if price chops back into the middle of the recent range without volume.\n\n"
        f"Risk notes:\n"
        + ("\n".join(f"- {warning}" for warning in warnings) if warnings else "- No major simulator risk warning from the entered fields.")
        + "\n\nThis is decision support only. It is not an instruction to trade."
    )


class SimulatorCoachService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def analyze(self, payload: SimulatorAnalyzeRequest) -> CoachAnalysis:
        warnings = _risk_warnings(payload)
        binance_symbol = _binance_symbol_from_tradingview(payload.symbol) or pionex_perp_to_binance_symbol(payload.symbol)

        binance_client = BinanceFuturesClient(self._settings)
        try:
            candles_15m = await binance_client.get_klines(binance_symbol, interval="15m", limit=80)
            candles_1h = await binance_client.get_klines(binance_symbol, interval="1h", limit=80)
        finally:
            await binance_client.close()

        summary_15m = _summarize_candles(candles_15m)
        summary_1h = _summarize_candles(candles_1h)

        if not self._settings.openai_api_key.strip():
            return CoachAnalysis(
                analysis=_fallback_analysis(payload, summary_15m, summary_1h, warnings),
                used_ai=False,
                warnings=warnings + ["OpenAI API key is not configured; using local rule-based analysis."],
            )

        prompt = {
            "role": "user",
            "content": (
                "Act as a futures trading coach inside a paper simulator. "
                "Do not execute trades. Do not claim certainty. Give decision-support analysis only.\n\n"
                f"Simulator setup: {payload.model_dump()}\n"
                f"15m candle summary: {summary_15m}\n"
                f"1h candle summary: {summary_1h}\n"
                f"Risk warnings: {warnings}\n\n"
                "Return concise sections: Market read, Long option, Short option, Entry/exit logic, Invalidation, Risk warnings, No-trade conditions."
            ),
        }
        body = {
            "model": self._settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a cautious futures trading coach for a paper trading simulator. "
                        "You may suggest possible entry zones, exits, stops, invalidation, and strategy options. "
                        "You must not tell the user to place a live trade, guarantee outcomes, or ignore risk controls."
                    ),
                },
                prompt,
            ],
        }
        async with httpx.AsyncClient(timeout=self._settings.openai_timeout_seconds) as client:
            response = await client.post(
                f"{self._settings.openai_base_url.rstrip('/')}/v1/responses",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        text = data.get("output_text")
        if not text:
            parts: list[str] = []
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        parts.append(content["text"])
            text = "\n".join(parts).strip()

        return CoachAnalysis(
            analysis=text or _fallback_analysis(payload, summary_15m, summary_1h, warnings),
            used_ai=bool(text),
            warnings=warnings,
        )
