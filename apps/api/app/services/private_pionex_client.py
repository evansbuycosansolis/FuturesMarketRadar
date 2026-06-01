from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from ..config import Settings
from .pionex_client import PionexClientError, to_float


class PionexPrivateClientError(PionexClientError):
    pass


def _from_millis(value: Any) -> datetime | None:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    if millis <= 0:
        return None
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)


@dataclass(slots=True)
class PionexQuoteRisk:
    quote: str
    risk_state: str


@dataclass(slots=True)
class PionexAccountBalance:
    coin: str
    assets: float
    free: float
    frozen: float
    transferable: float
    available: float
    unrealized_pnl: float
    total_initial_margin: float
    debts: float


@dataclass(slots=True)
class PionexAccountPosition:
    symbol: str
    position_id: str
    isolated_mode: str
    risk_state: str
    position_side: str
    net_size: float
    avg_price: float
    unrealized_pnl: float
    mark_price: float
    initial_margin: float
    maint_margin: float
    liquidation_price: float
    leverage: float
    created_time: datetime | None
    updated_time: datetime | None

    @property
    def notional_value(self) -> float:
        reference_price = self.mark_price or self.avg_price
        return abs(reference_price * self.net_size)


@dataclass(slots=True)
class PionexAccountDetail:
    quote_risks: list[PionexQuoteRisk]
    balances: list[PionexAccountBalance]
    positions: list[PionexAccountPosition]


@dataclass(slots=True)
class PionexOpenOrder:
    symbol: str
    order_id: str
    client_order_id: str
    side: str
    position_side: str
    order_type: str
    price: float
    size: float
    filled_size: float
    reduce_only: bool
    status: str
    created_time: datetime | None
    updated_time: datetime | None


@dataclass(slots=True)
class PionexOrderRecord:
    symbol: str
    order_id: str
    client_order_id: str
    side: str
    position_side: str
    order_type: str
    price: float
    size: float
    filled_size: float
    reduce_only: bool
    status: str
    created_time: datetime | None
    updated_time: datetime | None


class PrivatePionexClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.pionex_base_url.rstrip("/"),
            timeout=settings.pionex_timeout_seconds,
            headers={"Accept": "application/json"},
        )

    @property
    def is_configured(self) -> bool:
        return self._settings.private_api_configured

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

    def _serialize_body(self, body: dict[str, Any] | None) -> str:
        if not body:
            return ""
        return json.dumps(body, separators=(",", ":"), sort_keys=True)

    def _signature_headers(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[dict[str, str], dict[str, Any], str]:
        if not self.is_configured:
            raise PionexPrivateClientError("Private Pionex API is not configured. Add FMR_PIONEX_API_KEY and FMR_PIONEX_API_SECRET.")

        query_params = {
            key: value
            for key, value in (params or {}).items()
            if value is not None
        }
        query_params["timestamp"] = int(time.time() * 1000)

        sorted_items = sorted((key, str(value)) for key, value in query_params.items())
        query_string = "&".join(f"{key}={value}" for key, value in sorted_items)
        path_url = f"{path}?{query_string}"
        body_text = self._serialize_body(body)
        payload = f"{method.upper()}{path_url}{body_text if method.upper() in {'POST', 'DELETE'} else ''}"
        signature = hmac.new(
            self._settings.pionex_api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Accept": "application/json",
            "PIONEX-KEY": self._settings.pionex_api_key,
            "PIONEX-SIGNATURE": signature,
        }
        if body_text:
            headers["Content-Type"] = "application/json"
        return headers, query_params, body_text

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers, query_params, body_text = self._signature_headers(method, path, params, body)
        retries = max(self._settings.pionex_rate_limit_retries, 0)
        for attempt in range(retries + 1):
            try:
                response = await self._client.request(
                    method.upper(),
                    path,
                    params=query_params,
                    headers=headers,
                    content=body_text.encode("utf-8") if body_text else None,
                )
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < retries:
                    await asyncio.sleep(self._rate_limit_delay(exc.response, attempt))
                    continue
                raise PionexPrivateClientError(
                    f"Pionex private request failed for {path}: {exc}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.HTTPError as exc:
                raise PionexPrivateClientError(f"Pionex private request failed for {path}: {exc}") from exc

        payload = response.json()
        if not payload.get("result", False):
            raise PionexPrivateClientError(
                f"Pionex private request returned an unsuccessful payload for {path}: {payload}"
            )
        return payload.get("data", {})

    async def get_account_detail(self) -> PionexAccountDetail:
        data = await self._request("GET", "/uapi/v1/account/detail")
        return PionexAccountDetail(
            quote_risks=[
                PionexQuoteRisk(
                    quote=item.get("quote", ""),
                    risk_state=item.get("riskState", ""),
                )
                for item in data.get("quoteRisks", [])
            ],
            balances=[
                PionexAccountBalance(
                    coin=item.get("coin", ""),
                    assets=to_float(item.get("assets")),
                    free=to_float(item.get("free")),
                    frozen=to_float(item.get("frozen")),
                    transferable=to_float(item.get("transferable")),
                    available=to_float(item.get("available")),
                    unrealized_pnl=to_float(item.get("unrealizedPnL")),
                    total_initial_margin=to_float(item.get("totalInitialMargin")),
                    debts=to_float(item.get("debts")),
                )
                for item in data.get("balances", [])
            ],
            positions=[
                PionexAccountPosition(
                    symbol=item.get("symbol", ""),
                    position_id=str(item.get("positionId", "")),
                    isolated_mode=item.get("isolatedMode", ""),
                    risk_state=item.get("riskState", ""),
                    position_side=item.get("positionSide", ""),
                    net_size=to_float(item.get("netSize")),
                    avg_price=to_float(item.get("avgPrice")),
                    unrealized_pnl=to_float(item.get("unrealizedPnL")),
                    mark_price=to_float(item.get("markPrice")),
                    initial_margin=to_float(item.get("initialMargin")),
                    maint_margin=to_float(item.get("maintMargin")),
                    liquidation_price=to_float(item.get("liquidationPrice")),
                    leverage=to_float(item.get("leverage")),
                    created_time=_from_millis(item.get("createdTime")),
                    updated_time=_from_millis(item.get("updatedTime")),
                )
                for item in data.get("positions", [])
            ],
        )

    async def get_open_orders(self, symbol: str | None = None, limit: int = 100) -> list[PionexOpenOrder]:
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        data = await self._request("GET", "/uapi/v1/trade/openOrders", params=params)
        orders = data.get("orders", [])
        return [self._parse_order(item, PionexOpenOrder) for item in orders]

    async def get_order_by_client_order_id(self, symbol: str, client_order_id: str) -> PionexOrderRecord | None:
        data = await self._request(
            "GET",
            "/uapi/v1/trade/orderByClientOrderId",
            params={"symbol": symbol, "clientOrderId": client_order_id},
        )
        if not data:
            return None
        return self._parse_order(data, PionexOrderRecord)

    async def get_order(self, symbol: str, order_id: str) -> PionexOrderRecord | None:
        data = await self._request(
            "GET",
            "/uapi/v1/trade/order",
            params={"symbol": symbol, "orderId": order_id},
        )
        if not data:
            return None
        return self._parse_order(data, PionexOrderRecord)

    async def place_order(self, payload: dict[str, Any]) -> str:
        clean_payload = {
            key: value
            for key, value in payload.items()
            if value is not None and value != ""
        }
        data = await self._request("POST", "/uapi/v1/trade/order", body=clean_payload)
        return str(data.get("orderId", ""))

    async def cancel_all_orders(self, symbol: str) -> None:
        await self._request("DELETE", "/uapi/v1/trade/allOrders", body={"symbol": symbol})

    def _parse_order(self, item: dict[str, Any], model_type):
        return model_type(
            symbol=item.get("symbol", ""),
            order_id=str(item.get("orderId", "")),
            client_order_id=item.get("clientOrderId", ""),
            side=item.get("side", ""),
            position_side=item.get("positionSide", "BOTH"),
            order_type=item.get("type", ""),
            price=to_float(item.get("price")),
            size=to_float(item.get("size")),
            filled_size=to_float(
                item.get("filledSize")
                or item.get("dealSize")
                or item.get("filledQty")
                or item.get("executedSize")
            ),
            reduce_only=bool(item.get("reduceOnly", False)),
            status=item.get("status", item.get("state", "OPEN")),
            created_time=_from_millis(item.get("createdTime")),
            updated_time=_from_millis(item.get("updatedTime")),
        )
