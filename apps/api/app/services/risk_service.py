from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import asc, desc, func, select

from .. import models
from ..config import Settings
from ..db import SessionLocal
from ..schemas import (
    AccountBalanceRead,
    ArmManagedExitRequest,
    CancelAllOrdersRequest,
    ManagedExitEventRead,
    ManagedExitPlanRead,
    MarketRiskContextRead,
    OrderExecutionResponse,
    OrderSnapshotRead,
    PositionSnapshotRead,
    RiskBreachRead,
    RiskPolicyRead,
    RiskSummaryResponse,
    RiskQuoteStateRead,
    TradeCheckLineRead,
    TradeCheckRequest,
    TradeCheckResponse,
    TradePlanRequest,
    TradePlanResponse,
)
from .private_pionex_client import (
    PionexAccountBalance,
    PionexAccountDetail,
    PionexOpenOrder,
    PionexPrivateClientError,
    PrivatePionexClient,
)
from .risk_engine import RiskEngine
from .risk_policy_service import RiskPolicyService
from .exit_automation_service import model_to_managed_exit_schema


@dataclass(slots=True)
class RiskSyncStatus:
    running: bool = False
    last_run_started_at: datetime | None = None
    last_run_completed_at: datetime | None = None
    last_error: str | None = None


class RiskService:
    def __init__(
        self,
        settings: Settings,
        private_client: PrivatePionexClient,
        policy_service: RiskPolicyService,
    ) -> None:
        self._settings = settings
        self._private_client = private_client
        self._policy_service = policy_service
        self._engine = RiskEngine()
        self._lock = asyncio.Lock()
        self._status = RiskSyncStatus()
        self._exit_automation_service = None
        self._automation_service = None

    def set_exit_automation_service(self, service) -> None:
        self._exit_automation_service = service

    def set_automation_service(self, service) -> None:
        self._automation_service = service

    @property
    def status(self) -> RiskSyncStatus:
        return self._status

    async def sync_account_state(self, force: bool = False, raise_on_rate_limit: bool = False) -> models.AccountSnapshot | None:
        if not self._settings.enable_private_api or not self._private_client.is_configured:
            self._status.last_error = None
            return None

        async with self._lock:
            now = datetime.now(timezone.utc)
            self._status.running = True
            self._status.last_run_started_at = now
            self._status.last_error = None
            try:
                with SessionLocal() as db:
                    latest_snapshot = self._latest_account_snapshot(db)
                if (
                    not force
                    and latest_snapshot is not None
                    and (now - latest_snapshot.snapshot_time).total_seconds() < self._settings.risk_sync_min_interval_seconds
                ):
                    self._status.last_run_completed_at = latest_snapshot.snapshot_time
                    return latest_snapshot

                account_detail = await self._private_client.get_account_detail()
                open_orders = await self._private_client.get_open_orders(limit=100)
                snapshot_time = datetime.now(timezone.utc)
                with SessionLocal() as db:
                    self._policy_service.ensure_policy(db)
                    snapshot = self._persist_snapshot(db, account_detail, open_orders, snapshot_time)
                self._status.last_run_completed_at = snapshot_time
                return snapshot
            except PionexPrivateClientError as exc:
                self._status.last_error = str(exc)
                if exc.is_rate_limited and not raise_on_rate_limit:
                    return None
                raise
            except Exception as exc:
                self._status.last_error = str(exc)
                raise
            finally:
                self._status.running = False

    def get_policy(self) -> models.RiskPolicy:
        return self._policy_service.get_policy()

    def update_policy(self, payload) -> models.RiskPolicy:
        return self._policy_service.update_policy(payload)

    def build_summary(self) -> RiskSummaryResponse:
        with SessionLocal() as db:
            policy = self._policy_service.ensure_policy(db)
            snapshot = self._latest_account_snapshot(db)
            positions, orders = self._latest_positions_and_orders(db, snapshot)
            daily_pnl, weekly_pnl = self._compute_period_pnl(db, snapshot)
            managed_exits = self._managed_exits(db)
            exit_events = self._recent_exit_events(db)
            return self._summary_from_state(
                policy,
                snapshot,
                positions,
                orders,
                daily_pnl,
                weekly_pnl,
                managed_exits,
                exit_events,
            )

    def check_trade(self, payload: TradeCheckRequest) -> TradeCheckResponse:
        with SessionLocal() as db:
            policy = self._policy_service.ensure_policy(db)
            snapshot = self._latest_account_snapshot(db)
            positions, _orders = self._latest_positions_and_orders(db, snapshot)
            daily_pnl, weekly_pnl = self._compute_period_pnl(db, snapshot)
            account_equity = snapshot.account_equity if snapshot else 0.0
            daily_loss_used_pct = ((-daily_pnl / account_equity) * 100) if account_equity > 0 and daily_pnl < 0 else 0.0
            weekly_loss_used_pct = ((-weekly_pnl / account_equity) * 100) if account_equity > 0 and weekly_pnl < 0 else 0.0
            market_score = self._latest_market_score(db, payload.symbol)
            evaluation = self._engine.evaluate(
                policy=policy,
                account_snapshot=snapshot,
                positions=positions,
                market_score=market_score,
                trade=payload,
                daily_loss_remaining_pct=max(policy.max_daily_loss_pct - daily_loss_used_pct, 0.0),
                weekly_loss_remaining_pct=max(policy.max_weekly_loss_pct - weekly_loss_used_pct, 0.0),
            )
        return self._trade_response(evaluation)

    def plan_trade(self, payload: TradePlanRequest) -> TradePlanResponse:
        with SessionLocal() as db:
            policy = self._policy_service.ensure_policy(db)
            snapshot = self._latest_account_snapshot(db)
            market_score = self._latest_market_score(db, payload.symbol)
            market_snapshot = self._latest_market_snapshot(db, payload.symbol)

        if payload.entry_price is not None:
            entry_price = payload.entry_price
        elif market_snapshot is not None and market_snapshot.price > 0:
            entry_price = market_snapshot.price
        else:
            raise HTTPException(
                status_code=404,
                detail="No current market price is available for this symbol yet. Run the scanner first or enter an entry price manually.",
            )

        atr_percent = market_score.atr_percent if market_score and market_score.atr_percent > 0 else policy.min_stop_distance_pct
        stop_distance_pct = max(policy.min_stop_distance_pct, atr_percent * self._settings.default_stop_atr_multiplier)
        risk_reward_ratio = self._select_reward_multiple(payload.side, market_score)
        take_profit_distance_pct = stop_distance_pct * risk_reward_ratio

        if payload.side == "BUY":
            stop_price = entry_price * (1 - stop_distance_pct / 100)
            take_profit_price = entry_price * (1 + take_profit_distance_pct / 100)
        else:
            stop_price = entry_price * (1 + stop_distance_pct / 100)
            take_profit_price = entry_price * (1 - take_profit_distance_pct / 100)

        max_risk_amount = None
        suggested_size = None
        notes: list[str] = [
            f"Stop is based on ATR at {atr_percent:.2f}% with a {self._settings.default_stop_atr_multiplier:.2f}x volatility buffer.",
            f"Take profit is set at {risk_reward_ratio:.2f}R from entry.",
        ]

        per_unit_risk = abs(entry_price - stop_price)
        if snapshot is not None and snapshot.account_equity > 0 and per_unit_risk > 0:
            max_risk_amount = snapshot.account_equity * (policy.max_risk_per_trade_pct / 100)
            suggested_size = max_risk_amount / per_unit_risk
            notes.append(
                f"With current equity, the policy risk budget is {max_risk_amount:.2f} {snapshot.account_currency}."
            )
            if payload.size is not None and payload.size > suggested_size:
                notes.append(
                    f"Current size is above the policy-aligned size. Trim toward {suggested_size:.6f} to stay inside the risk budget."
                )
        elif payload.size is None:
            notes.append("No synced account equity was available, so size guidance could not be tied to your policy budget.")

        if market_score is not None:
            if payload.side == "BUY" and market_score.buyer_absence_score >= policy.buyer_absence_block_score:
                notes.append("This long setup is fighting a high buyer-absence reading, so the plan may not be worth taking.")
            if market_score.dead_market_score >= policy.dead_market_block_score:
                notes.append("This symbol is still scoring as a dead market. Breakout follow-through may be unreliable.")
            if payload.side == "BUY" and market_score.quiet_rally_score >= 60:
                notes.append("Quiet-then-rally structure is present, so the 2R target assumes you are buying early in the move, not late.")

        return TradePlanResponse(
            symbol=payload.symbol.upper(),
            side=payload.side,
            entry_price=entry_price,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            stop_distance_pct=stop_distance_pct,
            take_profit_distance_pct=take_profit_distance_pct,
            risk_reward_ratio=risk_reward_ratio,
            atr_percent=atr_percent,
            max_risk_amount=max_risk_amount,
            suggested_size=suggested_size,
            market_context=self._market_context(market_score),
            notes=notes,
        )

    async def execute_order(self, payload) -> OrderExecutionResponse:
        if not self._settings.enable_private_api or not self._private_client.is_configured:
            raise HTTPException(status_code=503, detail="Private API access is not configured yet.")
        if not self._settings.enable_trading:
            raise HTTPException(status_code=403, detail="Trading is disabled. Set FMR_ENABLE_TRADING=true only after you are comfortable with the guardrails.")
        if self._automation_service is not None:
            self._automation_service.raise_if_manual_execution_blocked()
        if payload.arm_exit_automation:
            if self._exit_automation_service is None:
                raise HTTPException(status_code=503, detail="Exit automation service is not available.")
            self._exit_automation_service.validate_arm_request(
                symbol=payload.symbol,
                position_side=payload.position_side,
                stop_price=payload.stop_price,
                take_profit_price=payload.take_profit_price,
            )

        check = self.check_trade(payload)
        if not check.allowed:
            raise HTTPException(status_code=400, detail={"message": "Trade blocked by policy.", "reasons": check.blocked_reasons})

        order_payload = {
            "clientOrderId": payload.client_order_id,
            "symbol": payload.symbol,
            "positionSide": payload.position_side,
            "side": payload.side,
            "type": payload.order_type,
            "size": f"{payload.size}",
            "price": f"{payload.entry_price}" if payload.order_type != "MARKET_QTY" else None,
            "reduceOnly": payload.reduce_only,
        }
        order_id = await self._private_client.place_order(order_payload)
        managed_exit_plan = None
        message = f"Order accepted by Pionex for {payload.symbol}."
        if payload.arm_exit_automation:
            try:
                managed_exit_plan = self._exit_automation_service.arm_from_order(
                    symbol=payload.symbol,
                    side=payload.side,
                    position_side=payload.position_side,
                    stop_price=payload.stop_price,
                    take_profit_price=payload.take_profit_price,
                    entry_order_id=order_id,
                    expected_entry_price=payload.entry_price,
                    expected_size=payload.size,
                )
                message = f"Order accepted by Pionex for {payload.symbol}, and managed exit automation is armed."
            except Exception as exc:
                message = (
                    f"Order accepted by Pionex for {payload.symbol}, but managed exit automation failed to arm: {exc}"
                )
        await self.sync_account_state(force=True)
        return OrderExecutionResponse(
            ok=True,
            order_id=order_id,
            message=message,
            check=check,
            managed_exit_plan=ManagedExitPlanRead.model_validate(managed_exit_plan, from_attributes=True) if managed_exit_plan else None,
        )

    async def cancel_all_orders(self, payload: CancelAllOrdersRequest) -> None:
        if not self._settings.enable_private_api or not self._private_client.is_configured:
            raise HTTPException(status_code=503, detail="Private API access is not configured yet.")
        if not self._settings.enable_trading:
            raise HTTPException(status_code=403, detail="Trading controls are disabled.")
        await self._private_client.cancel_all_orders(payload.symbol)
        await self.sync_account_state(force=True)

    def _persist_snapshot(
        self,
        db,
        account_detail: PionexAccountDetail,
        open_orders: list[PionexOpenOrder],
        snapshot_time: datetime,
    ) -> models.AccountSnapshot:
        primary = self._select_primary_balance(account_detail.balances)
        account_currency = primary.coin if primary else self._settings.risk_account_quote.upper()
        total_assets = primary.assets if primary else 0.0
        account_equity = max(total_assets + (primary.unrealized_pnl if primary else 0.0) - (primary.debts if primary else 0.0), 0.0)
        snapshot = models.AccountSnapshot(
            account_currency=account_currency,
            total_assets=total_assets,
            account_equity=account_equity,
            free_balance=primary.free if primary else 0.0,
            available_margin=primary.available if primary else 0.0,
            unrealized_pnl=primary.unrealized_pnl if primary else 0.0,
            total_initial_margin=primary.total_initial_margin if primary else 0.0,
            debts=primary.debts if primary else 0.0,
            balances_json=[
                {
                    "coin": balance.coin,
                    "assets": balance.assets,
                    "free": balance.free,
                    "frozen": balance.frozen,
                    "transferable": balance.transferable,
                    "available": balance.available,
                    "unrealized_pnl": balance.unrealized_pnl,
                    "total_initial_margin": balance.total_initial_margin,
                    "debts": balance.debts,
                }
                for balance in account_detail.balances
            ],
            quote_risks_json=[
                {"quote": risk.quote, "risk_state": risk.risk_state}
                for risk in account_detail.quote_risks
            ],
            snapshot_time=snapshot_time,
        )
        db.add(snapshot)
        db.flush()

        for position in account_detail.positions:
            db.add(
                models.PositionSnapshot(
                    snapshot_time=snapshot_time,
                    symbol=position.symbol,
                    position_id=position.position_id,
                    isolated_mode=position.isolated_mode,
                    risk_state=position.risk_state,
                    position_side=position.position_side,
                    net_size=position.net_size,
                    avg_price=position.avg_price,
                    mark_price=position.mark_price,
                    notional_value=position.notional_value,
                    initial_margin=position.initial_margin,
                    maint_margin=position.maint_margin,
                    liquidation_price=position.liquidation_price,
                    leverage=position.leverage,
                    unrealized_pnl=position.unrealized_pnl,
                    created_time=position.created_time,
                    updated_time=position.updated_time,
                )
            )

        for order in open_orders:
            db.add(
                models.OrderSnapshot(
                    snapshot_time=snapshot_time,
                    symbol=order.symbol,
                    order_id=order.order_id,
                    client_order_id=order.client_order_id,
                    side=order.side,
                    position_side=order.position_side,
                    order_type=order.order_type,
                    price=order.price,
                    size=order.size,
                    filled_size=order.filled_size,
                    reduce_only=order.reduce_only,
                    status=order.status,
                    created_time=order.created_time,
                    updated_time=order.updated_time,
                )
            )

        db.commit()
        db.refresh(snapshot)
        return snapshot

    def _select_primary_balance(self, balances: list[PionexAccountBalance]) -> PionexAccountBalance | None:
        if not balances:
            return None
        preferred_quote = self._settings.risk_account_quote.upper()
        preferred = next((balance for balance in balances if balance.coin.upper() == preferred_quote), None)
        if preferred:
            return preferred
        return max(balances, key=lambda balance: balance.assets + balance.unrealized_pnl - balance.debts)

    def _latest_account_snapshot(self, db) -> models.AccountSnapshot | None:
        return db.scalar(select(models.AccountSnapshot).order_by(desc(models.AccountSnapshot.snapshot_time)))

    def _latest_positions_and_orders(
        self,
        db,
        snapshot: models.AccountSnapshot | None,
    ) -> tuple[list[models.PositionSnapshot], list[models.OrderSnapshot]]:
        if snapshot is None:
            return [], []
        positions = db.scalars(
            select(models.PositionSnapshot)
            .where(models.PositionSnapshot.snapshot_time == snapshot.snapshot_time)
            .order_by(desc(models.PositionSnapshot.notional_value))
        ).all()
        orders = db.scalars(
            select(models.OrderSnapshot)
            .where(models.OrderSnapshot.snapshot_time == snapshot.snapshot_time)
            .order_by(desc(models.OrderSnapshot.created_time), asc(models.OrderSnapshot.symbol))
        ).all()
        return positions, orders

    def _period_start(self, now: datetime) -> tuple[datetime, datetime]:
        zone = ZoneInfo(self._settings.report_timezone)
        local_now = now.astimezone(zone)
        day_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start_local = day_start_local - timedelta(days=day_start_local.weekday())
        return day_start_local.astimezone(timezone.utc), week_start_local.astimezone(timezone.utc)

    def _compute_period_pnl(
        self,
        db,
        snapshot: models.AccountSnapshot | None,
    ) -> tuple[float, float]:
        if snapshot is None:
            return 0.0, 0.0

        day_start, week_start = self._period_start(snapshot.snapshot_time)
        first_day_snapshot = db.scalar(
            select(models.AccountSnapshot)
            .where(models.AccountSnapshot.snapshot_time >= day_start)
            .order_by(asc(models.AccountSnapshot.snapshot_time))
        )
        first_week_snapshot = db.scalar(
            select(models.AccountSnapshot)
            .where(models.AccountSnapshot.snapshot_time >= week_start)
            .order_by(asc(models.AccountSnapshot.snapshot_time))
        )

        daily_pnl = snapshot.account_equity - first_day_snapshot.account_equity if first_day_snapshot else 0.0
        weekly_pnl = snapshot.account_equity - first_week_snapshot.account_equity if first_week_snapshot else 0.0
        return daily_pnl, weekly_pnl

    def _latest_market_score(self, db, symbol: str) -> models.CoinScore | None:
        latest_time = db.scalar(select(func.max(models.CoinScore.report_time)))
        if latest_time is None:
            return None
        return db.scalar(
            select(models.CoinScore)
            .where(models.CoinScore.report_time == latest_time)
            .where(models.CoinScore.symbol == symbol.upper())
        )

    def _latest_market_snapshot(self, db, symbol: str) -> models.MarketSnapshot | None:
        latest_time = db.scalar(select(func.max(models.MarketSnapshot.timestamp)))
        if latest_time is None:
            return None
        return db.scalar(
            select(models.MarketSnapshot)
            .where(models.MarketSnapshot.timestamp == latest_time)
            .where(models.MarketSnapshot.symbol == symbol.upper())
        )

    def _market_context(self, market_score: models.CoinScore | None) -> MarketRiskContextRead | None:
        if market_score is None:
            return None
        return MarketRiskContextRead(
            symbol=market_score.symbol,
            trend_label=market_score.trend_label,
            activity_score=market_score.activity_score,
            bullish_score=market_score.bullish_score,
            bearish_score=market_score.bearish_score,
            buyer_absence_score=market_score.buyer_absence_score,
            dead_market_score=market_score.dead_market_score,
            quiet_rally_score=market_score.quiet_rally_score,
            price_change_5m=market_score.price_change_5m,
            price_change_15m=market_score.price_change_15m,
        )

    def _select_reward_multiple(self, side: str, market_score: models.CoinScore | None) -> float:
        reward = self._settings.default_take_profit_r_multiple
        if market_score is None:
            return reward
        if side == "BUY":
            if market_score.quiet_rally_score >= 60 and market_score.bullish_score >= market_score.bearish_score:
                return max(reward, 2.5)
            if market_score.bearish_score > market_score.bullish_score:
                return min(reward, 1.5)
        if side == "SELL":
            if market_score.bearish_score >= market_score.bullish_score:
                return max(reward, 2.2)
            if market_score.quiet_rally_score >= 60:
                return min(reward, 1.5)
        return reward

    def _liquidation_buffer_pct(self, position: models.PositionSnapshot) -> float:
        if position.mark_price <= 0 or position.liquidation_price <= 0:
            return 0.0
        return abs(position.mark_price - position.liquidation_price) / position.mark_price * 100

    def _summary_from_state(
        self,
        policy: models.RiskPolicy,
        snapshot: models.AccountSnapshot | None,
        positions: list[models.PositionSnapshot],
        orders: list[models.OrderSnapshot],
        daily_pnl: float,
        weekly_pnl: float,
        managed_exits: list[models.ManagedExitPlan],
        exit_events: list[models.ManagedExitEvent],
    ) -> RiskSummaryResponse:
        exit_status = self._exit_automation_service.status if self._exit_automation_service is not None else None
        if snapshot is None:
            message = None
            if not self._settings.enable_private_api:
                message = "Private account sync is disabled. Set FMR_ENABLE_PRIVATE_API=true to turn the radar into an account-aware risk console."
            elif not self._private_client.is_configured:
                message = "Add FMR_PIONEX_API_KEY and FMR_PIONEX_API_SECRET to enable account sync."
            else:
                message = "No account snapshot has been synced yet. Use Sync Account on the Risk page."

            return RiskSummaryResponse(
                private_api_enabled=self._settings.enable_private_api,
                private_api_configured=self._private_client.is_configured,
                trading_enabled=self._settings.enable_trading and self._private_client.is_configured,
                exit_automation_enabled=self._settings.enable_exit_automation,
                sync_running=self._status.running,
                exit_engine_running=bool(exit_status.running) if exit_status else False,
                last_synced_at=self._status.last_run_completed_at,
                last_exit_engine_at=exit_status.last_run_completed_at if exit_status else None,
                last_sync_error=self._status.last_error,
                last_exit_engine_error=exit_status.last_error if exit_status else None,
                message=message,
                account_currency=self._settings.risk_account_quote.upper(),
                total_assets=0.0,
                account_equity=0.0,
                free_balance=0.0,
                available_margin=0.0,
                unrealized_pnl=0.0,
                total_initial_margin=0.0,
                debts=0.0,
                daily_pnl=0.0,
                weekly_pnl=0.0,
                daily_loss_used_pct=0.0,
                weekly_loss_used_pct=0.0,
                daily_loss_remaining_pct=policy.max_daily_loss_pct,
                weekly_loss_remaining_pct=policy.max_weekly_loss_pct,
                portfolio_heat_pct=0.0,
                open_position_count=0,
                open_order_count=0,
                balances=[],
                risk_states=[],
                positions=[],
                orders=[],
                breaches=[],
                managed_exits=[ManagedExitPlanRead.model_validate(plan, from_attributes=True) for plan in managed_exits],
                exit_events=[ManagedExitEventRead.model_validate(event, from_attributes=True) for event in exit_events],
                policy=RiskPolicyRead.model_validate(policy),
            )

        equity = snapshot.account_equity
        portfolio_heat_pct = (snapshot.total_initial_margin / equity * 100) if equity > 0 else 0.0
        daily_loss_used_pct = ((-daily_pnl / equity) * 100) if equity > 0 and daily_pnl < 0 else 0.0
        weekly_loss_used_pct = ((-weekly_pnl / equity) * 100) if equity > 0 and weekly_pnl < 0 else 0.0
        breaches = self._build_breaches(policy, snapshot, positions, daily_loss_used_pct, weekly_loss_used_pct, portfolio_heat_pct)

        return RiskSummaryResponse(
            private_api_enabled=self._settings.enable_private_api,
            private_api_configured=self._private_client.is_configured,
            trading_enabled=self._settings.enable_trading and self._private_client.is_configured,
            exit_automation_enabled=self._settings.enable_exit_automation,
            sync_running=self._status.running,
            exit_engine_running=bool(exit_status.running) if exit_status else False,
            last_synced_at=snapshot.snapshot_time,
            last_exit_engine_at=exit_status.last_run_completed_at if exit_status else None,
            last_sync_error=self._status.last_error,
            last_exit_engine_error=exit_status.last_error if exit_status else None,
            message=None,
            account_currency=snapshot.account_currency,
            total_assets=snapshot.total_assets,
            account_equity=snapshot.account_equity,
            free_balance=snapshot.free_balance,
            available_margin=snapshot.available_margin,
            unrealized_pnl=snapshot.unrealized_pnl,
            total_initial_margin=snapshot.total_initial_margin,
            debts=snapshot.debts,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            daily_loss_used_pct=daily_loss_used_pct,
            weekly_loss_used_pct=weekly_loss_used_pct,
            daily_loss_remaining_pct=max(policy.max_daily_loss_pct - daily_loss_used_pct, 0.0),
            weekly_loss_remaining_pct=max(policy.max_weekly_loss_pct - weekly_loss_used_pct, 0.0),
            portfolio_heat_pct=portfolio_heat_pct,
            open_position_count=len([position for position in positions if abs(position.net_size) > 0]),
            open_order_count=len(orders),
            balances=[
                AccountBalanceRead(
                    coin=item.get("coin", ""),
                    assets=float(item.get("assets", 0.0)),
                    free=float(item.get("free", 0.0)),
                    frozen=float(item.get("frozen", 0.0)),
                    transferable=float(item.get("transferable", 0.0)),
                    available=float(item.get("available", 0.0)),
                    unrealized_pnl=float(item.get("unrealized_pnl", 0.0)),
                    total_initial_margin=float(item.get("total_initial_margin", 0.0)),
                    debts=float(item.get("debts", 0.0)),
                )
                for item in (snapshot.balances_json or [])
            ],
            risk_states=[
                RiskQuoteStateRead(
                    quote=item.get("quote", ""),
                    risk_state=item.get("risk_state", ""),
                )
                for item in (snapshot.quote_risks_json or [])
            ],
            positions=[
                PositionSnapshotRead(
                    symbol=position.symbol,
                    position_id=position.position_id,
                    isolated_mode=position.isolated_mode,
                    risk_state=position.risk_state,
                    position_side=position.position_side,
                    net_size=position.net_size,
                    avg_price=position.avg_price,
                    mark_price=position.mark_price,
                    notional_value=position.notional_value,
                    initial_margin=position.initial_margin,
                    maint_margin=position.maint_margin,
                    liquidation_price=position.liquidation_price,
                    liquidation_buffer_pct=self._liquidation_buffer_pct(position),
                    leverage=position.leverage,
                    unrealized_pnl=position.unrealized_pnl,
                    snapshot_time=position.snapshot_time,
                )
                for position in positions
            ],
            orders=[
                OrderSnapshotRead(
                    symbol=order.symbol,
                    order_id=order.order_id,
                    client_order_id=order.client_order_id,
                    side=order.side,
                    position_side=order.position_side,
                    order_type=order.order_type,
                    price=order.price,
                    size=order.size,
                    filled_size=order.filled_size,
                    reduce_only=order.reduce_only,
                    status=order.status,
                    snapshot_time=order.snapshot_time,
                    created_time=order.created_time,
                    updated_time=order.updated_time,
                )
                for order in orders
            ],
            breaches=breaches,
            managed_exits=[ManagedExitPlanRead.model_validate(plan, from_attributes=True) for plan in managed_exits],
            exit_events=[ManagedExitEventRead.model_validate(event, from_attributes=True) for event in exit_events],
            policy=RiskPolicyRead.model_validate(policy),
        )

    def _managed_exits(self, db) -> list[models.ManagedExitPlan]:
        return db.scalars(
            select(models.ManagedExitPlan).order_by(desc(models.ManagedExitPlan.updated_at)).limit(12)
        ).all()

    def _recent_exit_events(self, db) -> list[models.ManagedExitEvent]:
        return db.scalars(
            select(models.ManagedExitEvent).order_by(desc(models.ManagedExitEvent.created_at)).limit(24)
        ).all()

    def _build_breaches(
        self,
        policy: models.RiskPolicy,
        snapshot: models.AccountSnapshot,
        positions: list[models.PositionSnapshot],
        daily_loss_used_pct: float,
        weekly_loss_used_pct: float,
        portfolio_heat_pct: float,
    ) -> list[RiskBreachRead]:
        breaches: list[RiskBreachRead] = []
        if daily_loss_used_pct >= policy.max_daily_loss_pct:
            breaches.append(
                RiskBreachRead(
                    code="DAILY_LOCKOUT",
                    severity="critical",
                    message="Daily loss budget has been exhausted. New discretionary risk should stay off.",
                )
            )
        if weekly_loss_used_pct >= policy.max_weekly_loss_pct:
            breaches.append(
                RiskBreachRead(
                    code="WEEKLY_LOCKOUT",
                    severity="critical",
                    message="Weekly loss budget has been exhausted. Reduce risk and stand down.",
                )
            )
        if portfolio_heat_pct >= policy.max_portfolio_heat_pct:
            breaches.append(
                RiskBreachRead(
                    code="HEAT_LIMIT",
                    severity="high",
                    message=f"Portfolio heat is running at {portfolio_heat_pct:.2f}% of equity.",
                )
            )
        if len([position for position in positions if abs(position.net_size) > 0]) > policy.max_open_positions:
            breaches.append(
                RiskBreachRead(
                    code="POSITION_COUNT",
                    severity="warning",
                    message="The account is carrying more open positions than the current policy allows.",
                )
            )
        for position in positions:
            buffer_pct = self._liquidation_buffer_pct(position)
            if position.leverage > policy.max_allowed_leverage:
                breaches.append(
                    RiskBreachRead(
                        code=f"LEVERAGE_{position.symbol}",
                        severity="high",
                        message=f"{position.symbol} is running at {position.leverage:.2f}x leverage.",
                    )
                )
            if buffer_pct and buffer_pct < policy.min_liquidation_buffer_pct:
                breaches.append(
                    RiskBreachRead(
                        code=f"LIQ_BUFFER_{position.symbol}",
                        severity="high",
                        message=f"{position.symbol} is only {buffer_pct:.2f}% away from liquidation.",
                    )
                )
            if position.risk_state and position.risk_state.upper() not in {"NORMAL", "SAFE", "OK"}:
                breaches.append(
                    RiskBreachRead(
                        code=f"RISK_STATE_{position.symbol}",
                        severity="warning",
                        message=f"{position.symbol} reports exchange risk state {position.risk_state}.",
                    )
                )
        if not breaches and snapshot.account_equity > 0:
            breaches.append(
                RiskBreachRead(
                    code="ALL_CLEAR",
                    severity="info",
                    message="No hard policy breaches are showing in the latest synced account state.",
                )
            )
        return breaches

    def _trade_response(self, evaluation) -> TradeCheckResponse:
        return TradeCheckResponse(
            allowed=evaluation.allowed,
            trading_enabled=self._settings.enable_trading,
            execution_available=self._settings.enable_trading and self._private_client.is_configured,
            blocked_reasons=evaluation.blocked_reasons,
            warnings=evaluation.warnings,
            estimated_risk_amount=evaluation.estimated_risk_amount,
            estimated_risk_pct=evaluation.estimated_risk_pct,
            estimated_position_notional=evaluation.estimated_position_notional,
            estimated_margin_required=evaluation.estimated_margin_required,
            estimated_portfolio_heat_pct=evaluation.estimated_portfolio_heat_pct,
            estimated_symbol_exposure_pct=evaluation.estimated_symbol_exposure_pct,
            stop_distance_pct=evaluation.stop_distance_pct,
            market_context=self._market_context(evaluation.market_score),
            checks=[
                TradeCheckLineRead(
                    name=check.name,
                    passed=check.passed,
                    detail=check.detail,
                    metric=check.metric,
                    threshold=check.threshold,
                )
                for check in evaluation.checks
            ],
        )
