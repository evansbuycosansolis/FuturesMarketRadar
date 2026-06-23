from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Protocol


class CandleLike(Protocol):
    time: int
    open: float
    close: float
    high: float
    low: float
    volume: float


@dataclass(frozen=True, slots=True)
class SleepingGiantSetup:
    symbol: str
    direction: str
    awakening_phase: str
    average_candle_size: float
    latest_candle_size: float
    median_candle_height_pct: float
    latest_candle_height_pct: float
    height_ratio: float
    volume_ratio: float
    body_strength: float
    two_candle_pressure: float
    range_burst_score: float
    volume_burst_score: float
    compression_score: float
    breakout_score: float
    volume_expansion_ratio: float
    range_expansion_ratio: float
    distance_from_box_breakout: float
    current_price: float
    timestamp: int
    score: float
    compression_candles: int
    box_high: float
    box_low: float
    notes: list[str]


@dataclass(frozen=True, slots=True)
class SleepingGiantConfig:
    timeframe: str = "4H"
    baseline_candles: int = 200
    compression_min_candles: int = 20
    compression_max_candles: int = 50
    min_range_burst_score: float = 2.0
    min_volume_burst_score: float = 2.0
    min_confirmed_volume_burst_score: float = 1.5
    min_range_expansion_ratio: float = 1.35
    watch_height_ratio: float = 1.5
    pressure_height_ratio: float = 2.0
    giant_height_ratio: float = 3.0
    giant_volume_ratio: float = 2.0
    directional_body_strength: float = 0.6
    wick_body_strength: float = 0.3
    max_sleep_height_ratio: float = 1.5
    require_sleep_window: bool = True
    require_two_candle_confirmation: bool = True
    strong_volume_expansion_ratio: float = 2.0
    strong_close_threshold: float = 0.7


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if abs(denominator) <= 1e-12:
        return default
    return numerator / denominator


def _burst_score(current: float, average: float, standard_deviation: float) -> float:
    floor = max(abs(average) * 0.1, 1e-12)
    adjusted_deviation = max(standard_deviation, floor)
    return (current - average) / adjusted_deviation


def _candle_height_pct(candle: CandleLike) -> float:
    if candle.close <= 0:
        return 0.0
    return (max(candle.high - candle.low, 0.0) / candle.close) * 100


def _body_strength(candle: CandleLike) -> float:
    spread = candle.high - candle.low
    if spread <= 0:
        return 0.0
    return abs(candle.close - candle.open) / spread


def _true_ranges(candles: list[CandleLike]) -> list[float]:
    if not candles:
        return []
    ranges: list[float] = [max(candles[0].high - candles[0].low, 0.0)]
    previous_close = candles[0].close
    for candle in candles[1:]:
        ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
                0.0,
            )
        )
        previous_close = candle.close
    return ranges


def _atr(candles: list[CandleLike], period: int = 14) -> float:
    ranges = _true_ranges(candles)
    if not ranges:
        return 0.0
    return mean(ranges[-period:])


def _close_position(candle: CandleLike) -> float:
    spread = candle.high - candle.low
    if spread <= 0:
        return 0.5
    return (candle.close - candle.low) / spread


def _bollinger_width_pct(candles: list[CandleLike], period: int = 20, deviations: float = 2.0) -> float:
    closes = [candle.close for candle in candles[-period:]]
    if len(closes) < 2:
        return 0.0
    middle = mean(closes)
    if middle <= 0:
        return 0.0
    width = (deviations * pstdev(closes)) * 2
    return (width / middle) * 100


class SleepingGiantScanner:
    def __init__(self, config: SleepingGiantConfig | None = None) -> None:
        self._config = config or SleepingGiantConfig()

    def scan(self, candles_by_symbol: dict[str, list[CandleLike]], limit: int = 25) -> list[SleepingGiantSetup]:
        setups = [
            setup
            for symbol, candles in candles_by_symbol.items()
            if (setup := self.analyze_symbol(symbol, candles)) is not None
        ]
        setups.sort(
            key=lambda setup: (
                setup.score,
                setup.height_ratio,
                setup.volume_ratio,
                setup.range_expansion_ratio,
                setup.volume_expansion_ratio,
                setup.compression_score,
            ),
            reverse=True,
        )
        return setups[:limit]

    def analyze_symbol(self, symbol: str, candles: list[CandleLike]) -> SleepingGiantSetup | None:
        config = self._config
        required = config.baseline_candles + 2
        if len(candles) < required:
            return None

        candles = sorted(candles, key=lambda candle: candle.time)
        baseline = candles[-required:-2]
        previous = candles[-2]
        latest = candles[-1]

        baseline_ranges = [max(candle.high - candle.low, 0.0) for candle in baseline]
        baseline_height_pcts = [_candle_height_pct(candle) for candle in baseline]
        baseline_volumes = [max(candle.volume, 0.0) for candle in baseline]
        average_candle_size = mean(baseline_ranges)
        median_candle_height_pct = median(baseline_height_pcts)
        median_volume = median(baseline_volumes)
        average_volume = mean(baseline_volumes)
        if average_candle_size <= 0 or median_candle_height_pct <= 0:
            return None

        latest_candle_size = max(latest.high - latest.low, 0.0)
        previous_candle_size = max(previous.high - previous.low, 0.0)
        latest_candle_height_pct = _candle_height_pct(latest)
        previous_candle_height_pct = _candle_height_pct(previous)
        latest_size_ratio = _safe_divide(latest_candle_size, average_candle_size)
        previous_size_ratio = _safe_divide(previous_candle_size, average_candle_size)
        height_ratio = _safe_divide(latest_candle_height_pct, median_candle_height_pct)
        previous_height_ratio = _safe_divide(previous_candle_height_pct, median_candle_height_pct)
        volume_ratio = _safe_divide(max(latest.volume, 0.0), median_volume, default=1.0)
        body_strength = _body_strength(latest)
        two_candle_pressure = (height_ratio + previous_height_ratio) / 2
        sleep_window = baseline
        sleep_height_ratios = [
            _safe_divide(_candle_height_pct(candle), median_candle_height_pct)
            for candle in sleep_window
        ]
        if config.require_sleep_window and (
            not sleep_height_ratios or max(sleep_height_ratios) >= config.max_sleep_height_ratio
        ):
            return None
        range_deviation = pstdev(baseline_ranges) if len(baseline_ranges) >= 2 else 0.0
        volume_deviation = pstdev(baseline_volumes) if len(baseline_volumes) >= 2 else 0.0
        range_burst_score = _burst_score(latest_candle_size, average_candle_size, range_deviation)
        previous_range_burst_score = _burst_score(previous_candle_size, average_candle_size, range_deviation)
        volume_burst_score = _burst_score(max(latest.volume, 0.0), average_volume, volume_deviation)

        range_trigger = (
            range_burst_score >= config.min_range_burst_score
            and latest_size_ratio >= config.min_range_expansion_ratio
        )
        volume_confirmed_trigger = (
            range_burst_score >= config.min_confirmed_volume_burst_score
            and volume_burst_score >= config.min_volume_burst_score
            and latest_size_ratio >= config.min_range_expansion_ratio
        )
        two_candle_expansion = (
            range_burst_score >= config.min_confirmed_volume_burst_score
            and previous_range_burst_score >= config.min_confirmed_volume_burst_score
            and latest_size_ratio >= config.min_range_expansion_ratio
            and previous_size_ratio >= config.min_range_expansion_ratio
        )
        last_two_abnormal = height_ratio >= config.pressure_height_ratio and previous_height_ratio >= config.pressure_height_ratio
        median_watch = last_two_abnormal
        median_pressure = last_two_abnormal
        median_awakening = (
            (last_two_abnormal or not config.require_two_candle_confirmation)
            and (
                height_ratio >= config.giant_height_ratio
                or previous_height_ratio >= config.giant_height_ratio
                or two_candle_pressure >= 2.5
            )
            and volume_ratio >= config.giant_volume_ratio
        )
        liquidity_spike = last_two_abnormal and height_ratio >= config.giant_height_ratio and body_strength < config.wick_body_strength
        if config.require_two_candle_confirmation:
            if not last_two_abnormal:
                return None
        else:
            recent_abnormal = (
                height_ratio >= config.pressure_height_ratio
                or (height_ratio >= config.watch_height_ratio and previous_height_ratio >= config.pressure_height_ratio)
                or two_candle_expansion
                or range_trigger
                or volume_confirmed_trigger
            )
            if not recent_abnormal:
                return None

        close_position = _close_position(latest)
        bullish = latest.close >= latest.open and (close_position >= 0.55 or liquidity_spike)
        bearish = latest.close < latest.open and (close_position <= 0.45 or liquidity_spike)
        if not bullish and not bearish and not liquidity_spike:
            return None

        direction = "bullish" if bullish else "bearish"
        close_strength = close_position if bullish else 1 - close_position
        if liquidity_spike:
            awakening_phase = "liquidity_spike"
        elif median_awakening and body_strength >= config.directional_body_strength:
            awakening_phase = "giant_awakening"
        elif median_pressure or height_ratio >= config.pressure_height_ratio or previous_height_ratio >= config.pressure_height_ratio:
            awakening_phase = "pressure_building"
        else:
            awakening_phase = "watch"
        volume_expansion = _safe_divide(latest.volume, average_volume, default=1.0)
        compression = self._compression_read(baseline, average_candle_size)

        range_score = min(100.0, max(range_burst_score, 0.0) / 4.0 * 100)
        volume_score = min(100.0, max(volume_burst_score, 0.0) / 4.0 * 100)
        height_score = min(100.0, height_ratio / 5.0 * 100)
        volume_ratio_score = min(100.0, volume_ratio / 4.0 * 100)
        close_score = close_strength * 100
        two_candle_score = 100.0 if two_candle_expansion else 70.0
        breakout_score = round(
            (range_score * 0.22)
            + (volume_score * 0.16)
            + (height_score * 0.22)
            + (volume_ratio_score * 0.15)
            + (close_score * 0.15)
            + (two_candle_score * 0.1),
            2,
        )

        volume_bonus = 10.0 if volume_ratio >= config.giant_volume_ratio else 0.0
        close_bonus = 5.0 if close_strength >= config.strong_close_threshold else 0.0
        compression_bonus = 7.0 if compression["score"] >= 60 else 0.0
        phase_bonus = {
            "watch": 0.0,
            "pressure_building": 5.0,
            "giant_awakening": 12.0,
            "liquidity_spike": 3.0,
        }[awakening_phase]
        score = round(
            min(
                100.0,
                (height_ratio / 4.5 * 28)
                + (volume_ratio / 3.5 * 20)
                + (max(range_burst_score, 0.0) / 3.5 * 18)
                + (max(volume_burst_score, 0.0) / 3.0 * 12)
                + (compression["score"] * 0.12)
                + (close_score * 0.1)
                + volume_bonus
                + close_bonus
                + compression_bonus
                + phase_bonus,
            ),
            2,
        )

        box_high = compression["box_high"]
        box_low = compression["box_low"]
        breakout_level = box_high if bullish else box_low
        distance = latest.close - breakout_level if bullish else breakout_level - latest.close

        return SleepingGiantSetup(
            symbol=symbol,
            direction=direction,
            awakening_phase=awakening_phase,
            average_candle_size=round(average_candle_size, 8),
            latest_candle_size=round(latest_candle_size, 8),
            median_candle_height_pct=round(median_candle_height_pct, 6),
            latest_candle_height_pct=round(latest_candle_height_pct, 6),
            height_ratio=round(height_ratio, 4),
            volume_ratio=round(volume_ratio, 4),
            body_strength=round(body_strength, 4),
            two_candle_pressure=round(two_candle_pressure, 4),
            range_burst_score=round(range_burst_score, 4),
            volume_burst_score=round(volume_burst_score, 4),
            compression_score=round(compression["score"], 2),
            breakout_score=breakout_score,
            volume_expansion_ratio=round(volume_expansion, 4),
            range_expansion_ratio=round(latest_size_ratio, 4),
            distance_from_box_breakout=round(distance, 8),
            current_price=latest.close,
            timestamp=latest.time,
            score=score,
            compression_candles=int(compression["candles"]),
            box_high=box_high,
            box_low=box_low,
            notes=[
                f"{config.timeframe} early expansion scanner alert only; not a buy/sell signal.",
                f"{awakening_phase.replace('_', ' ').title()}: candle height is {height_ratio:.2f}x the median height and volume is {volume_ratio:.2f}x median.",
                f"Latest closed candle range is {range_burst_score:.2f} standard deviations above its {config.baseline_candles}-candle average.",
                f"Volume is {volume_burst_score:.2f} standard deviations above average; body strength is {body_strength:.0%}.",
                (
                    f"{int(compression['candles'])} prior candles scored {compression['score']:.0f}/100 compression; "
                    f"box width {compression['box_width_pct']:.2f}%, Bollinger width {compression['bbw_pct']:.2f}%, "
                    f"ATR ratio {compression['atr_ratio']:.2f}."
                    + (
                        f" Recent sleep window stayed below {config.max_sleep_height_ratio:.1f}x median height."
                        if config.require_sleep_window
                        else " Recent-awakening mode does not require the full baseline to still be asleep."
                    )
                ),
            ],
        )

    def _compression_read(self, baseline: list[CandleLike], average_candle_size: float) -> dict[str, float]:
        config = self._config
        baseline_atr = mean(_true_ranges(baseline)) if baseline else average_candle_size
        best: dict[str, float] | None = None

        for window_size in range(config.compression_max_candles, config.compression_min_candles - 1, -1):
            compression = baseline[-window_size:]
            ranges = [max(candle.high - candle.low, 0.0) for candle in compression]
            average_range = mean(ranges)
            box_high = max(candle.high for candle in compression)
            box_low = min(candle.low for candle in compression)
            mid_price = max(mean(candle.close for candle in compression), 1e-12)
            box_width_pct = ((box_high - box_low) / mid_price) * 100
            atr_ratio = _safe_divide(_atr(compression), baseline_atr, default=1.0)
            bbw_pct = _bollinger_width_pct(compression)
            average_body = mean(abs(candle.close - candle.open) for candle in compression)
            body_to_range = _safe_divide(average_body, average_range)
            range_ratio = _safe_divide(average_range, average_candle_size, default=1.0)

            tightness_score = max(0.0, min(100.0, (1 - min(range_ratio, 1.0)) * 100))
            atr_score = max(0.0, min(100.0, (1 - min(atr_ratio, 1.0)) * 100))
            body_score = max(0.0, min(100.0, (1 - min(body_to_range, 1.0)) * 100))
            box_score = max(0.0, 100.0 - min(box_width_pct * 8, 100.0))
            length_score = min(100.0, (window_size / config.compression_max_candles) * 100)
            score = round(
                (tightness_score * 0.3)
                + (atr_score * 0.25)
                + (body_score * 0.2)
                + (box_score * 0.15)
                + (length_score * 0.1),
                2,
            )

            candidate = {
                "score": score,
                "candles": float(window_size),
                "box_high": box_high,
                "box_low": box_low,
                "box_width_pct": box_width_pct,
                "bbw_pct": bbw_pct,
                "atr_ratio": atr_ratio,
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate

        if best is None:
            return {
                "score": 0.0,
                "candles": 0.0,
                "box_high": baseline[-1].high,
                "box_low": baseline[-1].low,
                "box_width_pct": 0.0,
                "bbw_pct": 0.0,
                "atr_ratio": 1.0,
            }
        return best


class RecentAwakeningScanner:
    """Broader legacy detector for symbols that recently started waking up.

    Unlike the strict SleepingGiantScanner, this does not require the whole
    baseline to remain asleep. It looks for the latest or previous closed candle
    expanding out of a recent 30-80 candle compression box.
    """

    def __init__(self, config: SleepingGiantConfig | None = None) -> None:
        self._config = config or SleepingGiantConfig(require_sleep_window=False, require_two_candle_confirmation=False)

    def scan(self, candles_by_symbol: dict[str, list[CandleLike]], limit: int = 25) -> list[SleepingGiantSetup]:
        setups = [
            setup
            for symbol, candles in candles_by_symbol.items()
            if (setup := self.analyze_symbol(symbol, candles)) is not None
        ]
        setups.sort(
            key=lambda setup: (
                setup.score,
                setup.range_expansion_ratio,
                setup.volume_expansion_ratio,
                setup.breakout_score,
                setup.compression_score,
            ),
            reverse=True,
        )
        return setups[:limit]

    def analyze_symbol(self, symbol: str, candles: list[CandleLike]) -> SleepingGiantSetup | None:
        config = self._config
        required = max(config.baseline_candles, config.compression_max_candles + 3)
        if len(candles) < required:
            return None

        candles = sorted(candles, key=lambda candle: candle.time)
        candidate_indices = [len(candles) - 1, len(candles) - 2]
        best: SleepingGiantSetup | None = None
        for candidate_index in candidate_indices:
            if candidate_index < config.compression_max_candles:
                continue
            baseline = candles[max(0, candidate_index - config.baseline_candles) : candidate_index]
            setup = self._analyze_candidate(symbol, candles, candidate_index, baseline)
            if setup and (best is None or setup.score > best.score):
                best = setup
        return best

    def _analyze_candidate(
        self,
        symbol: str,
        candles: list[CandleLike],
        candidate_index: int,
        baseline: list[CandleLike],
    ) -> SleepingGiantSetup | None:
        config = self._config
        candidate = candles[candidate_index]
        baseline_ranges = [max(candle.high - candle.low, 0.0) for candle in baseline]
        baseline_volumes = [max(candle.volume, 0.0) for candle in baseline]
        baseline_heights = [_candle_height_pct(candle) for candle in baseline]
        average_candle_size = mean(baseline_ranges)
        median_height = median(baseline_heights)
        median_volume = median(baseline_volumes)
        average_volume = mean(baseline_volumes)
        if average_candle_size <= 0 or median_height <= 0:
            return None

        compression = self._best_recent_box(candles, candidate_index)
        if compression is None:
            return None

        candle_size = max(candidate.high - candidate.low, 0.0)
        candle_height = _candle_height_pct(candidate)
        volume = max(candidate.volume, 0.0)
        range_expansion = _safe_divide(candle_size, compression["average_range"])
        volume_expansion = _safe_divide(volume, compression["average_volume"], default=1.0)
        height_ratio = _safe_divide(candle_height, median_height)
        volume_ratio = _safe_divide(volume, median_volume, default=1.0)
        body_strength = _body_strength(candidate)
        close_position = _close_position(candidate)
        range_deviation = pstdev(baseline_ranges) if len(baseline_ranges) >= 2 else 0.0
        volume_deviation = pstdev(baseline_volumes) if len(baseline_volumes) >= 2 else 0.0
        range_burst = _burst_score(candle_size, average_candle_size, range_deviation)
        volume_burst = _burst_score(volume, average_volume, volume_deviation)

        bullish_breakout = candidate.close > compression["box_high"] and candidate.close >= candidate.open and close_position >= 0.55
        bearish_breakout = candidate.close < compression["box_low"] and candidate.close < candidate.open and close_position <= 0.45
        if not bullish_breakout and not bearish_breakout:
            return None

        expansion_trigger = (
            range_expansion >= 1.5
            or height_ratio >= config.watch_height_ratio
            or range_burst >= 1.0
        )
        volume_trigger = volume_expansion >= 1.2 or volume_ratio >= 1.2 or volume_burst >= 0.75
        if not expansion_trigger or not volume_trigger:
            return None

        direction = "bullish" if bullish_breakout else "bearish"
        close_strength = close_position if bullish_breakout else 1 - close_position
        breakout_level = compression["box_high"] if bullish_breakout else compression["box_low"]
        distance = candidate.close - breakout_level if bullish_breakout else breakout_level - candidate.close
        atr = _atr(candles[max(0, candidate_index - 20) : candidate_index], period=14)
        if atr > 0 and distance > atr * 5:
            return None

        if height_ratio >= config.giant_height_ratio and volume_ratio >= config.giant_volume_ratio and body_strength >= config.directional_body_strength:
            phase = "giant_awakening"
        elif height_ratio >= config.pressure_height_ratio or range_expansion >= 2.0:
            phase = "pressure_building"
        else:
            phase = "watch"

        range_score = min(100.0, range_expansion / 3.0 * 100)
        volume_score = min(100.0, volume_expansion / 2.5 * 100)
        burst_score = min(100.0, max(range_burst, 0.0) / 3.0 * 100)
        close_score = close_strength * 100
        breakout_score = round(
            (range_score * 0.35)
            + (volume_score * 0.2)
            + (burst_score * 0.2)
            + (close_score * 0.15)
            + (compression["score"] * 0.1),
            2,
        )
        score = round(
            min(
                100.0,
                (breakout_score * 0.55)
                + (compression["score"] * 0.2)
                + (min(height_ratio / 3.0, 1.0) * 15)
                + (min(volume_ratio / 2.5, 1.0) * 10),
            ),
            2,
        )

        return SleepingGiantSetup(
            symbol=symbol,
            direction=direction,
            awakening_phase=phase,
            average_candle_size=round(average_candle_size, 8),
            latest_candle_size=round(candle_size, 8),
            median_candle_height_pct=round(median_height, 6),
            latest_candle_height_pct=round(candle_height, 6),
            height_ratio=round(height_ratio, 4),
            volume_ratio=round(volume_ratio, 4),
            body_strength=round(body_strength, 4),
            two_candle_pressure=round(height_ratio, 4),
            range_burst_score=round(range_burst, 4),
            volume_burst_score=round(volume_burst, 4),
            compression_score=round(compression["score"], 2),
            breakout_score=breakout_score,
            volume_expansion_ratio=round(volume_expansion, 4),
            range_expansion_ratio=round(range_expansion, 4),
            distance_from_box_breakout=round(distance, 8),
            current_price=candidate.close,
            timestamp=candidate.time,
            score=score,
            compression_candles=int(compression["candles"]),
            box_high=compression["box_high"],
            box_low=compression["box_low"],
            notes=[
                f"{config.timeframe} recent awakening watchlist only; not a buy/sell signal.",
                f"Legacy compression breakout: candle range is {range_expansion:.2f}x the recent box average and volume is {volume_expansion:.2f}x.",
                f"Compared with a {int(compression['candles'])}-candle compression box, not the strict 200-candle asleep rule.",
                f"Direction comes from a close outside the recent box with {body_strength:.0%} body strength.",
            ],
        )

    def _best_recent_box(self, candles: list[CandleLike], candidate_index: int) -> dict[str, float] | None:
        config = self._config
        baseline_start = max(0, candidate_index - config.baseline_candles)
        baseline_ranges = _true_ranges(candles[baseline_start:candidate_index])
        baseline_atr = mean(baseline_ranges) if baseline_ranges else 0.0
        best: dict[str, float] | None = None
        for window_size in range(config.compression_min_candles, config.compression_max_candles + 1):
            start = candidate_index - window_size
            if start < 0:
                continue
            window = candles[start:candidate_index]
            ranges = [max(candle.high - candle.low, 0.0) for candle in window]
            volumes = [max(candle.volume, 0.0) for candle in window]
            average_range = mean(ranges)
            average_volume = mean(volumes)
            if average_range <= 0:
                continue
            box_high = max(candle.high for candle in window)
            box_low = min(candle.low for candle in window)
            mid_price = max(mean(candle.close for candle in window), 1e-12)
            box_width_pct = ((box_high - box_low) / mid_price) * 100
            atr_ratio = _safe_divide(_atr(window), baseline_atr, default=1.0)
            body_ratio = _safe_divide(mean(abs(candle.close - candle.open) for candle in window), average_range)

            range_tightness = max(0.0, min(100.0, (1 - min(_safe_divide(average_range, mean(baseline_ranges), 1.0), 1.0)) * 100)) if baseline_ranges else 0.0
            atr_score = max(0.0, min(100.0, (1 - min(atr_ratio, 1.0)) * 100))
            body_score = max(0.0, min(100.0, (1 - min(body_ratio, 1.0)) * 100))
            box_score = max(0.0, 100.0 - min(box_width_pct * 8, 100.0))
            length_score = min(100.0, (window_size / config.compression_max_candles) * 100)
            score = round((range_tightness * 0.3) + (atr_score * 0.2) + (body_score * 0.2) + (box_score * 0.2) + (length_score * 0.1), 2)
            candidate = {
                "score": score,
                "candles": float(window_size),
                "average_range": average_range,
                "average_volume": average_volume,
                "box_high": box_high,
                "box_low": box_low,
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
        return best
