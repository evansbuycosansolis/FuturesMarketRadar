from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings


class PionexClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class PionexSymbolInfo:
    symbol: str
    name: str
    base_currency: str
    quote_currency: str
    market_type: str
    status: str


@dataclass(slots=True)
class PionexTicker:
    symbol: str
    time: int
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    count: int

    @property
    def price_change_24h(self) -> float:
        if self.open == 0:
            return 0.0
        return ((self.close - self.open) / self.open) * 100


@dataclass(slots=True)
class PionexKline:
    time: int
    open: float
    close: float
    high: float
    low: float
    volume: float


@dataclass(slots=True)
class PionexFundingRate:
    symbol: str
    funding_rate: float
    funding_time: int


@dataclass(slots=True)
class PionexBookLevel:
    price: float
    size: float


@dataclass(slots=True)
class PionexOrderBook:
    symbol: str
    bids: list[PionexBookLevel]
    asks: list[PionexBookLevel]


@dataclass(slots=True)
class PionexIndexPrice:
    symbol: str
    index_price: float
    mark_price: float
    funding_rate: float
    next_funding_time: int


class PionexClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        limits = httpx.Limits(
            max_connections=max(settings.pionex_max_concurrent_requests * 2, 20),
            max_keepalive_connections=settings.pionex_max_concurrent_requests,
        )
        self._client = httpx.AsyncClient(
            base_url=settings.pionex_base_url.rstrip("/"),
            timeout=settings.pionex_timeout_seconds,
            limits=limits,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _rate_limit_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "").strip()
        try:
            retry_after_seconds = float(retry_after)
        except ValueError:
            retry_after_seconds = 0.0
        if retry_after_seconds > 0:
            return retry_after_seconds
        return self._settings.pionex_rate_limit_backoff_seconds * (2 ** attempt)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        retries = max(self._settings.pionex_rate_limit_retries, 0)
        for attempt in range(retries + 1):
            try:
                response = await self._client.get(path, params=params)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < retries:
                    await asyncio.sleep(self._rate_limit_delay(exc.response, attempt))
                    continue
                raise PionexClientError(
                    f"Pionex request failed for {path}: {exc}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.HTTPError as exc:
                raise PionexClientError(f"Pionex request failed for {path}: {exc}") from exc

        payload = response.json()
        if not payload.get("result", False):
            raise PionexClientError(f"Pionex returned an unsuccessful payload for {path}: {payload}")
        return payload.get("data", {})

    async def get_symbols(self) -> list[PionexSymbolInfo]:
        data = await self._get("/api/v1/common/symbols", params={"type": "PERP"})
        return [
            PionexSymbolInfo(
                symbol=item["symbol"],
                name=item.get("name", item["symbol"]),
                base_currency=item.get("baseCurrency", ""),
                quote_currency=item.get("quoteCurrency", ""),
                market_type=item.get("type", "PERP"),
                status=item.get("status", "UNKNOWN"),
            )
            for item in data.get("symbols", [])
        ]

    async def get_tickers(self) -> list[PionexTicker]:
        data = await self._get("/api/v1/market/tickers", params={"type": "PERP"})
        return [
            PionexTicker(
                symbol=item["symbol"],
                time=int(item.get("time", 0)),
                open=to_float(item.get("open")),
                close=to_float(item.get("close")),
                high=to_float(item.get("high")),
                low=to_float(item.get("low")),
                volume=to_float(item.get("volume")),
                amount=to_float(item.get("amount")),
                count=int(item.get("count", 0)),
            )
            for item in data.get("tickers", [])
        ]

    async def get_open_interests(self) -> dict[str, float]:
        data = await self._get("/api/v1/market/openInterests")
        return {
            item["symbol"]: to_float(item.get("openInterest"))
            for item in data.get("openInterests", [])
            if item.get("symbol")
        }

    async def get_funding_rates(self, symbol: str, limit: int = 1) -> list[PionexFundingRate]:
        data = await self._get(
            "/api/v1/market/fundingRates",
            params={"symbol": symbol, "limit": limit},
        )
        return [
            PionexFundingRate(
                symbol=item.get("symbol", symbol),
                funding_rate=to_float(item.get("fundingRate")),
                funding_time=int(item.get("fundingTime", item.get("time", 0)) or 0),
            )
            for item in data.get("fundingRates", [])
        ]

    async def get_order_book(self, symbol: str, limit: int = 20) -> PionexOrderBook:
        data = await self._get(
            "/api/v1/market/depth",
            params={"symbol": symbol, "limit": limit},
        )

        def levels(items: list[Any]) -> list[PionexBookLevel]:
            parsed: list[PionexBookLevel] = []
            for item in items:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    parsed.append(PionexBookLevel(price=to_float(item[0]), size=to_float(item[1])))
                elif isinstance(item, dict):
                    parsed.append(PionexBookLevel(price=to_float(item.get("price")), size=to_float(item.get("size"))))
            return parsed

        return PionexOrderBook(
            symbol=symbol,
            bids=levels(data.get("bids", [])),
            asks=levels(data.get("asks", [])),
        )

    async def get_index_prices(self, symbol: str | None = None) -> list[PionexIndexPrice]:
        params = {"symbol": symbol} if symbol else None
        data = await self._get("/api/v1/market/indexes", params=params)
        return [
            PionexIndexPrice(
                symbol=item.get("symbol", ""),
                index_price=to_float(item.get("indexPrice")),
                mark_price=to_float(item.get("markPrice")),
                funding_rate=to_float(item.get("fundingRate") or item.get("nextFundingRate")),
                next_funding_time=int(item.get("nextFundingTime", 0) or 0),
            )
            for item in data.get("indexes", [])
        ]

    async def get_klines(self, symbol: str, interval: str = "1M", limit: int = 60) -> list[PionexKline]:
        data = await self._get(
            "/api/v1/market/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        candles = [
            PionexKline(
                time=int(item.get("time", 0)),
                open=to_float(item.get("open")),
                close=to_float(item.get("close")),
                high=to_float(item.get("high")),
                low=to_float(item.get("low")),
                volume=to_float(item.get("volume")),
            )
            for item in data.get("klines", [])
        ]
        candles.sort(key=lambda candle: candle.time)
        return candles
