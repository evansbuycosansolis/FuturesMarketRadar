from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from .pionex_client import PionexKline, to_float


class BinanceFuturesClientError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BinanceFuturesSymbol:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    contract_type: str


_SYMBOL_CACHE: tuple[float, set[str]] = (0.0, set())
_SYMBOL_CACHE_TTL_SECONDS = 60 * 60


def pionex_perp_to_binance_symbol(symbol: str) -> str:
    return symbol.upper().replace("_USDT_PERP", "USDT").replace("_", "")


class BinanceFuturesClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.binance_base_url.rstrip("/"),
            timeout=settings.binance_timeout_seconds,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise BinanceFuturesClientError(f"Binance Futures request failed for {path}: {exc}") from exc

    async def get_usdt_perpetual_symbols(self) -> set[str]:
        global _SYMBOL_CACHE
        cached_at, cached_symbols = _SYMBOL_CACHE
        if cached_symbols and time.time() - cached_at < _SYMBOL_CACHE_TTL_SECONDS:
            return cached_symbols

        data = await self._get("/fapi/v1/exchangeInfo")
        symbols = {
            item.get("symbol", "")
            for item in data.get("symbols", [])
            if item.get("status") == "TRADING"
            and item.get("contractType") == "PERPETUAL"
            and item.get("quoteAsset") == "USDT"
        }
        symbols.discard("")
        _SYMBOL_CACHE = (time.time(), symbols)
        return symbols

    async def get_klines(self, symbol: str, interval: str = "4h", limit: int = 120) -> list[PionexKline]:
        data = await self._get(
            "/fapi/v1/klines",
            params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
        )
        candles = [
            PionexKline(
                time=int(item[0]),
                open=to_float(item[1]),
                high=to_float(item[2]),
                low=to_float(item[3]),
                close=to_float(item[4]),
                volume=to_float(item[5]),
            )
            for item in data
            if isinstance(item, list) and len(item) >= 6
        ]
        candles.sort(key=lambda candle: candle.time)
        return candles

    async def get_klines_for_pionex_symbols(
        self,
        pionex_symbols: list[str],
        *,
        interval: str = "4h",
        limit: int = 120,
        max_concurrency: int = 8,
    ) -> dict[str, list[PionexKline]]:
        supported = await self.get_usdt_perpetual_symbols()
        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch(pionex_symbol: str) -> tuple[str, list[PionexKline]]:
            binance_symbol = pionex_perp_to_binance_symbol(pionex_symbol)
            if binance_symbol not in supported:
                return pionex_symbol, []
            async with semaphore:
                try:
                    return pionex_symbol, await self.get_klines(binance_symbol, interval=interval, limit=limit)
                except BinanceFuturesClientError:
                    return pionex_symbol, []

        results = await asyncio.gather(*(fetch(symbol) for symbol in pionex_symbols))
        return {symbol: candles for symbol, candles in results if candles}
