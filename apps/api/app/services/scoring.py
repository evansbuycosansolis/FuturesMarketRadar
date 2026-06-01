from __future__ import annotations

from dataclasses import dataclass

from .pionex_client import PionexKline, PionexTicker


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def scaled_score(value: float, lower: float, upper: float, points: float) -> float:
    if value <= lower:
        return 0.0
    if value >= upper:
        return points
    return ((value - lower) / (upper - lower)) * points


def reverse_scaled_score(value: float, lower: float, upper: float, points: float) -> float:
    if value <= lower:
        return points
    if value >= upper:
        return 0.0
    return ((upper - value) / (upper - lower)) * points


def pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = (value * alpha) + (result * (1 - alpha))
    return result


def atr_percent(candles: list[PionexKline], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges: list[float] = []
    for index in range(1, len(candles)):
        current = candles[index]
        previous = candles[index - 1]
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    if not true_ranges:
        return 0.0
    recent = true_ranges[-period:]
    average_tr = sum(recent) / len(recent)
    close = candles[-1].close or 1.0
    return (average_tr / close) * 100


def candle_close_position(candle: PionexKline) -> float:
    spread = candle.high - candle.low
    if spread <= 0:
        return 0.5
    return (candle.close - candle.low) / spread


def volume_spike_ratio(candles: list[PionexKline]) -> float:
    if len(candles) < 25:
        return 1.0
    recent = candles[-5:]
    baseline = candles[-25:-5]
    recent_volume = sum(candle.volume for candle in recent)
    baseline_windows = [
        sum(candle.volume for candle in baseline[index : index + 5])
        for index in range(0, len(baseline), 5)
        if len(baseline[index : index + 5]) == 5
    ]
    baseline_average = sum(baseline_windows) / max(len(baseline_windows), 1)
    if baseline_average <= 0:
        return 1.0
    return recent_volume / baseline_average


def recent_range_percent(candles: list[PionexKline], window: int = 15) -> float:
    recent = candles[-window:] if len(candles) >= window else candles
    if not recent:
        return 0.0
    high = max(candle.high for candle in recent)
    low = min(candle.low for candle in recent)
    close = recent[-1].close or 1.0
    return ((high - low) / close) * 100


def split_quiet_and_recent_windows(
    candles: list[PionexKline],
    quiet_window: int = 60,
    recent_window: int = 30,
) -> tuple[list[PionexKline], list[PionexKline]]:
    if not candles:
        return [], []
    recent_size = min(recent_window, max(12, len(candles) // 4))
    recent = candles[-recent_size:]
    quiet_pool = candles[:-recent_size]
    if not quiet_pool:
        return candles[:-1], candles[-1:]
    quiet_size = min(quiet_window, max(24, len(quiet_pool) // 2))
    quiet = quiet_pool[-quiet_size:]
    return quiet, recent


def average_candle_range_percent(candles: list[PionexKline]) -> float:
    if not candles:
        return 0.0
    return sum(((candle.high - candle.low) / (candle.close or 1.0)) * 100 for candle in candles) / len(candles)


def expansion_candle_ratio(
    candles: list[PionexKline],
    baseline_range_percent: float,
    multiplier: float = 1.8,
) -> float:
    if not candles:
        return 0.0
    threshold = max(baseline_range_percent * multiplier, 0.08)
    expansion_candles = sum(
        1
        for candle in candles
        if ((candle.high - candle.low) / (candle.close or 1.0)) * 100 >= threshold and candle.close >= candle.open
    )
    return expansion_candles / len(candles)


def positive_leg_ratio(candles: list[PionexKline], leg_size: int = 5, threshold_pct: float = 0.35) -> float:
    if len(candles) < leg_size:
        return 0.0
    windows = [
        candles[index : index + leg_size]
        for index in range(0, len(candles), leg_size)
        if len(candles[index : index + leg_size]) == leg_size
    ]
    if not windows:
        return 0.0
    positive_legs = sum(
        1
        for window in windows
        if pct_change(window[-1].close, window[0].open) >= threshold_pct and window[-1].close >= window[0].open
    )
    return positive_legs / len(windows)


def post_breakout_hold_ratio(candles: list[PionexKline], breakout_level: float, min_breakout_pct: float = 0.10) -> float:
    if not candles or breakout_level <= 0:
        return 0.0
    trigger_level = breakout_level * (1 + (min_breakout_pct / 100))
    breakout_index = next((index for index, candle in enumerate(candles) if candle.close >= trigger_level), None)
    if breakout_index is None:
        return 0.0
    post_breakout = candles[breakout_index:]
    if not post_breakout:
        return 0.0
    hold_floor = breakout_level * 0.995
    holds = sum(1 for candle in post_breakout if candle.close >= hold_floor)
    return holds / len(post_breakout)


def buyer_volume_share(candles: list[PionexKline], window: int = 15) -> float:
    recent = candles[-window:] if len(candles) >= window else candles
    total_volume = sum(candle.volume for candle in recent)
    if total_volume <= 0:
        return 0.5
    buyer_volume = sum(candle.volume for candle in recent if candle.close >= candle.open)
    return buyer_volume / total_volume


def green_candle_ratio(candles: list[PionexKline], window: int = 15) -> float:
    recent = candles[-window:] if len(candles) >= window else candles
    if not recent:
        return 0.5
    green_candles = sum(1 for candle in recent if candle.close >= candle.open)
    return green_candles / len(recent)


def red_to_green_volume_ratio(candles: list[PionexKline], window: int = 15) -> float:
    recent = candles[-window:] if len(candles) >= window else candles
    green_volume = sum(candle.volume for candle in recent if candle.close >= candle.open)
    red_volume = sum(candle.volume for candle in recent if candle.close < candle.open)
    if green_volume <= 0:
        return red_volume if red_volume > 0 else 1.0
    return red_volume / green_volume


def close_near_low_ratio(candles: list[PionexKline], window: int = 8, threshold: float = 0.35) -> float:
    recent = candles[-window:] if len(candles) >= window else candles
    if not recent:
        return 0.0
    weak_closes = sum(1 for candle in recent if candle_close_position(candle) <= threshold)
    return weak_closes / len(recent)


def descending_high_ratio(candles: list[PionexKline], window: int = 6) -> float:
    recent = candles[-window:] if len(candles) >= window else candles
    if len(recent) < 2:
        return 0.0
    descending_pairs = sum(1 for index in range(1, len(recent)) if recent[index].high <= recent[index - 1].high)
    return descending_pairs / (len(recent) - 1)


@dataclass(slots=True)
class ScoredCoin:
    symbol: str
    price: float
    price_change_24h: float
    volume_24h: float
    quote_volume_24h: float
    high_24h: float
    low_24h: float
    open_interest: float
    open_interest_change_pct: float
    activity_score: float
    bullish_score: float
    bearish_score: float
    buyer_absence_score: float
    dead_market_score: float
    quiet_rally_score: float
    volume_spike_ratio: float
    price_change_5m: float
    price_change_15m: float
    atr_percent: float
    buyer_volume_share: float
    green_candle_ratio: float
    trend_label: str
    breakdown: dict[str, dict[str, float]]


class ScoringService:
    def __init__(
        self,
        activity_threshold: float,
        bullish_threshold: float,
        bearish_threshold: float,
        watchlist_threshold: float,
    ) -> None:
        self._activity_threshold = activity_threshold
        self._bullish_threshold = bullish_threshold
        self._bearish_threshold = bearish_threshold
        self._watchlist_threshold = watchlist_threshold

    def score(
        self,
        ticker: PionexTicker,
        open_interest: float,
        previous_open_interest: float,
        candles: list[PionexKline],
    ) -> ScoredCoin:
        closes = [candle.close for candle in candles]
        latest = candles[-1]
        volume_ratio = volume_spike_ratio(candles)
        change_5m = pct_change(closes[-1], closes[-6]) if len(closes) >= 6 else pct_change(closes[-1], closes[0])
        change_15m = pct_change(closes[-1], closes[-16]) if len(closes) >= 16 else pct_change(closes[-1], closes[0])
        atr_pct = atr_percent(candles)
        recent_range_pct = recent_range_percent(candles)
        ema20 = ema(closes[-20:] if len(closes) >= 20 else closes, 20)
        ema50 = ema(closes[-50:] if len(closes) >= 50 else closes, 50)
        oi_change_pct = pct_change(open_interest, previous_open_interest) if previous_open_interest else 0.0
        close_pos = candle_close_position(latest)
        buyer_share = buyer_volume_share(candles)
        green_ratio = green_candle_ratio(candles)
        red_green_ratio = red_to_green_volume_ratio(candles)
        close_low_ratio = close_near_low_ratio(candles)
        lower_high_ratio = descending_high_ratio(candles)
        quiet_candles, recent_candles = split_quiet_and_recent_windows(candles)
        quiet_atr_pct = atr_percent(quiet_candles)
        quiet_range_pct = recent_range_percent(quiet_candles, window=len(quiet_candles))
        recent_window_range_pct = recent_range_percent(recent_candles, window=len(recent_candles))
        range_expansion_ratio = recent_window_range_pct / max(quiet_range_pct, 0.05)
        quiet_high = max((candle.high for candle in quiet_candles), default=ticker.close)
        breakout_pct = max(pct_change(ticker.close, quiet_high), 0.0)
        quiet_avg_volume = sum(candle.volume for candle in quiet_candles) / max(len(quiet_candles), 1)
        recent_avg_volume = sum(candle.volume for candle in recent_candles) / max(len(recent_candles), 1)
        volume_ignition_ratio = recent_avg_volume / quiet_avg_volume if quiet_avg_volume > 0 else 1.0
        quiet_avg_range_pct = average_candle_range_percent(quiet_candles)
        spike_ratio = expansion_candle_ratio(recent_candles, quiet_avg_range_pct)
        leg_ratio = positive_leg_ratio(recent_candles)
        hold_ratio = post_breakout_hold_ratio(recent_candles, quiet_high)
        quiet_average_close = sum(candle.close for candle in quiet_candles) / max(len(quiet_candles), 1)
        launch_distance_pct = max(pct_change(ticker.close, quiet_average_close), 0.0)
        follow_through_strength = clamp(
            (
                (1.0 if change_5m > 0 else 0.0)
                + (1.0 if change_15m > 0 else 0.0)
                + (1.0 if ticker.close > ema20 else 0.0)
                + (1.0 if close_pos >= 0.70 else 0.0)
                + green_ratio
            )
            / 5.0,
            0.0,
            1.0,
        )
        ema_failure_strength = clamp(
            (
                (1.0 if ticker.close < ema20 else 0.0)
                + (1.0 if ticker.close < ema50 else 0.0)
                + lower_high_ratio
            )
            / 3.0,
            0.0,
            1.0,
        )

        activity_parts = {
            "volume_spike": round(scaled_score(volume_ratio, 1.1, 3.5, 35.0), 2),
            "price_move_5m": round(scaled_score(abs(change_5m), 0.20, 2.50, 20.0), 2),
            "price_move_15m": round(scaled_score(abs(change_15m), 0.40, 4.20, 15.0), 2),
            "atr_volatility": round(scaled_score(atr_pct, 0.15, 3.20, 15.0), 2),
            "open_interest_change": round(scaled_score(abs(oi_change_pct), 0.50, 10.0, 15.0), 2),
        }
        bullish_parts = {
            "price_change_5m": round(scaled_score(max(change_5m, 0.0), 0.05, 1.50, 20.0), 2),
            "price_change_15m": round(scaled_score(max(change_15m, 0.0), 0.10, 3.00, 20.0), 2),
            "above_ema20": 15.0 if ticker.close > ema20 else 0.0,
            "above_ema50": 15.0 if ticker.close > ema50 else 0.0,
            "volume_spike": round(scaled_score(volume_ratio, 1.1, 3.0, 15.0), 2),
            "open_interest_rising": round(scaled_score(max(oi_change_pct, 0.0), 0.50, 8.0, 10.0), 2),
            "strong_close": round(5.0 if latest.close > latest.open and close_pos >= 0.75 else 0.0, 2),
        }
        bearish_parts = {
            "price_change_5m": round(scaled_score(max(-change_5m, 0.0), 0.05, 1.50, 20.0), 2),
            "price_change_15m": round(scaled_score(max(-change_15m, 0.0), 0.10, 3.00, 20.0), 2),
            "below_ema20": 15.0 if ticker.close < ema20 else 0.0,
            "below_ema50": 15.0 if ticker.close < ema50 else 0.0,
            "volume_spike": round(scaled_score(volume_ratio, 1.1, 3.0, 15.0), 2),
            "open_interest_rising": round(
                scaled_score(max(oi_change_pct if change_5m < 0 else 0.0, 0.0), 0.50, 8.0, 10.0),
                2,
            ),
            "strong_close": round(5.0 if latest.close < latest.open and close_pos <= 0.25 else 0.0, 2),
        }
        buyer_absence_parts = {
            "buyer_volume_share_low": round(reverse_scaled_score(buyer_share, 0.22, 0.55, 25.0), 2),
            "red_over_green_volume": round(scaled_score(red_green_ratio, 1.10, 3.20, 20.0), 2),
            "close_near_low_ratio": round(scaled_score(close_low_ratio, 0.25, 0.85, 15.0), 2),
            "failed_ema_reclaim": round(ema_failure_strength * 15.0, 2),
            "open_interest_pressure": round(
                scaled_score(abs(oi_change_pct), 0.25, 8.0, 15.0) if change_15m < 0 else 0.0,
                2,
            ),
            "green_candle_absence": round(reverse_scaled_score(green_ratio, 0.20, 0.55, 10.0), 2),
        }
        dead_market_parts = {
            "move_absent": round(reverse_scaled_score(abs(change_15m), 0.08, 1.00, 20.0), 2),
            "atr_compression": round(reverse_scaled_score(atr_pct, 0.10, 0.90, 25.0), 2),
            "volume_dryness": round(reverse_scaled_score(volume_ratio, 0.75, 1.15, 25.0), 2),
            "open_interest_flat": round(reverse_scaled_score(abs(oi_change_pct), 0.10, 2.0, 15.0), 2),
            "range_compression": round(reverse_scaled_score(recent_range_pct, 0.12, 1.25, 15.0), 2),
        }
        quiet_rally_parts = {
            "quiet_atr_compression": round(reverse_scaled_score(quiet_atr_pct, 0.10, 0.55, 15.0), 2),
            "quiet_range_compression": round(reverse_scaled_score(quiet_range_pct, 0.15, 1.50, 10.0), 2),
            "range_expansion": round(scaled_score(range_expansion_ratio, 1.35, 4.00, 10.0), 2),
            "breakout_above_quiet_high": round(scaled_score(breakout_pct, 0.05, 2.50, 15.0), 2),
            "volume_ignition": round(scaled_score(volume_ignition_ratio, 1.15, 4.00, 15.0), 2),
            "spike_cluster": round(scaled_score(spike_ratio, 0.10, 0.60, 10.0), 2),
            "rally_leg_persistence": round(scaled_score(leg_ratio, 0.20, 0.80, 10.0), 2),
            "breakout_hold": round(scaled_score(hold_ratio, 0.35, 0.95, 5.0), 2),
            "launch_distance": round(scaled_score(launch_distance_pct, 0.35, 4.50, 5.0), 2),
            "bullish_follow_through": round(follow_through_strength * 5.0, 2),
        }

        activity_score = round(sum(activity_parts.values()), 2)
        bullish_score = round(sum(bullish_parts.values()), 2)
        bearish_score = round(sum(bearish_parts.values()), 2)
        buyer_absence_score = round(sum(buyer_absence_parts.values()), 2)
        dead_market_score = round(sum(dead_market_parts.values()), 2)
        quiet_rally_score = round(sum(quiet_rally_parts.values()), 2)

        trend_label = self._label_trend(
            activity_score=activity_score,
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            buyer_absence_score=buyer_absence_score,
            dead_market_score=dead_market_score,
            quiet_rally_score=quiet_rally_score,
        )
        breakdown = {
            "activity": activity_parts,
            "bullish": bullish_parts,
            "bearish": bearish_parts,
            "buyer_absence": buyer_absence_parts,
            "dead_market": dead_market_parts,
            "quiet_rally": quiet_rally_parts,
        }

        return ScoredCoin(
            symbol=ticker.symbol,
            price=round(ticker.close, 8),
            price_change_24h=round(ticker.price_change_24h, 4),
            volume_24h=round(ticker.volume, 8),
            quote_volume_24h=round(ticker.amount, 8),
            high_24h=round(ticker.high, 8),
            low_24h=round(ticker.low, 8),
            open_interest=round(open_interest, 8),
            open_interest_change_pct=round(oi_change_pct, 4),
            activity_score=activity_score,
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            buyer_absence_score=buyer_absence_score,
            dead_market_score=dead_market_score,
            quiet_rally_score=quiet_rally_score,
            volume_spike_ratio=round(volume_ratio, 4),
            price_change_5m=round(change_5m, 4),
            price_change_15m=round(change_15m, 4),
            atr_percent=round(atr_pct, 4),
            buyer_volume_share=round(buyer_share, 4),
            green_candle_ratio=round(green_ratio, 4),
            trend_label=trend_label,
            breakdown=breakdown,
        )

    def _label_trend(
        self,
        activity_score: float,
        bullish_score: float,
        bearish_score: float,
        buyer_absence_score: float,
        dead_market_score: float,
        quiet_rally_score: float,
    ) -> str:
        if dead_market_score >= 72.0 and activity_score < self._watchlist_threshold and abs(bullish_score - bearish_score) < 18.0:
            return "Dead Market"
        if (
            quiet_rally_score >= 60.0
            and bullish_score >= max(self._watchlist_threshold + 2.0, bearish_score + 4.0)
        ):
            return "Quiet Then Rally"
        if buyer_absence_score >= 74.0 and bearish_score >= bullish_score + 5.0:
            return "Buyers Left"
        if buyer_absence_score >= 60.0 and bearish_score >= bullish_score:
            return "Weak Bid"
        if activity_score >= self._activity_threshold:
            if bullish_score >= self._bullish_threshold and bullish_score >= bearish_score + 7:
                return "Suddenly Bullish"
            if bearish_score >= self._bearish_threshold and bearish_score >= bullish_score + 7:
                return "Suddenly Bearish"
            return "Suddenly Active"

        if bullish_score >= self._watchlist_threshold and bullish_score >= bearish_score + 5:
            return "Bullish Watchlist"
        if quiet_rally_score >= 48.0 and bullish_score >= bearish_score + 2:
            return "Coiled Watchlist"
        if bearish_score >= self._watchlist_threshold and bearish_score >= bullish_score + 5:
            return "Bearish Watchlist"
        if activity_score >= self._watchlist_threshold:
            return "Watchlist"
        return "Quiet"
