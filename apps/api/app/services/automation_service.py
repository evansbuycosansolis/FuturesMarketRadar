from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import desc, func, select

from .. import models
from ..config import Settings
from ..db import SessionLocal
from ..schemas import (
    AutomationActionResponse,
    AutomationAlertRead,
    AutomationControlRead,
    AutomationControlUpdate,
    AutomationSignalRead,
    AutomationSummaryResponse,
    ExecutionOrderRequest,
    SignalActionResponse,
    TradingViewWebhookResponse,
    TradePlanRequest,
)
from .private_pionex_client import PrivatePionexClient

if TYPE_CHECKING:
    from .exit_automation_service import ExitAutomationService
    from .pionex_stream_service import PionexStreamService
    from .risk_service import RiskService


AUTOMATION_MODES = {"paper", "supervised_live", "unattended_live"}
AUTOMATION_ALERT_CODES = {
    "KILL_SWITCH",
    "SYNC_STALE",
    "PRIVATE_STREAM_STALE",
    "PUBLIC_STREAM_STALE",
    "FAILURE_STREAK",
    "EXIT_ENGINE_ERROR",
}
ACTIVE_EXIT_STATUSES = {"pending_fill", "armed", "exit_submitted"}


@dataclass(slots=True)
class NormalizedSignal:
    source: str
    source_signal_id: str
    strategy_name: str
    symbol: str
    side: str
    order_type: str
    position_side: str
    size: float | None
    entry_price: float | None
    stop_price: float | None
    take_profit_price: float | None
    planned_leverage: float | None
    reduce_only: bool
    secret: str | None
    raw_payload: dict[str, Any]


class AutomationService:
    def __init__(self, settings: Settings, private_client: PrivatePionexClient) -> None:
        self._settings = settings
        self._private_client = private_client
        self._risk_service: RiskService | None = None
        self._exit_automation_service: ExitAutomationService | None = None
        self._stream_service: PionexStreamService | None = None

    def set_risk_service(self, service: RiskService) -> None:
        self._risk_service = service

    def set_exit_automation_service(self, service: ExitAutomationService) -> None:
        self._exit_automation_service = service

    def set_stream_service(self, service: PionexStreamService) -> None:
        self._stream_service = service

    def ensure_control(self, db) -> models.AutomationControl:
        control = db.get(models.AutomationControl, 1)
        if control is None:
            default_mode = self._settings.automation_default_mode
            if default_mode not in AUTOMATION_MODES:
                default_mode = "paper"
            control = models.AutomationControl(id=1, mode=default_mode)
            db.add(control)
            db.commit()
            db.refresh(control)
            return control
        if control.mode not in AUTOMATION_MODES:
            control.mode = "paper"
            db.commit()
            db.refresh(control)
        return control

    def build_summary(self) -> AutomationSummaryResponse:
        with SessionLocal() as db:
            control = self.ensure_control(db)
            alerts = db.scalars(
                select(models.AutomationAlert)
                .where(models.AutomationAlert.active.is_(True))
                .order_by(desc(models.AutomationAlert.updated_at))
                .limit(12)
            ).all()
            signals = db.scalars(
                select(models.AutomationSignal)
                .order_by(desc(models.AutomationSignal.created_at))
                .limit(self._settings.automation_signal_history_limit)
            ).all()
            pending_approval_count = db.scalar(
                select(func.count(models.AutomationSignal.id)).where(models.AutomationSignal.status == "pending_approval")
            ) or 0

        private_status = self._stream_service.private_status if self._stream_service is not None else None
        public_status = self._stream_service.public_status if self._stream_service is not None else None
        return AutomationSummaryResponse(
            control=AutomationControlRead.model_validate(control),
            webhook_secret_configured=self._settings.tradingview_webhook_configured,
            websocket_monitoring_enabled=self._settings.enable_websocket_monitoring,
            private_stream_connected=bool(private_status.connected) if private_status else False,
            public_stream_connected=bool(public_status.connected) if public_status else False,
            private_stream_last_error=private_status.last_error if private_status else None,
            public_stream_last_error=public_status.last_error if public_status else None,
            pending_approval_count=int(pending_approval_count),
            recent_signals=[AutomationSignalRead.model_validate(signal, from_attributes=True) for signal in signals],
            alerts=[AutomationAlertRead.model_validate(alert, from_attributes=True) for alert in alerts],
        )

    def update_control(self, payload: AutomationControlUpdate) -> models.AutomationControl:
        with SessionLocal() as db:
            control = self.ensure_control(db)
            control.mode = payload.mode
            db.commit()
            db.refresh(control)
            return control

    def engage_kill_switch(self, reason: str, source: str = "manual") -> models.AutomationControl:
        with SessionLocal() as db:
            control = self.ensure_control(db)
            control.kill_switch_enabled = True
            control.kill_switch_reason = reason.strip() or f"Kill-switch engaged by {source}."
            control.last_automation_error = control.kill_switch_reason
            self._upsert_alert(
                db,
                code="KILL_SWITCH",
                severity="critical",
                message=control.kill_switch_reason,
                payload={"source": source},
            )
            db.commit()
            db.refresh(control)
            return control

    def release_kill_switch(self, reason: str | None = None) -> models.AutomationControl:
        with SessionLocal() as db:
            control = self.ensure_control(db)
            control.kill_switch_enabled = False
            control.kill_switch_reason = reason.strip() if reason else ""
            control.last_automation_error = ""
            control.consecutive_failures = 0
            self._resolve_alert(db, "KILL_SWITCH")
            self._resolve_alert(db, "FAILURE_STREAK")
            db.commit()
            db.refresh(control)
            return control

    def raise_if_manual_execution_blocked(self) -> None:
        with SessionLocal() as db:
            control = self.ensure_control(db)
            if control.kill_switch_enabled:
                raise HTTPException(
                    status_code=423,
                    detail=f"Trading is locked by the automation kill-switch: {control.kill_switch_reason or 'No reason recorded.'}",
                )

    async def handle_tradingview_webhook(
        self,
        payload: dict[str, Any],
        *,
        header_secret: str | None = None,
    ) -> TradingViewWebhookResponse:
        if self._risk_service is None:
            raise HTTPException(status_code=503, detail="Risk service is not ready yet.")

        normalized = self._normalize_signal(payload)
        supplied_secret = header_secret or normalized.secret
        self._verify_secret(supplied_secret)

        with SessionLocal() as db:
            control = self.ensure_control(db)
            existing_signal = db.scalar(
                select(models.AutomationSignal)
                .where(models.AutomationSignal.source == normalized.source)
                .where(models.AutomationSignal.source_signal_id == normalized.source_signal_id)
            )
            if existing_signal is not None:
                return TradingViewWebhookResponse(
                    ok=True,
                    signal=AutomationSignalRead.model_validate(existing_signal, from_attributes=True),
                    message="Duplicate webhook ignored by replay protection.",
                )

            self._store_receipt(db, normalized)
            signal = models.AutomationSignal(
                source=normalized.source,
                source_signal_id=normalized.source_signal_id,
                strategy_name=normalized.strategy_name,
                symbol=normalized.symbol,
                side=normalized.side,
                mode_at_receipt=control.mode,
                status="received",
                requested_order_type=normalized.order_type,
                requested_size=normalized.size or 0.0,
                requested_entry_price=normalized.entry_price or 0.0,
                requested_stop_price=normalized.stop_price or 0.0,
                requested_take_profit_price=normalized.take_profit_price or 0.0,
                raw_payload_json=normalized.raw_payload,
            )
            db.add(signal)
            control.last_webhook_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(signal)

        order_request, risk_check = self._prepare_order_request(normalized, signal_id=signal.id)
        signal = self._update_signal_plan(signal.id, order_request, risk_check)
        control = self.build_summary().control

        if not risk_check.allowed:
            signal = self._set_signal_status(
                signal.id,
                status="blocked",
                reason="Risk gate blocked the signal before any execution path was opened.",
            )
            return TradingViewWebhookResponse(
                ok=True,
                signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
                message="Signal stored, but it was blocked by the deterministic risk gate.",
            )

        if control.mode == "paper":
            signal = self._set_signal_status(
                signal.id,
                status="paper_executed",
                reason="Paper mode stored the planned order without sending it to Pionex.",
                execution_result={"paper": True, "planned_order": order_request.model_dump(mode="json")},
            )
            return TradingViewWebhookResponse(
                ok=True,
                signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
                message="Signal accepted in paper mode.",
            )

        automation_blockers = self._automation_blockers(strict_stream=True)
        if automation_blockers:
            signal = self._set_signal_status(
                signal.id,
                status="blocked",
                reason=" | ".join(automation_blockers),
            )
            return TradingViewWebhookResponse(
                ok=True,
                signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
                message="Signal stored, but automation circuit breakers refused execution.",
            )

        if control.mode == "supervised_live":
            signal = self._set_signal_status(
                signal.id,
                status="pending_approval",
                reason="Signal passed the gate and is waiting for supervisor approval.",
            )
            return TradingViewWebhookResponse(
                ok=True,
                signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
                message="Signal is queued for supervised approval.",
            )

        signal = await self._execute_live_signal(signal.id, order_request, reason="unattended-webhook")
        return TradingViewWebhookResponse(
            ok=True,
            signal=AutomationSignalRead.model_validate(signal, from_attributes=True),
            message="Signal processed in unattended live mode.",
        )

    async def approve_signal(self, signal_id: int) -> models.AutomationSignal:
        signal, order_request = self._load_pending_signal_request(signal_id)
        return await self._execute_live_signal(signal.id, order_request, reason="supervised-approval")

    def reject_signal(self, signal_id: int, reason: str) -> models.AutomationSignal:
        return self._set_signal_status(
            signal_id,
            status="rejected",
            reason=reason.strip() or "Supervisor rejected the signal.",
        )

    async def reconcile_state(self, reason: str = "scheduled", raise_on_rate_limit: bool = False) -> None:
        with SessionLocal() as db:
            control = self.ensure_control(db)

        if self._risk_service is not None and self._settings.enable_private_api and self._private_client.is_configured:
            try:
                await self._risk_service.sync_account_state(raise_on_rate_limit=raise_on_rate_limit)
            except Exception as exc:
                self._register_failure(f"Reconciliation sync failed: {exc}")
                raise

        if self._exit_automation_service is not None and self._settings.enable_exit_automation:
            await self._exit_automation_service.run_once(reason=f"reconcile:{reason}")

        if self._settings.enable_private_api and self._private_client.is_configured:
            with SessionLocal() as db:
                executing_signals = db.scalars(
                    select(models.AutomationSignal)
                    .where(models.AutomationSignal.status == "executing")
                    .where(models.AutomationSignal.client_order_id != "")
                    .order_by(models.AutomationSignal.created_at)
                ).all()

            for signal in executing_signals:
                try:
                    order = await self._private_client.get_order_by_client_order_id(signal.symbol, signal.client_order_id)
                except Exception:
                    order = None
                if order is not None:
                    self._set_signal_status(
                        signal.id,
                        status="executed",
                        reason="Reconciled after restart by querying the exchange with clientOrderId.",
                        order_id=order.order_id,
                        execution_result={
                            "reconciled": True,
                            "status": order.status,
                            "client_order_id": order.client_order_id,
                            "order_id": order.order_id,
                        },
                    )

        with SessionLocal() as db:
            control = self.ensure_control(db)
            control.last_reconciliation_at = datetime.now(timezone.utc)
            db.commit()

    async def run_watchdog(self, reason: str = "scheduled") -> None:
        now = datetime.now(timezone.utc)
        active_codes: set[str] = set()

        with SessionLocal() as db:
            control = self.ensure_control(db)
            latest_snapshot = None
            if self._settings.enable_private_api:
                latest_snapshot = db.scalar(
                    select(models.AccountSnapshot).order_by(desc(models.AccountSnapshot.snapshot_time))
                )
            if control.kill_switch_enabled:
                active_codes.add("KILL_SWITCH")
                self._upsert_alert(
                    db,
                    code="KILL_SWITCH",
                    severity="critical",
                    message=control.kill_switch_reason or "Kill-switch is engaged.",
                    payload={"reason": control.kill_switch_reason, "watchdog_reason": reason},
                )

            if latest_snapshot is not None:
                age = (now - latest_snapshot.snapshot_time).total_seconds()
                if age > self._settings.automation_sync_stale_seconds:
                    active_codes.add("SYNC_STALE")
                    self._upsert_alert(
                        db,
                        code="SYNC_STALE",
                        severity="critical",
                        message=f"Account sync is stale by {age:.0f}s, so unattended execution should stay off.",
                        payload={"age_seconds": age},
                    )
                    if not control.kill_switch_enabled:
                        control.kill_switch_enabled = True
                        control.kill_switch_reason = "Watchdog engaged the kill-switch because account sync went stale."
                else:
                    self._resolve_alert(db, "SYNC_STALE")

            if control.consecutive_failures > 0:
                active_codes.add("FAILURE_STREAK")
                severity = "critical" if control.consecutive_failures >= self._settings.automation_max_consecutive_failures else "warning"
                self._upsert_alert(
                    db,
                    code="FAILURE_STREAK",
                    severity=severity,
                    message=f"Automation has logged {control.consecutive_failures} consecutive execution failure(s).",
                    payload={"count": control.consecutive_failures},
                )
                if control.consecutive_failures >= self._settings.automation_max_consecutive_failures and not control.kill_switch_enabled:
                    control.kill_switch_enabled = True
                    control.kill_switch_reason = "Watchdog engaged the kill-switch after consecutive automation failures."
            else:
                self._resolve_alert(db, "FAILURE_STREAK")

            if self._exit_automation_service is not None and self._exit_automation_service.status.last_error:
                active_codes.add("EXIT_ENGINE_ERROR")
                self._upsert_alert(
                    db,
                    code="EXIT_ENGINE_ERROR",
                    severity="high",
                    message=f"Managed exit engine reported: {self._exit_automation_service.status.last_error}",
                    payload={},
                )
            else:
                self._resolve_alert(db, "EXIT_ENGINE_ERROR")

            if self._settings.enable_websocket_monitoring and self._stream_service is not None:
                private_status = self._stream_service.private_status
                if self._settings.enable_private_api and self._private_client.is_configured:
                    private_age = self._event_age_seconds(control.last_private_stream_event_at, now)
                    if private_status.last_error or (
                        private_age is not None and private_age > self._settings.automation_stream_stale_seconds
                    ):
                        active_codes.add("PRIVATE_STREAM_STALE")
                        self._upsert_alert(
                            db,
                            code="PRIVATE_STREAM_STALE",
                            severity="warning",
                            message="Private websocket monitoring is stale or disconnected.",
                            payload={
                                "age_seconds": private_age,
                                "connected": private_status.connected,
                                "last_error": private_status.last_error,
                            },
                        )
                    else:
                        self._resolve_alert(db, "PRIVATE_STREAM_STALE")

                active_plan_count = db.scalar(
                    select(func.count(models.ManagedExitPlan.id)).where(models.ManagedExitPlan.status.in_(ACTIVE_EXIT_STATUSES))
                ) or 0
                if active_plan_count > 0:
                    public_age = self._event_age_seconds(control.last_public_stream_event_at, now)
                    public_status = self._stream_service.public_status
                    if public_status.last_error or (
                        public_age is not None and public_age > self._settings.automation_stream_stale_seconds
                    ):
                        active_codes.add("PUBLIC_STREAM_STALE")
                        self._upsert_alert(
                            db,
                            code="PUBLIC_STREAM_STALE",
                            severity="high",
                            message="Public trade websocket monitoring is stale while managed exits are active.",
                            payload={
                                "age_seconds": public_age,
                                "connected": public_status.connected,
                                "last_error": public_status.last_error,
                                "active_plan_count": active_plan_count,
                            },
                        )
                    else:
                        self._resolve_alert(db, "PUBLIC_STREAM_STALE")
                else:
                    self._resolve_alert(db, "PUBLIC_STREAM_STALE")

            for code in AUTOMATION_ALERT_CODES - active_codes:
                self._resolve_alert(db, code)

            control.last_watchdog_at = now
            db.commit()

    def _verify_secret(self, supplied_secret: str | None) -> None:
        if not self._settings.tradingview_webhook_configured:
            raise HTTPException(
                status_code=503,
                detail="TradingView webhook handling is not configured. Set FMR_TRADINGVIEW_WEBHOOK_SECRET first.",
            )
        if not supplied_secret or not hmac.compare_digest(
            supplied_secret.strip(),
            self._settings.tradingview_webhook_secret.strip(),
        ):
            raise HTTPException(status_code=401, detail="Webhook secret verification failed.")

    def _normalize_signal(self, payload: dict[str, Any]) -> NormalizedSignal:
        raw_payload = dict(payload)
        symbol = self._first_text(payload, "symbol", "ticker", "market")
        if not symbol:
            raise HTTPException(status_code=400, detail="Webhook payload must contain a symbol or ticker.")

        side_text = self._first_text(payload, "side", "action", "signal")
        side = self._normalize_side(side_text)
        if side is None:
            raise HTTPException(status_code=400, detail="Webhook payload must contain a BUY/SELL-style action.")

        order_type = (self._first_text(payload, "order_type", "type") or "").upper()
        if order_type not in {"LIMIT", "MARKET_QTY", "IOC", "FOK", "POSTONLY"}:
            order_type = "MARKET_QTY"

        position_side = (self._first_text(payload, "position_side") or "BOTH").upper()
        if position_side not in {"BOTH", "LONG", "SHORT"}:
            position_side = "BOTH"

        strategy_name = self._first_text(payload, "strategy", "strategy_name", "name") or "TradingView"
        secret = self._first_text(payload, "secret")

        source_signal_id = (
            self._first_text(payload, "id", "alert_id", "tv_id", "message_id", "client_order_id")
            or self._fallback_signal_id(payload, symbol=symbol.upper(), side=side)
        )

        return NormalizedSignal(
            source="tradingview",
            source_signal_id=source_signal_id,
            strategy_name=strategy_name,
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            position_side=position_side,
            size=self._to_optional_float(payload.get("size") or payload.get("qty") or payload.get("quantity")),
            entry_price=self._to_optional_float(payload.get("entry_price") or payload.get("price") or payload.get("entry")),
            stop_price=self._to_optional_float(payload.get("stop_price") or payload.get("stop") or payload.get("sl")),
            take_profit_price=self._to_optional_float(
                payload.get("take_profit_price") or payload.get("take_profit") or payload.get("tp")
            ),
            planned_leverage=self._to_optional_float(payload.get("planned_leverage") or payload.get("leverage")),
            reduce_only=bool(payload.get("reduce_only") or payload.get("reduceOnly") or payload.get("close_only")),
            secret=secret,
            raw_payload=raw_payload,
        )

    def _prepare_order_request(
        self,
        signal: NormalizedSignal,
        *,
        signal_id: int,
    ) -> tuple[ExecutionOrderRequest, Any]:
        if self._risk_service is None:
            raise HTTPException(status_code=503, detail="Risk service is not ready yet.")

        plan = None
        if signal.entry_price is None or signal.stop_price is None or signal.take_profit_price is None or signal.size is None:
            plan = self._risk_service.plan_trade(
                TradePlanRequest(
                    symbol=signal.symbol,
                    side=signal.side,
                    entry_price=signal.entry_price,
                    size=signal.size,
                    planned_leverage=signal.planned_leverage,
                )
            )

        entry_price = signal.entry_price or (plan.entry_price if plan is not None else None)
        stop_price = signal.stop_price or (plan.stop_price if plan is not None else None)
        take_profit_price = signal.take_profit_price or (plan.take_profit_price if plan is not None else None)
        size = signal.size or (plan.suggested_size if plan is not None else None)

        if entry_price is None or entry_price <= 0:
            raise HTTPException(status_code=400, detail="Could not derive a valid entry price for this signal.")
        if stop_price is None or stop_price <= 0:
            raise HTTPException(status_code=400, detail="Could not derive a valid stop price for this signal.")
        if take_profit_price is None or take_profit_price <= 0:
            raise HTTPException(status_code=400, detail="Could not derive a valid take-profit price for this signal.")
        if size is None or size <= 0:
            raise HTTPException(status_code=400, detail="Webhook signal did not provide a valid size and no policy-aligned fallback was available.")

        request = ExecutionOrderRequest(
            symbol=signal.symbol,
            side=signal.side,
            size=size,
            entry_price=entry_price,
            stop_price=stop_price,
            order_type=signal.order_type,
            position_side=signal.position_side,
            planned_leverage=signal.planned_leverage,
            reduce_only=signal.reduce_only,
            client_order_id=f"fmr-signal-{signal_id}-{uuid4().hex[:12]}",
            take_profit_price=take_profit_price,
            arm_exit_automation=(
                self._settings.enable_exit_automation
                and not signal.reduce_only
                and signal.position_side == "BOTH"
                and stop_price > 0
                and take_profit_price > 0
            ),
        )
        risk_check = self._risk_service.check_trade(request)
        return request, risk_check

    def _update_signal_plan(self, signal_id: int, order_request: ExecutionOrderRequest, risk_check) -> models.AutomationSignal:
        with SessionLocal() as db:
            signal = db.get(models.AutomationSignal, signal_id)
            if signal is None:
                raise HTTPException(status_code=404, detail="Automation signal not found.")
            signal.client_order_id = order_request.client_order_id or ""
            signal.planned_order_json = order_request.model_dump(mode="json")
            signal.risk_check_json = risk_check.model_dump(mode="json")
            signal.requested_order_type = order_request.order_type
            signal.requested_size = order_request.size
            signal.requested_entry_price = order_request.entry_price
            signal.requested_stop_price = order_request.stop_price or 0.0
            signal.requested_take_profit_price = order_request.take_profit_price or 0.0
            db.commit()
            db.refresh(signal)
            return signal

    def _set_signal_status(
        self,
        signal_id: int,
        *,
        status: str,
        reason: str,
        order_id: str | None = None,
        execution_result: dict[str, Any] | None = None,
    ) -> models.AutomationSignal:
        with SessionLocal() as db:
            signal = db.get(models.AutomationSignal, signal_id)
            if signal is None:
                raise HTTPException(status_code=404, detail="Automation signal not found.")
            signal.status = status
            signal.status_reason = reason
            signal.acted_at = datetime.now(timezone.utc)
            if order_id is not None:
                signal.order_id = order_id
            if execution_result is not None:
                signal.execution_result_json = execution_result
            db.commit()
            db.refresh(signal)
            return signal

    def _load_pending_signal_request(self, signal_id: int) -> tuple[models.AutomationSignal, ExecutionOrderRequest]:
        with SessionLocal() as db:
            signal = db.get(models.AutomationSignal, signal_id)
            if signal is None:
                raise HTTPException(status_code=404, detail="Automation signal not found.")
            if signal.status != "pending_approval":
                raise HTTPException(status_code=400, detail=f"Signal is {signal.status}, not waiting for approval.")
            if not signal.planned_order_json:
                raise HTTPException(status_code=400, detail="Signal does not have a stored execution plan.")
            order_request = ExecutionOrderRequest.model_validate(signal.planned_order_json)
            return signal, order_request

    async def _execute_live_signal(
        self,
        signal_id: int,
        order_request: ExecutionOrderRequest,
        *,
        reason: str,
    ) -> models.AutomationSignal:
        if self._risk_service is None:
            raise HTTPException(status_code=503, detail="Risk service is not ready yet.")

        blockers = self._automation_blockers(strict_stream=True)
        if blockers:
            return self._set_signal_status(
                signal_id,
                status="blocked",
                reason=" | ".join(blockers),
            )

        self._set_signal_status(signal_id, status="executing", reason=f"Live execution started via {reason}.")
        try:
            response = await self._risk_service.execute_order(order_request)
            self._reset_failures()
            return self._set_signal_status(
                signal_id,
                status="executed",
                reason=f"Order accepted by Pionex via {reason}.",
                order_id=response.order_id,
                execution_result=response.model_dump(mode="json"),
            )
        except Exception as exc:
            self._register_failure(str(exc))
            return self._set_signal_status(
                signal_id,
                status="failed",
                reason=f"Execution failed via {reason}: {exc}",
                execution_result={"error": str(exc)},
            )

    def _automation_blockers(self, *, strict_stream: bool) -> list[str]:
        blockers: list[str] = []
        with SessionLocal() as db:
            control = self.ensure_control(db)
            if control.kill_switch_enabled:
                blockers.append(control.kill_switch_reason or "Kill-switch is engaged.")

            if self._settings.enable_private_api:
                latest_snapshot = db.scalar(
                    select(models.AccountSnapshot).order_by(desc(models.AccountSnapshot.snapshot_time))
                )
                if latest_snapshot is None:
                    blockers.append("No synced account snapshot is available for unattended execution.")
                else:
                    age_seconds = (datetime.now(timezone.utc) - latest_snapshot.snapshot_time).total_seconds()
                    if age_seconds > self._settings.automation_sync_stale_seconds:
                        blockers.append(
                            f"Account sync is stale by {age_seconds:.0f}s, which breaches the automation circuit breaker."
                        )

            if strict_stream and self._settings.enable_websocket_monitoring and self._stream_service is not None:
                private_status = self._stream_service.private_status
                if self._settings.enable_private_api and self._private_client.is_configured and private_status.last_error:
                    blockers.append(f"Private websocket monitoring is unhealthy: {private_status.last_error}")

        return blockers

    def _store_receipt(self, db, signal: NormalizedSignal) -> None:
        payload_hash = hashlib.sha256(
            json.dumps(signal.raw_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        receipt = models.WebhookReceipt(
            source=signal.source,
            delivery_key=signal.source_signal_id,
            payload_hash=payload_hash,
            payload_json=signal.raw_payload,
        )
        db.add(receipt)

    def _upsert_alert(
        self,
        db,
        *,
        code: str,
        severity: str,
        message: str,
        payload: dict[str, Any],
    ) -> None:
        alert = db.scalar(select(models.AutomationAlert).where(models.AutomationAlert.code == code))
        now = datetime.now(timezone.utc)
        if alert is None:
            alert = models.AutomationAlert(
                code=code,
                severity=severity,
                message=message,
                active=True,
                payload_json=payload,
                created_at=now,
                updated_at=now,
            )
            db.add(alert)
            return
        alert.severity = severity
        alert.message = message
        alert.payload_json = payload
        alert.active = True
        alert.updated_at = now
        alert.resolved_at = None

    def _resolve_alert(self, db, code: str) -> None:
        alert = db.scalar(select(models.AutomationAlert).where(models.AutomationAlert.code == code))
        if alert is None or not alert.active:
            return
        alert.active = False
        alert.resolved_at = datetime.now(timezone.utc)

    def _register_failure(self, message: str) -> None:
        with SessionLocal() as db:
            control = self.ensure_control(db)
            control.consecutive_failures += 1
            control.last_automation_error = message
            if control.consecutive_failures >= self._settings.automation_max_consecutive_failures:
                control.kill_switch_enabled = True
                if not control.kill_switch_reason:
                    control.kill_switch_reason = "Kill-switch engaged after consecutive automation failures."
            db.commit()

    def _reset_failures(self) -> None:
        with SessionLocal() as db:
            control = self.ensure_control(db)
            control.consecutive_failures = 0
            control.last_automation_error = ""
            db.commit()

    def _event_age_seconds(self, event_time: datetime | None, now: datetime) -> float | None:
        if event_time is None:
            return None
        return (now - event_time).total_seconds()

    def _first_text(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _normalize_side(self, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().upper()
        if text in {"BUY", "LONG", "ENTRY_LONG", "OPEN_LONG"}:
            return "BUY"
        if text in {"SELL", "SHORT", "ENTRY_SHORT", "OPEN_SHORT"}:
            return "SELL"
        return None

    def _to_optional_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _fallback_signal_id(self, payload: dict[str, Any], *, symbol: str, side: str) -> str:
        timestamp_value = self._first_text(payload, "timestamp", "time", "sent_at") or str(int(datetime.now(timezone.utc).timestamp()))
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
        return f"{symbol}-{side}-{timestamp_value}-{digest}"
