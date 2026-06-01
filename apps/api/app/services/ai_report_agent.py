from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import Settings
from .scoring import ScoredCoin


class AiReportAgent:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(
        self,
        run_at: datetime,
        top_active: list[ScoredCoin],
        top_bullish: list[ScoredCoin],
        top_bearish: list[ScoredCoin],
        top_buyers_left: list[ScoredCoin],
        top_dead_markets: list[ScoredCoin],
        top_quiet_rallies: list[ScoredCoin],
        watchlist: list[ScoredCoin],
    ) -> str:
        local_time = run_at.astimezone(ZoneInfo(self._settings.report_timezone))
        lines = [f"Market Radar narrative for {local_time:%Y-%m-%d %I:%M %p %Z}."]

        if top_active:
            leader = top_active[0]
            lines.append(
                f"{leader.symbol} is the activity leader with a {leader.volume_spike_ratio:.2f}x volume burst and "
                f"{leader.price_change_15m:+.2f}% over 15 minutes."
            )

        if top_bullish:
            bull = top_bullish[0]
            lines.append(
                f"{bull.symbol} is the strongest bullish setup: {bull.price_change_5m:+.2f}% in 5 minutes, "
                f"{bull.price_change_15m:+.2f}% in 15 minutes, and price is holding above both short EMAs."
            )

        if top_bearish:
            bear = top_bearish[0]
            lines.append(
                f"{bear.symbol} is the clearest bearish setup with downside pressure still supported by "
                f"{bear.volume_spike_ratio:.2f}x relative volume."
            )

        if top_buyers_left:
            weak_bid = top_buyers_left[0]
            lines.append(
                f"{weak_bid.symbol} also stands out for buyer exhaustion, with only "
                f"{weak_bid.buyer_volume_share * 100:.0f}% of recent volume landing on green candles."
            )

        if top_dead_markets:
            dead = top_dead_markets[0]
            lines.append(
                f"{dead.symbol} looks like a low-participation contract, with compressed range and a dead-market score "
                f"of {dead.dead_market_score:.1f}/100."
            )

        if top_quiet_rallies:
            coil = top_quiet_rallies[0]
            lines.append(
                f"{coil.symbol} best matches the quiet-then-rally pattern, waking up from a compressed base and then "
                f"printing repeated impulse legs with {coil.volume_spike_ratio:.2f}x relative volume and "
                f"{coil.price_change_15m:+.2f}% over 15 minutes."
            )

        stretched = [
            coin
            for coin in (top_active[:3] + top_quiet_rallies[:3] + watchlist[:3])
            if abs(coin.price_change_5m) >= 1.8 or coin.atr_percent >= 2.8
        ]
        if stretched:
            risk_names = ", ".join(coin.symbol for coin in stretched[:3])
            lines.append(
                f"Risk note: {risk_names} already look extended on a short horizon, so pullbacks or noisy follow-through "
                f"are more likely than clean continuation."
            )
        else:
            lines.append("Risk note: momentum is present, but no leading contract looks extremely overstretched yet.")

        return " ".join(lines)
