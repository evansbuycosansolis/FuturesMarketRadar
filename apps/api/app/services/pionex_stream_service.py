from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import websockets
from sqlalchemy import select

from ..config import Settings
from ..db import SessionLocal
from .. import models
from .private_pionex_client import PrivatePionexClient


@dataclass(slots=True)
class StreamConnectionStatus:
    name: str
    running: bool = False
    connected: bool = False
    last_event_at: datetime | None = None
    last_error: str | None = None
    subscribed_symbols: list[str] = field(default_factory=list)


class PionexStreamService:
    def __init__(self, settings: Settings, private_client: PrivatePionexClient) -> None:
        self._settings = settings
        self._private_client = private_client
        self._exit_automation_service = None
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._last_control_write: dict[str, datetime] = {}
        self._private_status = StreamConnectionStatus(name="private")
        self._public_status = StreamConnectionStatus(name="public")

    def set_exit_automation_service(self, service) -> None:
        self._exit_automation_service = service

    @property
    def private_status(self) -> StreamConnectionStatus:
        return self._private_status

    @property
    def public_status(self) -> StreamConnectionStatus:
        return self._public_status

    async def start(self) -> None:
        if not self._settings.enable_websocket_monitoring:
            return
        self._stop_event.clear()
        self._tasks = [
            asyncio.create_task(self._public_loop(), name="fmr-public-stream"),
        ]
        if self._settings.enable_private_api and self._private_client.is_configured:
            self._tasks.append(asyncio.create_task(self._private_loop(), name="fmr-private-stream"))

    async def stop(self) -> None:
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._private_status.running = False
        self._public_status.running = False
        self._private_status.connected = False
        self._public_status.connected = False

    async def _public_loop(self) -> None:
        self._public_status.running = True
        while not self._stop_event.is_set():
            symbols = self._active_exit_symbols()
            if not symbols:
                self._public_status.connected = False
                self._public_status.subscribed_symbols = []
                await asyncio.sleep(2)
                continue

            try:
                async with websockets.connect(
                    "wss://ws.pionex.com/wsPub",
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2_000_000,
                ) as websocket:
                    self._public_status.connected = True
                    self._public_status.last_error = None
                    subscribed = set()
                    last_refresh = 0.0
                    while not self._stop_event.is_set():
                        now_monotonic = time.monotonic()
                        if now_monotonic - last_refresh >= 2:
                            latest_symbols = self._active_exit_symbols()
                            if latest_symbols != subscribed:
                                await self._sync_public_subscriptions(websocket, subscribed, latest_symbols)
                                subscribed = latest_symbols
                                self._public_status.subscribed_symbols = sorted(subscribed)
                            if not latest_symbols:
                                break
                            last_refresh = now_monotonic

                        try:
                            raw_message = await asyncio.wait_for(websocket.recv(), timeout=3)
                        except asyncio.TimeoutError:
                            continue

                        payload = self._decode_message(raw_message)
                        if payload is None:
                            continue
                        event_time = datetime.now(timezone.utc)
                        self._public_status.last_event_at = event_time
                        self._touch_control("last_public_stream_event_at", event_time)
                        await self._handle_public_message(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._public_status.connected = False
                self._public_status.last_error = str(exc)
                await asyncio.sleep(3)

        self._public_status.running = False

    async def _private_loop(self) -> None:
        self._private_status.running = True
        while not self._stop_event.is_set():
            if not self._settings.enable_private_api or not self._private_client.is_configured:
                self._private_status.connected = False
                await asyncio.sleep(2)
                continue

            try:
                async with websockets.connect(
                    "wss://ws.pionex.com/wsUA",
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2_000_000,
                ) as websocket:
                    await self._authenticate_private_stream(websocket)
                    for topic in ("ORDER", "FILL", "POSITION"):
                        await websocket.send(json.dumps({"op": "SUBSCRIBE", "topic": topic, "symbol": "ALL"}))
                    self._private_status.connected = True
                    self._private_status.last_error = None

                    while not self._stop_event.is_set():
                        try:
                            raw_message = await asyncio.wait_for(websocket.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            continue

                        payload = self._decode_message(raw_message)
                        if payload is None:
                            continue
                        event_time = datetime.now(timezone.utc)
                        self._private_status.last_event_at = event_time
                        self._touch_control("last_private_stream_event_at", event_time)
                        await self._handle_private_message(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._private_status.connected = False
                self._private_status.last_error = str(exc)
                await asyncio.sleep(3)

        self._private_status.running = False

    async def _authenticate_private_stream(self, websocket) -> None:
        timestamp = int(time.time() * 1000)
        signature = hmac.new(
            self._settings.pionex_api_secret.encode("utf-8"),
            f"{timestamp}websocket_auth".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        await websocket.send(
            json.dumps(
                {
                    "op": "auth",
                    "args": [
                        self._settings.pionex_api_key,
                        timestamp,
                        signature,
                    ],
                }
            )
        )

    async def _sync_public_subscriptions(self, websocket, current: set[str], target: set[str]) -> None:
        for symbol in sorted(target - current):
            await websocket.send(json.dumps({"op": "SUBSCRIBE", "topic": "TRADE", "symbol": symbol}))
        for symbol in sorted(current - target):
            await websocket.send(json.dumps({"op": "UNSUBSCRIBE", "topic": "TRADE", "symbol": symbol}))

    async def _handle_public_message(self, payload: dict) -> None:
        if payload.get("topic") != "TRADE" or self._exit_automation_service is None:
            return
        symbol = str(payload.get("symbol", "")).upper()
        for record in payload.get("data", []) or []:
            price = self._to_float(record.get("price"))
            if price <= 0:
                continue
            await self._exit_automation_service.handle_market_trade(
                symbol=symbol,
                trade_price=price,
                reason="ws-public-trade",
            )

    async def _handle_private_message(self, payload: dict) -> None:
        topic = str(payload.get("topic", "")).upper()
        symbol = str(payload.get("symbol", "")).upper()
        if self._exit_automation_service is None:
            return
        if topic == "POSITION":
            await self._exit_automation_service.handle_private_position_update(symbol=symbol, reason="ws-position")
        elif topic in {"ORDER", "FILL"}:
            await self._exit_automation_service.handle_private_execution_update(symbol=symbol, reason=f"ws-{topic.lower()}")

    def _active_exit_symbols(self) -> set[str]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(models.ManagedExitPlan.symbol)
                .where(models.ManagedExitPlan.status.in_(("pending_fill", "armed", "exit_submitted")))
            ).all()
        return {row.upper() for row in rows if row}

    def _touch_control(self, field_name: str, value: datetime) -> None:
        previous = self._last_control_write.get(field_name)
        if previous is not None and (value - previous).total_seconds() < 2:
            return
        self._last_control_write[field_name] = value
        with SessionLocal() as db:
            control = db.get(models.AutomationControl, 1)
            if control is None:
                control = models.AutomationControl(id=1, mode=self._settings.automation_default_mode)
                db.add(control)
                db.flush()
            setattr(control, field_name, value)
            db.commit()

    def _decode_message(self, raw_message) -> dict | None:
        if isinstance(raw_message, bytes):
            try:
                raw_message = raw_message.decode("utf-8")
            except UnicodeDecodeError:
                return None
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return payload
        return None

    def _to_float(self, value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
