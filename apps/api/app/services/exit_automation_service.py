from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import desc, select

from .. import models
from ..config import Settings
from ..db import SessionLocal
from ..schemas import ArmManagedExitRequest, ManagedExitPlanRead
from .private_pionex_client import PionexAccountDetail, PionexOpenOrder, PrivatePionexClient


ACTIVE_EXIT_STATUSES = {"pending_fill", "armed", "exit_submitted"}


@dataclass(slots=True)
class ExitAutomationRunResult:
    plans_checked: int = 0
    triggered: int = 0


@dataclass(slots=True)
class ExitAutomationStatus:
    running: bool = False
    last_run_started_at: datetime | None = None
    last_run_completed_at: datetime | None = None
    last_error: str | None = None


class ExitAutomationService:
    def __init__(self, settings: Settings, private_client: PrivatePionexClient) -> None:
        self._settings = settings
        self._private_client = private_client
        self._lock = asyncio.Lock()
        self._status = ExitAutomationStatus()

    @property
    def status(self) -> ExitAutomationStatus:
        return self._status

    async def run_once(self, reason: str = "scheduled") -> ExitAutomationRunResult:
        if not self._settings.enable_exit_automation:
            return ExitAutomationRunResult()
        if not self._settings.enable_private_api or not self._private_client.is_configured:
            self._status.last_error = "Private API is not configured for exit automation."
            return ExitAutomationRunResult()
        if not self._settings.enable_trading:
            self._status.last_error = "Trading is disabled, so exit automation will not fire."
            return ExitAutomationRunResult()

        async with self._lock:
            self._status.running = True
            self._status.last_run_started_at = datetime.now(timezone.utc)
            self._status.last_error = None
            result = ExitAutomationRunResult()
            try:
                with SessionLocal() as db:
                    active_plans = db.scalars(
                        select(models.ManagedExitPlan)
                        .where(models.ManagedExitPlan.status.in_(ACTIVE_EXIT_STATUSES))
                        .order_by(models.ManagedExitPlan.created_at)
                    ).all()
                result.plans_checked = len(active_plans)
                if not active_plans:
                    self._status.last_run_completed_at = datetime.now(timezone.utc)
                    return result

                account_detail = await self._private_client.get_account_detail()
                open_orders = await self._private_client.get_open_orders(limit=200)

                for plan in active_plans:
                    changed = await self._process_plan(plan.id, account_detail, open_orders, reason, None)
                    if changed == "triggered":
                        result.triggered += 1

                self._status.last_run_completed_at = datetime.now(timezone.utc)
                return result
            except Exception as exc:
                self._status.last_error = str(exc)
                raise
            finally:
                self._status.running = False

    async def handle_market_trade(self, *, symbol: str, trade_price: float, reason: str) -> None:
        await self._process_symbol(symbol=symbol, reason=reason, price_override=trade_price)

    async def handle_private_position_update(self, *, symbol: str, reason: str) -> None:
        await self._process_symbol(symbol=symbol, reason=reason, price_override=None)

    async def handle_private_execution_update(self, *, symbol: str, reason: str) -> None:
        await self._process_symbol(symbol=symbol, reason=reason, price_override=None)

    def arm_from_order(
        self,
        *,
        symbol: str,
        side: str,
        position_side: str,
        stop_price: float,
        take_profit_price: float,
        entry_order_id: str,
        expected_entry_price: float,
        expected_size: float,
    ) -> models.ManagedExitPlan:
        self.validate_arm_request(
            symbol=symbol,
            position_side=position_side,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
        )

        with SessionLocal() as db:
            self._ensure_no_active_plan(db, symbol, position_side)
            plan = models.ManagedExitPlan(
                symbol=symbol.upper(),
                entry_side=side,
                position_side=position_side,
                stop_price=stop_price,
                take_profit_price=take_profit_price,
                expected_entry_price=expected_entry_price,
                expected_size=expected_size,
                entry_order_id=entry_order_id,
                status="pending_fill",
            )
            db.add(plan)
            db.flush()
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="armed",
                severity="info",
                message="Managed exit plan created and waiting for the entry position to appear.",
                payload={
                    "symbol": plan.symbol,
                    "entry_side": side,
                    "stop_price": stop_price,
                    "take_profit_price": take_profit_price,
                    "expected_size": expected_size,
                },
            )
            db.commit()
            db.refresh(plan)
            return plan

    def validate_arm_request(
        self,
        *,
        symbol: str,
        position_side: str,
        stop_price: float | None,
        take_profit_price: float | None,
    ) -> None:
        self._assert_enabled()
        if position_side != "BOTH":
            raise HTTPException(
                status_code=400,
                detail="Live exit automation currently supports one-way mode only because Pionex documents reduceOnly for BOTH mode, not hedge mode.",
            )
        if stop_price is None or take_profit_price is None or stop_price <= 0 or take_profit_price <= 0:
            raise HTTPException(status_code=400, detail="Stop loss and take profit must both be set to arm live exit automation.")
        with SessionLocal() as db:
            self._ensure_no_active_plan(db, symbol, position_side)

    async def arm_existing_position(self, payload: ArmManagedExitRequest) -> models.ManagedExitPlan:
        self._assert_enabled()
        if payload.position_side != "BOTH":
            raise HTTPException(
                status_code=400,
                detail="Live exit automation currently supports one-way mode only because Pionex documents reduceOnly for BOTH mode, not hedge mode.",
            )

        account_detail = await self._private_client.get_account_detail()
        position = self._match_position(
            account_detail,
            symbol=payload.symbol.upper(),
            side=payload.side,
        )
        if position is None:
            raise HTTPException(status_code=404, detail="No live one-way position matching this symbol and side was found to arm.")

        with SessionLocal() as db:
            self._ensure_no_active_plan(db, payload.symbol.upper(), payload.position_side)
            plan = models.ManagedExitPlan(
                symbol=payload.symbol.upper(),
                entry_side=payload.side,
                position_side=payload.position_side,
                stop_price=payload.stop_price,
                take_profit_price=payload.take_profit_price,
                expected_entry_price=payload.entry_price or position.avg_price,
                expected_size=payload.expected_size or abs(position.net_size),
                active_size=abs(position.net_size),
                status="armed",
                activated_at=datetime.now(timezone.utc),
                last_mark_price=position.mark_price,
                last_checked_at=datetime.now(timezone.utc),
            )
            db.add(plan)
            db.flush()
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="armed",
                severity="info",
                message="Managed exit plan armed against an existing live position.",
                payload={"symbol": plan.symbol, "active_size": plan.active_size},
            )
            db.commit()
            db.refresh(plan)
            return plan

    def disarm_plan(self, plan_id: int) -> models.ManagedExitPlan:
        with SessionLocal() as db:
            plan = db.get(models.ManagedExitPlan, plan_id)
            if plan is None:
                raise HTTPException(status_code=404, detail="Managed exit plan not found.")
            if plan.status not in ACTIVE_EXIT_STATUSES:
                raise HTTPException(status_code=400, detail=f"Managed exit plan is already {plan.status}.")
            plan.status = "cancelled"
            plan.closed_at = datetime.now(timezone.utc)
            plan.last_error = ""
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="disarmed",
                severity="warning",
                message="Managed exit plan was manually disarmed.",
                payload={},
            )
            db.commit()
            db.refresh(plan)
            return plan

    def list_recent_plans(self, limit: int = 12) -> list[models.ManagedExitPlan]:
        with SessionLocal() as db:
            return db.scalars(
                select(models.ManagedExitPlan).order_by(desc(models.ManagedExitPlan.updated_at)).limit(limit)
            ).all()

    def list_recent_events(self, limit: int = 24) -> list[models.ManagedExitEvent]:
        with SessionLocal() as db:
            return db.scalars(
                select(models.ManagedExitEvent).order_by(desc(models.ManagedExitEvent.created_at)).limit(limit)
            ).all()

    def _assert_enabled(self) -> None:
        if not self._settings.enable_exit_automation:
            raise HTTPException(status_code=403, detail="Exit automation is disabled. Set FMR_ENABLE_EXIT_AUTOMATION=true to arm managed exits.")
        if not self._settings.enable_private_api or not self._private_client.is_configured:
            raise HTTPException(status_code=503, detail="Private API access is not configured yet.")
        if not self._settings.enable_trading:
            raise HTTPException(status_code=403, detail="Trading must be enabled before live exit automation can arm.")

    def _ensure_no_active_plan(self, db, symbol: str, position_side: str) -> None:
        existing = db.scalar(
            select(models.ManagedExitPlan)
            .where(models.ManagedExitPlan.symbol == symbol.upper())
            .where(models.ManagedExitPlan.position_side == position_side)
            .where(models.ManagedExitPlan.status.in_(ACTIVE_EXIT_STATUSES))
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"There is already an active managed exit plan for {symbol.upper()} in {position_side} mode.",
            )

    async def _process_plan(
        self,
        plan_id: int,
        account_detail: PionexAccountDetail,
        open_orders: list[PionexOpenOrder],
        reason: str,
        price_override: float | None,
    ) -> str | None:
        now = datetime.now(timezone.utc)
        open_order_ids = {order.order_id for order in open_orders}

        with SessionLocal() as db:
            plan = db.get(models.ManagedExitPlan, plan_id)
            if plan is None or plan.status not in ACTIVE_EXIT_STATUSES:
                return None

            matching_position = self._match_position(
                account_detail,
                symbol=plan.symbol,
                side=plan.entry_side,
            )
            plan.last_checked_at = now
            plan.last_mark_price = matching_position.mark_price if matching_position is not None else 0.0
            plan.active_size = abs(matching_position.net_size) if matching_position is not None else 0.0

            if plan.status == "pending_fill":
                outcome = self._handle_pending_fill(db, plan, matching_position, open_order_ids, now)
                db.commit()
                return outcome

            if plan.status == "armed":
                outcome = await self._handle_armed(db, plan, matching_position, now, reason, price_override)
                db.commit()
                return outcome

            if plan.status == "exit_submitted":
                outcome = await self._handle_exit_submitted(db, plan, matching_position, open_order_ids, now, reason)
                db.commit()
                return outcome

            db.commit()
            return None

    async def _process_symbol(self, *, symbol: str, reason: str, price_override: float | None) -> None:
        if not self._settings.enable_exit_automation:
            return
        if not self._settings.enable_private_api or not self._private_client.is_configured:
            return
        if not self._settings.enable_trading:
            return

        async with self._lock:
            with SessionLocal() as db:
                query = (
                    select(models.ManagedExitPlan)
                    .where(models.ManagedExitPlan.status.in_(ACTIVE_EXIT_STATUSES))
                    .order_by(models.ManagedExitPlan.created_at)
                )
                if symbol and symbol.upper() != "ALL":
                    query = query.where(models.ManagedExitPlan.symbol == symbol.upper())
                active_plans = db.scalars(query).all()

            if not active_plans:
                return

            account_detail = await self._private_client.get_account_detail()
            open_orders = await self._private_client.get_open_orders(limit=200)
            for plan in active_plans:
                current_price_override = price_override if plan.symbol == symbol.upper() else None
                await self._process_plan(plan.id, account_detail, open_orders, reason, current_price_override)

    def _handle_pending_fill(self, db, plan: models.ManagedExitPlan, matching_position, open_order_ids: set[str], now: datetime) -> str | None:
        if matching_position is not None and abs(matching_position.net_size) > 0:
            plan.status = "armed"
            plan.activated_at = now
            plan.active_size = abs(matching_position.net_size)
            plan.last_mark_price = matching_position.mark_price
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="fill_detected",
                severity="info",
                message="Entry fill detected and managed exit plan is now armed.",
                payload={"active_size": plan.active_size, "mark_price": plan.last_mark_price},
            )
            return None

        confirmation_deadline = plan.created_at + timedelta(seconds=self._settings.exit_automation_fill_confirmation_seconds)
        if now >= confirmation_deadline and plan.entry_order_id and plan.entry_order_id not in open_order_ids:
            plan.status = "error"
            plan.closed_at = now
            plan.last_error = "Could not confirm an open position or an active entry order before the fill confirmation window expired."
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="confirmation_timeout",
                severity="critical",
                message=plan.last_error,
                payload={"entry_order_id": plan.entry_order_id},
            )
        return None

    async def _handle_armed(
        self,
        db,
        plan: models.ManagedExitPlan,
        matching_position,
        now: datetime,
        reason: str,
        price_override: float | None,
    ) -> str | None:
        if matching_position is None or abs(matching_position.net_size) <= 0:
            plan.status = "closed"
            plan.closed_at = now
            plan.trigger_reason = "POSITION_GONE"
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="position_gone",
                severity="warning",
                message="Managed exit plan closed because the underlying position no longer exists.",
                payload={"reason": reason},
            )
            return None

        trigger_price = price_override if price_override is not None and price_override > 0 else matching_position.mark_price
        trigger = self._detect_trigger(plan, trigger_price)
        if trigger is None:
            return None

        await self._submit_reduce_only_exit(db, plan, matching_position.net_size, trigger_price, trigger, now)
        return "triggered"

    async def _handle_exit_submitted(
        self,
        db,
        plan: models.ManagedExitPlan,
        matching_position,
        open_order_ids: set[str],
        now: datetime,
        reason: str,
    ) -> str | None:
        if matching_position is None or abs(matching_position.net_size) <= 0:
            plan.status = "closed"
            plan.closed_at = now
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="closed",
                severity="info",
                message="Managed exit plan completed because the live position is no longer open.",
                payload={"reason": reason},
            )
            return None

        if plan.exit_order_id and plan.exit_order_id in open_order_ids:
            return None

        retry_ready = plan.last_exit_attempt_at is None or (
            now - plan.last_exit_attempt_at
        ).total_seconds() >= self._settings.exit_automation_retry_cooldown_seconds
        if not retry_ready:
            return None

        if plan.retries_used >= self._settings.exit_automation_max_retries:
            plan.status = "error"
            plan.closed_at = now
            plan.last_error = "Managed exit retries were exhausted while the position stayed open."
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="retry_exhausted",
                severity="critical",
                message=plan.last_error,
                payload={"last_trigger_price": plan.last_trigger_price},
            )
            return None

        await self._submit_reduce_only_exit(
            db,
            plan,
            matching_position.net_size,
            matching_position.mark_price,
            plan.trigger_reason or "RETRY",
            now,
        )
        return "triggered"

    def _detect_trigger(self, plan: models.ManagedExitPlan, mark_price: float) -> str | None:
        if mark_price <= 0:
            return None
        is_long = plan.entry_side == "BUY"
        if is_long and mark_price <= plan.stop_price:
            return "STOP_LOSS"
        if is_long and mark_price >= plan.take_profit_price:
            return "TAKE_PROFIT"
        if not is_long and mark_price >= plan.stop_price:
            return "STOP_LOSS"
        if not is_long and mark_price <= plan.take_profit_price:
            return "TAKE_PROFIT"
        return None

    async def _submit_reduce_only_exit(
        self,
        db,
        plan: models.ManagedExitPlan,
        live_net_size: float,
        mark_price: float,
        trigger_reason: str,
        now: datetime,
    ) -> None:
        if plan.position_side != "BOTH":
            raise HTTPException(status_code=400, detail="Managed exits currently support only one-way mode.")

        exit_side = "SELL" if live_net_size > 0 else "BUY"
        size = abs(live_net_size)
        client_order_id = f"fmr-exit-{plan.id}-{int(now.timestamp())}"
        try:
            order_id = await self._private_client.place_order(
                {
                    "clientOrderId": client_order_id,
                    "symbol": plan.symbol,
                    "positionSide": "BOTH",
                    "side": exit_side,
                    "type": "MARKET_QTY",
                    "size": f"{size}",
                    "reduceOnly": True,
                }
            )
            plan.status = "exit_submitted"
            plan.exit_order_id = order_id
            plan.trigger_reason = trigger_reason
            plan.last_trigger_price = mark_price
            plan.last_exit_attempt_at = now
            plan.retries_used += 1
            plan.last_error = ""
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="exit_submitted",
                severity="warning" if trigger_reason == "STOP_LOSS" else "info",
                message=f"Managed exit submitted as a reduce-only market order because {trigger_reason} was hit.",
                payload={"order_id": order_id, "trigger_price": mark_price, "size": size},
            )
        except Exception as exc:
            plan.last_exit_attempt_at = now
            plan.retries_used += 1
            plan.last_error = str(exc)
            severity = "critical" if plan.retries_used >= self._settings.exit_automation_max_retries else "error"
            if plan.retries_used >= self._settings.exit_automation_max_retries:
                plan.status = "error"
                plan.closed_at = now
            self._log_event(
                db,
                plan_id=plan.id,
                event_type="exit_submit_failed",
                severity=severity,
                message=f"Managed exit submission failed: {exc}",
                payload={"trigger_reason": trigger_reason, "trigger_price": mark_price, "retries_used": plan.retries_used},
            )

    def _match_position(self, account_detail: PionexAccountDetail, *, symbol: str, side: str):
        positions = [position for position in account_detail.positions if position.symbol == symbol.upper()]
        if side == "BUY":
            return next((position for position in positions if position.net_size > 0), None)
        return next((position for position in positions if position.net_size < 0), None)

    def _log_event(
        self,
        db,
        *,
        plan_id: int,
        event_type: str,
        severity: str,
        message: str,
        payload: dict[str, object],
    ) -> None:
        db.add(
            models.ManagedExitEvent(
                plan_id=plan_id,
                event_type=event_type,
                severity=severity,
                message=message,
                payload_json=payload,
            )
        )


def model_to_managed_exit_schema(plan: models.ManagedExitPlan) -> ManagedExitPlanRead:
    return ManagedExitPlanRead.model_validate(plan, from_attributes=True)
