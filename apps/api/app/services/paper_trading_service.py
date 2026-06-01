from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import desc, select

from .. import models
from ..config import Settings
from ..db import SessionLocal
from ..schemas import (
    PaperAccountRead,
    PaperCloseRequest,
    PaperOrderRequest,
    PaperPositionRead,
    PaperSummaryResponse,
    PaperTradeResponse,
)


class PaperTradingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def ensure_account(self, db) -> models.PaperAccount:
        account = db.get(models.PaperAccount, 1)
        if account is None:
            account = models.PaperAccount(
                id=1,
                starting_balance=self._settings.paper_starting_balance,
                cash_balance=self._settings.paper_starting_balance,
                default_trade_size=self._settings.paper_default_trade_size,
                default_leverage=self._settings.paper_default_leverage,
                commission_rate=self._settings.paper_commission_rate,
                default_stop_loss_pct=self._settings.paper_default_stop_loss_pct,
                default_take_profit_pct=self._settings.paper_default_take_profit_pct,
                default_trailing_stop_pct=self._settings.paper_default_trailing_stop_pct,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
        return account

    def summary(self) -> PaperSummaryResponse:
        with SessionLocal() as db:
            account = self.ensure_account(db)
            open_positions = db.scalars(
                select(models.PaperPosition)
                .where(models.PaperPosition.status == "open")
                .order_by(desc(models.PaperPosition.opened_at))
            ).all()
            closed_positions = db.scalars(
                select(models.PaperPosition)
                .where(models.PaperPosition.status == "closed")
                .order_by(desc(models.PaperPosition.closed_at))
                .limit(50)
            ).all()

            open_reads = [self._position_read(position) for position in open_positions]
            closed_reads = [self._position_read(position) for position in closed_positions]
            wins = sum(1 for position in closed_positions if position.realized_pnl > 0)
            trade_count = len(closed_positions)
            hold_minutes = [
                (position.closed_at - position.opened_at).total_seconds() / 60
                for position in closed_positions
                if position.closed_at is not None
            ]
            unrealized = sum(position.unrealized_pnl for position in open_reads)

            return PaperSummaryResponse(
                account=PaperAccountRead(
                    starting_balance=account.starting_balance,
                    cash_balance=account.cash_balance,
                    realized_pnl=account.realized_pnl,
                    unrealized_pnl=unrealized,
                    equity=account.cash_balance + unrealized,
                    commission_paid=account.commission_paid,
                    default_trade_size=account.default_trade_size,
                    default_leverage=account.default_leverage,
                    commission_rate=account.commission_rate,
                    default_stop_loss_pct=account.default_stop_loss_pct,
                    default_take_profit_pct=account.default_take_profit_pct,
                    default_trailing_stop_pct=account.default_trailing_stop_pct,
                ),
                open_positions=open_reads,
                closed_positions=closed_reads,
                win_rate=(wins / trade_count) * 100 if trade_count else 0.0,
                trade_count=trade_count,
                average_hold_minutes=sum(hold_minutes) / len(hold_minutes) if hold_minutes else None,
            )

    def open_position(self, payload: PaperOrderRequest) -> PaperTradeResponse:
        with SessionLocal() as db:
            account = self.ensure_account(db)
            size = payload.size or account.default_trade_size
            leverage = payload.leverage or account.default_leverage
            notional = size * leverage
            margin_used = size
            entry_fee = notional * account.commission_rate
            if account.cash_balance < margin_used + entry_fee:
                raise HTTPException(status_code=400, detail="Paper account has insufficient buying power.")

            if payload.side == "LONG":
                stop_loss = payload.stop_loss or payload.entry_price * (1 - account.default_stop_loss_pct / 100)
                take_profit = payload.take_profit or payload.entry_price * (1 + account.default_take_profit_pct / 100)
            else:
                stop_loss = payload.stop_loss or payload.entry_price * (1 + account.default_stop_loss_pct / 100)
                take_profit = payload.take_profit or payload.entry_price * (1 - account.default_take_profit_pct / 100)

            account.cash_balance -= margin_used + entry_fee
            account.commission_paid += entry_fee
            position = models.PaperPosition(
                symbol=payload.symbol.upper(),
                side=payload.side,
                entry_price=payload.entry_price,
                current_price=payload.entry_price,
                size=size,
                leverage=leverage,
                margin_used=margin_used,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop_pct=payload.trailing_stop_pct if payload.trailing_stop_pct is not None else account.default_trailing_stop_pct,
                highest_price=payload.entry_price,
                lowest_price=payload.entry_price,
                fees_paid=entry_fee,
            )
            db.add(position)
            self._log(db, "paper_trade", "info", f"Opened paper {payload.side} on {payload.symbol}.", {"position": payload.model_dump()})
            db.commit()
            db.refresh(position)
            return PaperTradeResponse(ok=True, position=self._position_read(position), message="Paper position opened.")

    def close_position(self, position_id: int, payload: PaperCloseRequest) -> PaperTradeResponse:
        with SessionLocal() as db:
            account = self.ensure_account(db)
            position = db.get(models.PaperPosition, position_id)
            if position is None:
                raise HTTPException(status_code=404, detail="Paper position not found.")
            if position.status != "open":
                raise HTTPException(status_code=400, detail="Paper position is already closed.")

            gross = self._pnl(position, payload.close_price)
            exit_fee = (position.size * position.leverage) * account.commission_rate
            net = gross - exit_fee
            position.status = "closed"
            position.current_price = payload.close_price
            position.close_price = payload.close_price
            position.close_reason = payload.reason
            position.realized_pnl = net
            position.fees_paid += exit_fee
            position.closed_at = datetime.now(timezone.utc)
            account.cash_balance += position.margin_used + net
            account.realized_pnl += net
            account.commission_paid += exit_fee
            self._log(db, "paper_trade", "info", f"Closed paper {position.side} on {position.symbol}.", {"position_id": position.id, "pnl": net})
            db.commit()
            db.refresh(position)
            return PaperTradeResponse(ok=True, position=self._position_read(position), message="Paper position closed.")

    def _pnl(self, position: models.PaperPosition, price: float) -> float:
        quantity = (position.size * position.leverage) / position.entry_price
        if position.side == "LONG":
            return (price - position.entry_price) * quantity
        return (position.entry_price - price) * quantity

    def _position_read(self, position: models.PaperPosition) -> PaperPositionRead:
        unrealized = 0.0 if position.status == "closed" else self._pnl(position, position.current_price)
        liquidation_warning = None
        if position.leverage > 0:
            distance_pct = 100 / position.leverage
            liquidation_warning = f"Approx. liquidation danger if price moves about {distance_pct:.1f}% against entry."
        return PaperPositionRead(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            status=position.status,
            entry_price=position.entry_price,
            current_price=position.current_price,
            size=position.size,
            leverage=position.leverage,
            margin_used=position.margin_used,
            unrealized_pnl=unrealized,
            realized_pnl=position.realized_pnl,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            trailing_stop_pct=position.trailing_stop_pct,
            liquidation_warning=liquidation_warning,
            opened_at=position.opened_at,
            closed_at=position.closed_at,
        )

    def _log(self, db, category: str, severity: str, message: str, payload: dict) -> None:
        db.add(models.CopilotLog(category=category, severity=severity, message=message, payload_json=payload))
