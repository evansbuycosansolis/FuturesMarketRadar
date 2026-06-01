from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from ..schemas import CopilotSignalRead, SignalIndicatorRead
from .pionex_client import PionexKline


@dataclass(slots=True)
class IndicatorVote:
    name: str
    value: float | str
    direction: str
    reason: str


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value * alpha) + (result[-1] * (1 - alpha)))
    return result


def _dema(values: list[float], period: int) -> float:
    ema = _ema(values, period)
    ema_ema = _ema(ema, period)
    return (2 * ema[-1]) - ema_ema[-1]


def _tema(values: list[float], period: int) -> float:
    ema1 = _ema(values, period)
    ema2 = _ema(ema1, period)
    ema3 = _ema(ema2, period)
    return (3 * ema1[-1]) - (3 * ema2[-1]) + ema3[-1]


def _vwap(candles: list[PionexKline]) -> float:
    weighted = sum(((candle.high + candle.low + candle.close) / 3) * candle.volume for candle in candles)
    volume = sum(candle.volume for candle in candles)
    return weighted / volume if volume else candles[-1].close


def _atr(candles: list[PionexKline], period: int = 14) -> float:
    ranges: list[float] = []
    previous_close = candles[0].close
    for candle in candles[1:]:
        ranges.append(max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))
        previous_close = candle.close
    if not ranges:
        return 0.0
    return mean(ranges[-period:])


def _macd(values: list[float]) -> tuple[float, float, float]:
    fast = _ema(values, 12)
    slow = _ema(values, 26)
    macd_line = [fast_value - slow_value for fast_value, slow_value in zip(fast[-len(slow):], slow)]
    signal = _ema(macd_line, 9)
    histogram = macd_line[-1] - signal[-1]
    return macd_line[-1], signal[-1], histogram


def _adx(candles: list[PionexKline], period: int = 14) -> float:
    if len(candles) < period + 2:
        return 0.0
    directional_strength: list[float] = []
    for previous, current in zip(candles[-period - 1:-1], candles[-period:]):
        up_move = current.high - previous.high
        down_move = previous.low - current.low
        true_range = max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close))
        if true_range <= 0:
            directional_strength.append(0.0)
            continue
        dominant = max(up_move, down_move, 0.0)
        directional_strength.append((dominant / true_range) * 100)
    return mean(directional_strength) if directional_strength else 0.0


def _direction(long_votes: int, short_votes: int) -> str:
    if long_votes >= short_votes + 2:
        return "LONG"
    if short_votes >= long_votes + 2:
        return "SHORT"
    return "NEUTRAL"


class SignalEngine:
    def analyze(self, symbol: str, timeframe: str, candles: list[PionexKline]) -> CopilotSignalRead:
        if len(candles) < 30:
            return CopilotSignalRead(
                symbol=symbol,
                timeframe=timeframe,
                direction="NEUTRAL",
                confidence=0.0,
                reasons=["Not enough candle history for deterministic indicator stack."],
                invalidation_level=None,
                suggested_stop_loss=None,
                suggested_take_profit=None,
                risk_reward_ratio=None,
                indicators=[],
            )

        closes = [candle.close for candle in candles]
        latest = candles[-1]
        previous = candles[-2]
        atr = _atr(candles)
        tema = _tema(closes, 20)
        dema = _dema(closes, 20)
        vwap = _vwap(candles[-40:])
        macd_line, macd_signal, macd_hist = _macd(closes)
        adx = _adx(candles)
        recent_high = max(candle.high for candle in candles[-10:])
        recent_low = min(candle.low for candle in candles[-10:])
        volume_average = mean([candle.volume for candle in candles[-20:]])
        volume_ratio = latest.volume / volume_average if volume_average else 1.0

        votes: list[IndicatorVote] = []
        votes.append(IndicatorVote("TEMA", round(tema, 8), "LONG" if latest.close > tema else "SHORT", "Close is above TEMA." if latest.close > tema else "Close is below TEMA."))
        votes.append(IndicatorVote("DEMA", round(dema, 8), "LONG" if latest.close > dema else "SHORT", "Close is above DEMA." if latest.close > dema else "Close is below DEMA."))
        votes.append(IndicatorVote("VWAP", round(vwap, 8), "LONG" if latest.close > vwap else "SHORT", "Price is above VWAP." if latest.close > vwap else "Price is below VWAP."))
        votes.append(IndicatorVote("MACD", round(macd_hist, 8), "LONG" if macd_hist > 0 else "SHORT", "MACD histogram is positive." if macd_hist > 0 else "MACD histogram is negative."))
        votes.append(IndicatorVote("ATR", round(atr, 8), "NEUTRAL", "ATR defines stop distance and volatility, not direction."))
        votes.append(IndicatorVote("ADX", round(adx, 2), "LONG" if adx >= 22 and latest.close > previous.close else "SHORT" if adx >= 22 else "NEUTRAL", "Trend strength is usable." if adx >= 22 else "Trend strength is weak."))
        votes.append(IndicatorVote("Volume Trend", round(volume_ratio, 2), "LONG" if volume_ratio > 1.15 and latest.close > latest.open else "SHORT" if volume_ratio > 1.15 and latest.close < latest.open else "NEUTRAL", "Volume confirms the latest candle." if volume_ratio > 1.15 else "Volume is not confirming strongly."))
        votes.append(IndicatorVote("Smart Money Concept", "sweep/break", "LONG" if latest.close > recent_high and latest.low <= previous.low else "SHORT" if latest.close < recent_low and latest.high >= previous.high else "NEUTRAL", "Recent liquidity sweep plus break detected." if latest.close > recent_high or latest.close < recent_low else "No clear sweep/break structure."))

        long_votes = sum(1 for vote in votes if vote.direction == "LONG")
        short_votes = sum(1 for vote in votes if vote.direction == "SHORT")
        direction = _direction(long_votes, short_votes)
        confidence = round((max(long_votes, short_votes) / len(votes)) * 100, 2)

        if direction == "LONG":
            stop = latest.close - max(atr * 1.2, latest.close * 0.005)
            take_profit = latest.close + ((latest.close - stop) * 2)
            invalidation = stop
        elif direction == "SHORT":
            stop = latest.close + max(atr * 1.2, latest.close * 0.005)
            take_profit = latest.close - ((stop - latest.close) * 2)
            invalidation = stop
        else:
            stop = None
            take_profit = None
            invalidation = recent_low if latest.close >= previous.close else recent_high

        rr = 2.0 if stop is not None and take_profit is not None else None
        reasons = [vote.reason for vote in votes if vote.direction == direction][:4] or ["Mixed indicators; no directional consensus."]

        return CopilotSignalRead(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            reasons=reasons,
            invalidation_level=invalidation,
            suggested_stop_loss=stop,
            suggested_take_profit=take_profit,
            risk_reward_ratio=rr,
            indicators=[
                SignalIndicatorRead(name=vote.name, value=vote.value, direction=vote.direction, reason=vote.reason)
                for vote in votes
            ],
        )
