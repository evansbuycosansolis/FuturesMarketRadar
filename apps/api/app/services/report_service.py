from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import Settings
from ..models import CoinScore, MarketSnapshot, Report
from ..schemas import ReportRead, ScoreEntry
from .ai_report_agent import AiReportAgent
from .scoring import ScoredCoin


def score_to_entry(score: ScoredCoin) -> dict:
    return {
        "symbol": score.symbol,
        "price": score.price,
        "price_change_24h": score.price_change_24h,
        "volume_24h": score.volume_24h,
        "quote_volume_24h": score.quote_volume_24h,
        "high_24h": score.high_24h,
        "low_24h": score.low_24h,
        "open_interest": score.open_interest,
        "open_interest_change_pct": score.open_interest_change_pct,
        "activity_score": score.activity_score,
        "bullish_score": score.bullish_score,
        "bearish_score": score.bearish_score,
        "buyer_absence_score": score.buyer_absence_score,
        "dead_market_score": score.dead_market_score,
        "quiet_rally_score": score.quiet_rally_score,
        "volume_spike_ratio": score.volume_spike_ratio,
        "price_change_5m": score.price_change_5m,
        "price_change_15m": score.price_change_15m,
        "atr_percent": score.atr_percent,
        "buyer_volume_share": score.buyer_volume_share,
        "green_candle_ratio": score.green_candle_ratio,
        "trend_label": score.trend_label,
        "breakdown": score.breakdown,
    }


def models_to_score_entry(score: CoinScore, snapshot: MarketSnapshot | None) -> ScoreEntry:
    return ScoreEntry(
        symbol=score.symbol,
        price=snapshot.price if snapshot else 0.0,
        price_change_24h=snapshot.price_change_24h if snapshot else 0.0,
        volume_24h=snapshot.volume_24h if snapshot else 0.0,
        quote_volume_24h=snapshot.quote_volume_24h if snapshot else 0.0,
        high_24h=snapshot.high_24h if snapshot else 0.0,
        low_24h=snapshot.low_24h if snapshot else 0.0,
        open_interest=snapshot.open_interest if snapshot else 0.0,
        open_interest_change_pct=score.open_interest_change_pct,
        activity_score=score.activity_score,
        bullish_score=score.bullish_score,
        bearish_score=score.bearish_score,
        buyer_absence_score=score.buyer_absence_score or 0.0,
        dead_market_score=score.dead_market_score or 0.0,
        quiet_rally_score=score.quiet_rally_score or 0.0,
        volume_spike_ratio=score.volume_spike_ratio,
        price_change_5m=score.price_change_5m,
        price_change_15m=score.price_change_15m,
        atr_percent=score.atr_percent,
        buyer_volume_share=score.buyer_volume_share or 0.0,
        green_candle_ratio=score.green_candle_ratio or 0.0,
        trend_label=score.trend_label,
        breakdown=score.score_breakdown_json or {},
    )


class ReportService:
    def __init__(self, settings: Settings, ai_report_agent: AiReportAgent) -> None:
        self._settings = settings
        self._ai_report_agent = ai_report_agent

    def build_report(self, run_at: datetime, scored_coins: list[ScoredCoin], reason: str) -> dict:
        top_active = sorted(
            scored_coins,
            key=lambda coin: (coin.activity_score, coin.volume_spike_ratio, abs(coin.price_change_15m)),
            reverse=True,
        )[:10]
        top_bullish = sorted(
            scored_coins,
            key=lambda coin: (coin.bullish_score, coin.activity_score, coin.price_change_15m),
            reverse=True,
        )[:10]
        top_bearish = sorted(
            scored_coins,
            key=lambda coin: (coin.bearish_score, coin.activity_score, -coin.price_change_15m),
            reverse=True,
        )[:10]
        top_buyers_left = sorted(
            scored_coins,
            key=lambda coin: (coin.buyer_absence_score, coin.bearish_score, -coin.buyer_volume_share),
            reverse=True,
        )[:10]
        top_dead_markets = sorted(
            scored_coins,
            key=lambda coin: (coin.dead_market_score, -coin.activity_score, -abs(coin.price_change_15m)),
            reverse=True,
        )[:10]
        top_quiet_rallies = sorted(
            scored_coins,
            key=lambda coin: (coin.quiet_rally_score, coin.bullish_score, coin.volume_spike_ratio, coin.price_change_15m),
            reverse=True,
        )[:10]

        excluded = {
            coin.symbol
            for coin in top_active[:4] + top_bullish[:4] + top_bearish[:4] + top_buyers_left[:3] + top_quiet_rallies[:3]
        }
        watchlist = [
            coin
            for coin in sorted(
                scored_coins,
                key=lambda coin: (
                    max(coin.activity_score, coin.bullish_score, coin.bearish_score, coin.quiet_rally_score),
                    coin.volume_spike_ratio,
                ),
                reverse=True,
            )
            if coin.symbol not in excluded and "Watchlist" in coin.trend_label
        ][:10]

        local_time = run_at.astimezone(ZoneInfo(self._settings.report_timezone))
        title = f"Market Radar Report — {local_time:%b %d, %Y %I:%M %p %Z}"
        summary = self._summary(
            scored_coins,
            top_active,
            top_bullish,
            top_bearish,
            top_buyers_left,
            top_dead_markets,
            top_quiet_rallies,
            watchlist,
        )
        commentary = self._ai_report_agent.generate(
            run_at,
            top_active,
            top_bullish,
            top_bearish,
            top_buyers_left,
            top_dead_markets,
            top_quiet_rallies,
            watchlist,
        )

        return {
            "title": title,
            "summary": summary,
            "top_active": [score_to_entry(coin) for coin in top_active],
            "top_bullish": [score_to_entry(coin) for coin in top_bullish],
            "top_bearish": [score_to_entry(coin) for coin in top_bearish],
            "top_buyers_left": [score_to_entry(coin) for coin in top_buyers_left],
            "top_dead_markets": [score_to_entry(coin) for coin in top_dead_markets],
            "top_quiet_rallies": [score_to_entry(coin) for coin in top_quiet_rallies],
            "watchlist": [score_to_entry(coin) for coin in watchlist],
            "ai_commentary": commentary,
            "scan_reason": reason,
            "created_at": run_at,
        }

    def _summary(
        self,
        scored_coins: list[ScoredCoin],
        top_active: list[ScoredCoin],
        top_bullish: list[ScoredCoin],
        top_bearish: list[ScoredCoin],
        top_buyers_left: list[ScoredCoin],
        top_dead_markets: list[ScoredCoin],
        top_quiet_rallies: list[ScoredCoin],
        watchlist: list[ScoredCoin],
    ) -> str:
        parts = [f"Scanned {len(scored_coins)} liquid futures contracts."]
        if top_active:
            active = top_active[0]
            parts.append(
                f"{active.symbol} is the most active contract at {active.activity_score:.1f}/100 with "
                f"{active.volume_spike_ratio:.2f}x relative volume."
            )
        if top_bullish:
            bullish = top_bullish[0]
            parts.append(
                f"{bullish.symbol} leads the bullish list at {bullish.bullish_score:.1f}/100 and "
                f"{bullish.price_change_15m:+.2f}% over the last 15 minutes."
            )
        if top_bearish:
            bearish = top_bearish[0]
            parts.append(
                f"{bearish.symbol} leads the bearish list at {bearish.bearish_score:.1f}/100 with "
                f"{bearish.price_change_15m:+.2f}% over 15 minutes."
            )
        if top_buyers_left:
            weak_bid = top_buyers_left[0]
            parts.append(
                f"{weak_bid.symbol} is the clearest weak-bid contract with a buyer-absence score of "
                f"{weak_bid.buyer_absence_score:.1f}/100."
            )
        if top_dead_markets:
            dead = top_dead_markets[0]
            parts.append(
                f"{dead.symbol} is the quietest contract at {dead.dead_market_score:.1f}/100 dead-market score."
            )
        if top_quiet_rallies:
            coil = top_quiet_rallies[0]
            parts.append(
                f"{coil.symbol} best fits the quiet-then-rally pattern at {coil.quiet_rally_score:.1f}/100 after a "
                f"silent base and {coil.price_change_15m:+.2f}% over 15 minutes."
            )
        if watchlist:
            watch_names = ", ".join(coin.symbol for coin in watchlist[:3])
            parts.append(f"Watchlist names worth monitoring next: {watch_names}.")
        return " ".join(parts)

    def as_report_schema(self, report: Report) -> ReportRead:
        return ReportRead(
            id=report.id,
            title=report.title,
            summary=report.summary,
            top_active=[ScoreEntry.model_validate(item) for item in report.top_active_json or []],
            top_bullish=[ScoreEntry.model_validate(item) for item in report.top_bullish_json or []],
            top_bearish=[ScoreEntry.model_validate(item) for item in report.top_bearish_json or []],
            top_buyers_left=[ScoreEntry.model_validate(item) for item in report.top_buyers_left_json or []],
            top_dead_markets=[ScoreEntry.model_validate(item) for item in report.top_dead_markets_json or []],
            top_quiet_rallies=[ScoreEntry.model_validate(item) for item in report.top_quiet_rallies_json or []],
            watchlist=[ScoreEntry.model_validate(item) for item in report.watchlist_json or []],
            ai_commentary=report.ai_commentary,
            scan_reason=report.scan_reason,
            created_at=report.created_at,
        )
