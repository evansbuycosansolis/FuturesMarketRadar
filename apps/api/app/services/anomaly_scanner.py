from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime

from .. import models


@dataclass(slots=True)
class FuturesAnomaly:
    symbol: str
    direction: str
    score: float
    current_price: float
    ret_1m: float
    ret_5m: float
    ret_15m: float
    z_move_5m: float
    volume_ratio_1m: float
    accel_score: float
    range_position_24h: float
    wick_signal: float
    order_imbalance: float
    isolation_bonus: float
    funding_extreme: float
    open_interest_change_pct: float
    liquidity_score: float
    timestamp: datetime | None
    reason_tags: list[str] = field(default_factory=list)


def _pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100.0


def _safe_stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _interval_volumes(history: list[models.MarketSnapshot]) -> list[float]:
    volumes: list[float] = []
    for previous, current in zip(history, history[1:], strict=False):
        delta = current.quote_volume_24h - previous.quote_volume_24h
        volumes.append(max(delta, 0.0))
    return volumes


def _returns(history: list[models.MarketSnapshot]) -> list[float]:
    return [_pct_change(current.price, previous.price) for previous, current in zip(history, history[1:], strict=False)]


def _market_context_return(
    histories: dict[str, list[models.MarketSnapshot]],
    symbol: str,
    periods: int,
) -> float:
    context: list[float] = []
    for context_symbol in ("BTC_USDT_PERP", "ETH_USDT_PERP"):
        if context_symbol == symbol:
            continue
        context_history = histories.get(context_symbol, [])
        if len(context_history) > periods:
            context.append(_pct_change(context_history[-1].price, context_history[-1 - periods].price))
    return _mean(context)


def scan_futures_anomalies(
    histories: dict[str, list[models.MarketSnapshot]],
    *,
    limit: int = 12,
    min_quote_volume: float = 50_000.0,
) -> tuple[list[FuturesAnomaly], list[FuturesAnomaly]]:
    candidates: list[FuturesAnomaly] = []

    for symbol, raw_history in histories.items():
        history = sorted(raw_history, key=lambda snapshot: snapshot.timestamp)
        if len(history) < 6:
            continue

        latest = history[-1]
        previous = history[-2]
        prior_15m = history[-4] if len(history) >= 4 else history[0]
        prior_returns = _returns(history[:-1])[-288:]
        latest_returns = _returns(history)
        interval_volumes = _interval_volumes(history)

        ret_1m = _pct_change(latest.price, previous.price)
        ret_5m = ret_1m
        ret_15m = _pct_change(latest.price, prior_15m.price)
        vol_5m = max(_safe_stdev(prior_returns), 0.01)
        z_move_5m = ret_5m / vol_5m

        current_volume = interval_volumes[-1] if interval_volumes else 0.0
        avg_volume_1h = _mean([volume for volume in interval_volumes[-12:] if volume > 0])
        avg_volume_24h = _mean([volume for volume in interval_volumes[-288:] if volume > 0])
        volume_baseline = avg_volume_1h or avg_volume_24h or max(latest.quote_volume_24h / 288.0, 1.0)
        volume_ratio = current_volume / max(volume_baseline, 1.0)

        recent_returns = latest_returns[-3:]
        accel_score = 0.0
        if len(recent_returns) >= 3:
            slope = (recent_returns[-1] - recent_returns[0]) / 2.0
            accel_score = math.copysign(min(abs(slope) / max(vol_5m, 0.01), 5.0), slope)

        spread_24h = latest.high_24h - latest.low_24h
        range_position = 0.5 if spread_24h <= 0 else _clamp((latest.price - latest.low_24h) / spread_24h, 0.0, 1.0)
        direction = "breakout" if ret_5m >= 0 else "breakdown"

        reversal = 0.0
        if direction == "breakout" and latest.price < previous.price and range_position > 0.75:
            reversal = 1.0
        elif direction == "breakdown" and latest.price > previous.price and range_position < 0.25:
            reversal = 1.0

        oi_change = _pct_change(latest.open_interest, previous.open_interest) if previous.open_interest > 0 else 0.0
        context_return = _market_context_return(histories, symbol, 1)
        isolation_bonus = min(abs(ret_5m - context_return) / max(abs(context_return), 0.15), 3.0) if abs(ret_5m) >= 0.2 else 0.0
        liquidity_score = _clamp(latest.quote_volume_24h / max(min_quote_volume, 1.0), 0.0, 1.0)

        signed_accel = accel_score if direction == "breakout" else -accel_score
        signed_z = z_move_5m if direction == "breakout" else -z_move_5m
        score = (
            2.0 * max(signed_z, 0.0)
            + 1.5 * min(volume_ratio, 10.0)
            + 2.5 * max(signed_accel, 0.0)
            + 1.0 * reversal
            + 1.0 * isolation_bonus
            + 0.5 * max(abs(oi_change) / 2.0, 0.0)
        ) * liquidity_score

        if volume_ratio < 1.2 and abs(z_move_5m) < 1.5 and abs(accel_score) < 1.0:
            continue
        if latest.quote_volume_24h < min_quote_volume:
            continue

        tags: list[str] = []
        abs_z = abs(z_move_5m)
        if abs_z >= 3.0:
            tags.append(f"ZMOVE_{abs_z:.1f}")
        elif abs_z >= 1.5:
            tags.append("UNUSUAL_MOVE")
        if volume_ratio >= 10:
            tags.append("VOL_SPIKE_10X")
        elif volume_ratio >= 5:
            tags.append("VOL_SPIKE_5X")
        elif volume_ratio >= 2:
            tags.append("VOL_SPIKE_2X")
        if max(signed_accel, 0.0) >= 2:
            tags.append("ACCELERATION_BREAKOUT" if direction == "breakout" else "ACCELERATION_BREAKDOWN")
        if reversal:
            tags.append("LIQUIDATION_WICK")
        if isolation_bonus >= 1.5:
            tags.append("ISOLATED_MOVE")
        if abs(oi_change) >= 2:
            tags.append("OI_EXPANSION")
        if not tags:
            tags.append("EARLY_ANOMALY")

        candidates.append(
            FuturesAnomaly(
                symbol=symbol,
                direction=direction,
                score=round(score, 2),
                current_price=latest.price,
                ret_1m=round(ret_1m, 4),
                ret_5m=round(ret_5m, 4),
                ret_15m=round(ret_15m, 4),
                z_move_5m=round(z_move_5m, 4),
                volume_ratio_1m=round(volume_ratio, 4),
                accel_score=round(accel_score, 4),
                range_position_24h=round(range_position, 4),
                wick_signal=round(reversal, 4),
                order_imbalance=0.0,
                isolation_bonus=round(isolation_bonus, 4),
                funding_extreme=0.0,
                open_interest_change_pct=round(oi_change, 4),
                liquidity_score=round(liquidity_score, 4),
                timestamp=latest.timestamp,
                reason_tags=tags,
            )
        )

    breakouts = sorted(
        [candidate for candidate in candidates if candidate.direction == "breakout"],
        key=lambda candidate: candidate.score,
        reverse=True,
    )[:limit]
    breakdowns = sorted(
        [candidate for candidate in candidates if candidate.direction == "breakdown"],
        key=lambda candidate: candidate.score,
        reverse=True,
    )[:limit]
    return breakouts, breakdowns
