from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .pionex_client import PionexKline


@dataclass(frozen=True, slots=True)
class OneHourSpikeCandidate:
    symbol: str
    direction: str
    score: float
    current_price: float
    latest_price_change_pct: float
    latest_range_pct: float
    baseline_range_pct: float
    range_ratio: float
    volume_ratio: float
    latest_volume: float
    baseline_volume: float
    timestamp: int | None
    reason_tags: list[str]


def _candle_range_pct(candle: PionexKline) -> float:
    return ((candle.high - candle.low) / candle.close) * 100 if candle.close > 0 else 0.0


def _candle_change_pct(candle: PionexKline) -> float:
    return ((candle.close - candle.open) / candle.open) * 100 if candle.open > 0 else 0.0


def _safe_ratio(value: float, baseline: float) -> float:
    return value / baseline if baseline > 0 else 0.0


def scan_one_hour_spikes(
    candles_by_symbol: dict[str, list[PionexKline]],
    *,
    limit: int = 20,
    baseline_candles: int = 48,
    min_range_ratio: float = 2.2,
    min_volume_ratio: float = 2.5,
    min_abs_change_pct: float = 1.5,
) -> list[OneHourSpikeCandidate]:
    candidates: list[OneHourSpikeCandidate] = []

    for symbol, candles in candles_by_symbol.items():
        ordered = sorted(candles, key=lambda candle: candle.time)
        completed = ordered[:-1] if len(ordered) > baseline_candles + 2 else ordered
        if len(completed) < baseline_candles + 1:
            continue

        latest = completed[-1]
        baseline = completed[-(baseline_candles + 1):-1]
        baseline_ranges = [_candle_range_pct(candle) for candle in baseline if candle.close > 0]
        baseline_volumes = [candle.volume for candle in baseline if candle.volume > 0]
        if not baseline_ranges or not baseline_volumes:
            continue

        latest_range_pct = _candle_range_pct(latest)
        latest_change_pct = _candle_change_pct(latest)
        baseline_range_pct = median(baseline_ranges)
        baseline_volume = median(baseline_volumes)
        range_ratio = _safe_ratio(latest_range_pct, baseline_range_pct)
        volume_ratio = _safe_ratio(latest.volume, baseline_volume)

        price_pass = range_ratio >= min_range_ratio or abs(latest_change_pct) >= min_abs_change_pct
        volume_pass = volume_ratio >= min_volume_ratio
        if not (price_pass and volume_pass):
            continue

        direction = "bullish" if latest.close >= latest.open else "bearish"
        reason_tags = [
            f"1H_RANGE_{range_ratio:.1f}X",
            f"1H_VOLUME_{volume_ratio:.1f}X",
            f"1H_CHANGE_{latest_change_pct:+.2f}%",
        ]
        if range_ratio >= 4:
            reason_tags.append("EXTREME_PRICE_SPIKE")
        if volume_ratio >= 5:
            reason_tags.append("EXTREME_VOLUME_SPIKE")

        score = min(
            100.0,
            (range_ratio * 18.0)
            + (volume_ratio * 12.0)
            + min(abs(latest_change_pct) * 5.0, 20.0),
        )
        candidates.append(
            OneHourSpikeCandidate(
                symbol=symbol,
                direction=direction,
                score=round(score, 2),
                current_price=latest.close,
                latest_price_change_pct=round(latest_change_pct, 4),
                latest_range_pct=round(latest_range_pct, 4),
                baseline_range_pct=round(baseline_range_pct, 4),
                range_ratio=round(range_ratio, 4),
                volume_ratio=round(volume_ratio, 4),
                latest_volume=latest.volume,
                baseline_volume=baseline_volume,
                timestamp=latest.time,
                reason_tags=reason_tags,
            )
        )

    candidates.sort(key=lambda item: (item.score, item.volume_ratio, item.range_ratio), reverse=True)
    return candidates[:limit]
