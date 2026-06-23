from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import SessionLocal
from .. import models
from .ai_report_agent import AiReportAgent
from .pionex_client import PionexClient, PionexClientError, PionexKline, PionexSymbolInfo, PionexTicker
from .pionex_chromium_scraper import PionexChromiumScraper, PionexChromiumScraperError
from .report_service import ReportService
from .scoring import ScoredCoin, ScoringService


@dataclass(slots=True)
class ScannerStatus:
    running: bool = False
    last_run_started_at: datetime | None = None
    last_run_completed_at: datetime | None = None
    last_error: str | None = None


class RadarScanner:
    def __init__(self, settings: Settings, client: PionexClient) -> None:
        self._settings = settings
        self._client = client
        self._lock = asyncio.Lock()
        self._status = ScannerStatus()
        self._scoring = ScoringService(
            activity_threshold=settings.activity_threshold,
            bullish_threshold=settings.bullish_threshold,
            bearish_threshold=settings.bearish_threshold,
            watchlist_threshold=settings.watchlist_threshold,
        )
        self._reports = ReportService(settings, AiReportAgent(settings))
        self._chromium_scraper = PionexChromiumScraper(settings)

    @property
    def status(self) -> ScannerStatus:
        return self._status

    async def run_scan(self, reason: str = "scheduled", raise_on_rate_limit: bool = False) -> models.Report | None:
        async with self._lock:
            self._status.running = True
            self._status.last_run_started_at = datetime.now(timezone.utc)
            self._status.last_error = None

            try:
                symbols, tickers = await self._load_market_board()
                open_interests = await self._load_open_interests_optional()
                ticker_map = {ticker.symbol: ticker for ticker in tickers}

                with SessionLocal() as db:
                    self._upsert_symbols(db, symbols)
                    market_symbols = self._select_market_universe(symbols, ticker_map)
                    scannable_symbols = self._select_universe(market_symbols, ticker_map)
                    previous_snapshots = self._load_previous_snapshots(db)

                candle_map = await self._fetch_klines(scannable_symbols)
                run_at = datetime.now(timezone.utc)

                scored_coins: list[ScoredCoin] = []
                snapshots = self._build_market_snapshots(market_symbols, ticker_map, open_interests, run_at)
                for symbol_info in scannable_symbols:
                    ticker = ticker_map.get(symbol_info.symbol)
                    candles = candle_map.get(symbol_info.symbol)
                    if not ticker or not candles or len(candles) < 20:
                        continue

                    previous_snapshot = previous_snapshots.get(symbol_info.symbol)
                    current_open_interest = open_interests.get(symbol_info.symbol, 0.0)
                    previous_open_interest = previous_snapshot.open_interest if previous_snapshot else 0.0

                    scored = self._scoring.score(
                        ticker=ticker,
                        open_interest=current_open_interest,
                        previous_open_interest=previous_open_interest,
                        candles=candles,
                    )
                    scored_coins.append(scored)

                if not scored_coins:
                    with SessionLocal() as db:
                        db.add_all(snapshots)
                        db.commit()
                    self._status.last_run_completed_at = datetime.now(timezone.utc)
                    return None

                report_payload = self._reports.build_report(run_at, scored_coins, reason)
                score_rows = [
                    models.CoinScore(
                        symbol=coin.symbol,
                        activity_score=coin.activity_score,
                        bullish_score=coin.bullish_score,
                        bearish_score=coin.bearish_score,
                        buyer_absence_score=coin.buyer_absence_score,
                        dead_market_score=coin.dead_market_score,
                        quiet_rally_score=coin.quiet_rally_score,
                        volume_spike_ratio=coin.volume_spike_ratio,
                        price_change_5m=coin.price_change_5m,
                        price_change_15m=coin.price_change_15m,
                        atr_percent=coin.atr_percent,
                        open_interest_change_pct=coin.open_interest_change_pct,
                        buyer_volume_share=coin.buyer_volume_share,
                        green_candle_ratio=coin.green_candle_ratio,
                        trend_label=coin.trend_label,
                        score_breakdown_json=coin.breakdown,
                        report_time=run_at,
                    )
                    for coin in scored_coins
                ]

                with SessionLocal() as db:
                    db.add_all(snapshots)
                    db.add_all(score_rows)
                    report = models.Report(
                        title=report_payload["title"],
                        summary=report_payload["summary"],
                        top_active_json=report_payload["top_active"],
                        top_bullish_json=report_payload["top_bullish"],
                        top_bearish_json=report_payload["top_bearish"],
                        top_buyers_left_json=report_payload["top_buyers_left"],
                        top_dead_markets_json=report_payload["top_dead_markets"],
                        top_quiet_rallies_json=report_payload["top_quiet_rallies"],
                        watchlist_json=report_payload["watchlist"],
                        ai_commentary=report_payload["ai_commentary"],
                        scan_reason=report_payload["scan_reason"],
                        created_at=report_payload["created_at"],
                    )
                    db.add(report)
                    db.commit()
                    db.refresh(report)

                self._status.last_run_completed_at = datetime.now(timezone.utc)
                return report
            except PionexClientError as exc:
                self._status.last_error = str(exc)
                if exc.is_rate_limited and not raise_on_rate_limit:
                    return None
                raise
            except Exception as exc:
                self._status.last_error = str(exc)
                raise
            finally:
                self._status.running = False

    def _upsert_symbols(self, db: Session, symbols: list[PionexSymbolInfo]) -> None:
        existing = {
            row.symbol: row
            for row in db.scalars(select(models.Symbol)).all()
        }
        for symbol in symbols:
            current = existing.get(symbol.symbol)
            if current:
                current.name = symbol.name
                current.base_asset = symbol.base_currency
                current.quote_asset = symbol.quote_currency
                current.market_type = symbol.market_type
                current.status = symbol.status
            else:
                db.add(
                    models.Symbol(
                        symbol=symbol.symbol,
                        name=symbol.name,
                        base_asset=symbol.base_currency,
                        quote_asset=symbol.quote_currency,
                        market_type=symbol.market_type,
                        status=symbol.status,
                    )
                )
        db.commit()

    async def _load_symbols_with_cache_fallback(self) -> list[PionexSymbolInfo]:
        try:
            return await self._client.get_symbols()
        except PionexClientError:
            with SessionLocal() as db:
                cached_symbols = db.scalars(select(models.Symbol)).all()
                if not cached_symbols:
                    raise
                return [
                    PionexSymbolInfo(
                        symbol=row.symbol,
                        name=row.name,
                        base_currency=row.base_asset,
                        quote_currency=row.quote_asset,
                        market_type=row.market_type,
                        status=row.status,
                    )
                    for row in cached_symbols
                ]

    async def _load_open_interests_optional(self) -> dict[str, float]:
        try:
            return await self._client.get_open_interests()
        except PionexClientError:
            return {}

    async def _load_market_board(self) -> tuple[list[PionexSymbolInfo], list[PionexTicker]]:
        if self._settings.market_data_source.lower() in {"chromium", "pionex_chromium"}:
            try:
                scraped = await self._chromium_scraper.scrape_futures_movers()
                return scraped.symbols, scraped.tickers
            except PionexChromiumScraperError:
                pass

        symbols = await self._load_symbols_with_cache_fallback()
        tickers = await self._load_tickers_with_fallback(symbols)
        return symbols, tickers

    async def _load_tickers_with_fallback(self, symbols: list[PionexSymbolInfo]) -> list[PionexTicker]:
        try:
            return await self._client.get_tickers()
        except PionexClientError as exc:
            if not exc.is_rate_limited:
                raise

        semaphore = asyncio.Semaphore(max(1, min(4, self._settings.pionex_max_concurrent_requests)))
        cached_symbols = [
            symbol
            for symbol in symbols
            if symbol.status == "TRADING" and symbol.quote_currency.upper() in self._settings.quote_assets
        ]

        async def fetch_one(index: int, symbol: PionexSymbolInfo) -> PionexTicker | None:
            async with semaphore:
                await asyncio.sleep(index * 0.08)
                try:
                    return await self._client.get_ticker(symbol.symbol)
                except PionexClientError:
                    return None

        results = await asyncio.gather(*(fetch_one(index, symbol) for index, symbol in enumerate(cached_symbols)))
        tickers = [ticker for ticker in results if ticker is not None]
        if not tickers:
            raise PionexClientError(
                "Pionex ticker refresh failed: all-market and symbol-by-symbol fallback were rate-limited.",
                status_code=429,
            )
        return tickers

    def _select_universe(
        self,
        symbols: list[PionexSymbolInfo],
        ticker_map: dict[str, PionexTicker],
    ) -> list[PionexSymbolInfo]:
        liquid_symbols = [
            symbol
            for symbol in symbols
            if symbol.status == "TRADING"
            and symbol.quote_currency.upper() in self._settings.quote_assets
            and ticker_map.get(symbol.symbol)
            and ticker_map[symbol.symbol].amount >= self._settings.scanner_min_quote_volume
        ]
        liquid_symbols.sort(key=lambda symbol: ticker_map[symbol.symbol].amount, reverse=True)
        return liquid_symbols[: self._settings.scanner_max_symbols]

    def _select_market_universe(
        self,
        symbols: list[PionexSymbolInfo],
        ticker_map: dict[str, PionexTicker],
    ) -> list[PionexSymbolInfo]:
        market_symbols = [
            symbol
            for symbol in symbols
            if symbol.status == "TRADING"
            and symbol.quote_currency.upper() in self._settings.quote_assets
            and ticker_map.get(symbol.symbol)
        ]
        market_symbols.sort(key=lambda symbol: ticker_map[symbol.symbol].price_change_24h, reverse=True)
        return market_symbols

    def _build_market_snapshots(
        self,
        symbols: list[PionexSymbolInfo],
        ticker_map: dict[str, PionexTicker],
        open_interests: dict[str, float],
        run_at: datetime,
    ) -> list[models.MarketSnapshot]:
        snapshots: list[models.MarketSnapshot] = []
        for symbol_info in symbols:
            ticker = ticker_map.get(symbol_info.symbol)
            if ticker is None:
                continue
            snapshots.append(
                models.MarketSnapshot(
                    symbol=symbol_info.symbol,
                    price=ticker.close,
                    price_change_24h=ticker.price_change_24h,
                    volume_24h=ticker.volume,
                    quote_volume_24h=ticker.amount,
                    high_24h=ticker.high,
                    low_24h=ticker.low,
                    open_interest=open_interests.get(symbol_info.symbol, 0.0),
                    timestamp=run_at,
                )
            )
        return snapshots

    def _load_previous_snapshots(self, db: Session) -> dict[str, models.MarketSnapshot]:
        latest_snapshot_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        if latest_snapshot_time is None:
            return {}
        return {
            snapshot.symbol: snapshot
            for snapshot in db.scalars(
                select(models.MarketSnapshot).where(models.MarketSnapshot.timestamp == latest_snapshot_time)
            ).all()
        }

    async def _fetch_klines(self, symbols: list[PionexSymbolInfo]) -> dict[str, list[PionexKline]]:
        semaphore = asyncio.Semaphore(self._settings.pionex_max_concurrent_requests)

        async def fetch(symbol: PionexSymbolInfo) -> tuple[str, list[PionexKline] | None]:
            async with semaphore:
                try:
                    candles = await self._client.get_klines(
                        symbol=symbol.symbol,
                        interval="1M",
                        limit=self._settings.scanner_kline_limit,
                    )
                    return symbol.symbol, candles
                except PionexClientError:
                    return symbol.symbol, None

        results = await asyncio.gather(*(fetch(symbol) for symbol in symbols))
        return {symbol: candles for symbol, candles in results if candles}
