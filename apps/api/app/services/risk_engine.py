from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite

from .. import models
from ..schemas import TradeCheckRequest


@dataclass(slots=True)
class RiskCheckLine:
    name: str
    passed: bool
    detail: str
    metric: float | None = None
    threshold: float | None = None


@dataclass(slots=True)
class TradeEvaluation:
    allowed: bool
    blocked_reasons: list[str]
    warnings: list[str]
    estimated_risk_amount: float
    estimated_risk_pct: float
    estimated_position_notional: float
    estimated_margin_required: float
    estimated_portfolio_heat_pct: float
    estimated_symbol_exposure_pct: float
    stop_distance_pct: float
    checks: list[RiskCheckLine]
    market_score: models.CoinScore | None


class RiskEngine:
    def evaluate(
        self,
        *,
        policy: models.RiskPolicy,
        account_snapshot: models.AccountSnapshot | None,
        positions: list[models.PositionSnapshot],
        market_score: models.CoinScore | None,
        trade: TradeCheckRequest,
        daily_loss_remaining_pct: float,
        weekly_loss_remaining_pct: float,
    ) -> TradeEvaluation:
        checks: list[RiskCheckLine] = []
        blocked_reasons: list[str] = []
        warnings: list[str] = []

        equity = account_snapshot.account_equity if account_snapshot else 0.0
        available_margin = account_snapshot.available_margin if account_snapshot else 0.0
        total_initial_margin = account_snapshot.total_initial_margin if account_snapshot else 0.0
        symbol_positions = [position for position in positions if position.symbol == trade.symbol]
        symbol_notional = sum(position.notional_value for position in symbol_positions)
        open_position_count = sum(1 for position in positions if abs(position.net_size) > 0)

        effective_leverage = trade.planned_leverage
        if effective_leverage is None:
            effective_leverage = next((position.leverage for position in symbol_positions if position.leverage > 0), 1.0)
        effective_leverage = max(effective_leverage, 1.0)

        position_notional = abs(trade.entry_price * trade.size)
        margin_required = position_notional / effective_leverage if effective_leverage else position_notional
        projected_heat_pct = ((total_initial_margin + margin_required) / equity * 100) if equity > 0 else inf
        projected_symbol_exposure_pct = ((symbol_notional + position_notional) / equity * 100) if equity > 0 else inf

        stop_distance_pct = 0.0
        risk_amount = 0.0
        if trade.stop_price is not None and trade.entry_price > 0:
            stop_distance_pct = abs(trade.entry_price - trade.stop_price) / trade.entry_price * 100
            if trade.side == "BUY":
                risk_amount = max(trade.entry_price - trade.stop_price, 0.0) * trade.size
            else:
                risk_amount = max(trade.stop_price - trade.entry_price, 0.0) * trade.size

        risk_pct = (risk_amount / equity * 100) if equity > 0 else inf

        def finite(value: float | None) -> float | None:
            if value is None:
                return None
            return value if isfinite(value) else None

        def add_check(
            *,
            name: str,
            passed: bool,
            detail: str,
            metric: float | None = None,
            threshold: float | None = None,
            blocking: bool = True,
        ) -> None:
            checks.append(
                RiskCheckLine(
                    name=name,
                    passed=passed,
                    detail=detail,
                    metric=finite(metric),
                    threshold=finite(threshold),
                )
            )
            if blocking and not passed:
                blocked_reasons.append(detail)

        add_check(
            name="Account Sync",
            passed=account_snapshot is not None and equity > 0,
            detail="Private account sync is required before a trade can be approved.",
            blocking=True,
        )

        if policy.require_stop_loss:
            add_check(
                name="Stop Required",
                passed=trade.stop_price is not None,
                detail="A stop price is required by policy before a trade can be approved.",
                blocking=True,
            )
        elif trade.stop_price is None:
            warnings.append("No stop price was provided, so the risk estimate is incomplete.")

        stop_direction_valid = True
        if trade.stop_price is not None:
            if trade.side == "BUY":
                stop_direction_valid = trade.stop_price < trade.entry_price
            else:
                stop_direction_valid = trade.stop_price > trade.entry_price
        add_check(
            name="Directional Stop",
            passed=stop_direction_valid,
            detail="The stop must sit below entry for longs and above entry for shorts.",
            blocking=trade.stop_price is not None,
        )

        add_check(
            name="Risk Per Trade",
            passed=risk_pct <= policy.max_risk_per_trade_pct,
            detail=f"Estimated stop loss risk is {risk_pct:.2f}% of equity, above the {policy.max_risk_per_trade_pct:.2f}% cap.",
            metric=risk_pct,
            threshold=policy.max_risk_per_trade_pct,
            blocking=trade.stop_price is not None,
        )
        add_check(
            name="Portfolio Heat",
            passed=projected_heat_pct <= policy.max_portfolio_heat_pct,
            detail=f"Projected portfolio heat is {projected_heat_pct:.2f}% of equity, above the {policy.max_portfolio_heat_pct:.2f}% limit.",
            metric=projected_heat_pct,
            threshold=policy.max_portfolio_heat_pct,
        )
        add_check(
            name="Symbol Exposure",
            passed=projected_symbol_exposure_pct <= policy.max_symbol_exposure_pct,
            detail=f"Projected exposure in {trade.symbol} is {projected_symbol_exposure_pct:.2f}% of equity, above the {policy.max_symbol_exposure_pct:.2f}% limit.",
            metric=projected_symbol_exposure_pct,
            threshold=policy.max_symbol_exposure_pct,
        )
        add_check(
            name="Open Positions",
            passed=open_position_count + (0 if symbol_positions else 1) <= policy.max_open_positions,
            detail=f"Approving this trade would push the account above the {policy.max_open_positions} open-position cap.",
            metric=float(open_position_count + (0 if symbol_positions else 1)),
            threshold=float(policy.max_open_positions),
        )
        add_check(
            name="Leverage",
            passed=effective_leverage <= policy.max_allowed_leverage,
            detail=f"Requested leverage of {effective_leverage:.2f}x is above the {policy.max_allowed_leverage:.2f}x cap.",
            metric=effective_leverage,
            threshold=policy.max_allowed_leverage,
        )
        if trade.stop_price is not None:
            add_check(
                name="Stop Distance",
                passed=stop_distance_pct >= policy.min_stop_distance_pct,
                detail=f"Stop distance is {stop_distance_pct:.2f}%, below the {policy.min_stop_distance_pct:.2f}% minimum buffer.",
                metric=stop_distance_pct,
                threshold=policy.min_stop_distance_pct,
            )
        add_check(
            name="Daily Loss Lockout",
            passed=daily_loss_remaining_pct > 0,
            detail="The account has exhausted the allowed daily loss budget.",
            metric=daily_loss_remaining_pct,
            threshold=0.0,
        )
        add_check(
            name="Weekly Loss Lockout",
            passed=weekly_loss_remaining_pct > 0,
            detail="The account has exhausted the allowed weekly loss budget.",
            metric=weekly_loss_remaining_pct,
            threshold=0.0,
        )

        if market_score:
            if policy.block_longs_when_buyers_left and trade.side == "BUY":
                add_check(
                    name="Buyer-Absence Filter",
                    passed=market_score.buyer_absence_score < policy.buyer_absence_block_score,
                    detail=(
                        f"{trade.symbol} is in a weak-bid state with buyer-absence score "
                        f"{market_score.buyer_absence_score:.1f}/100."
                    ),
                    metric=market_score.buyer_absence_score,
                    threshold=policy.buyer_absence_block_score,
                )
            if policy.block_new_trades_in_dead_market:
                add_check(
                    name="Dead-Market Filter",
                    passed=market_score.dead_market_score < policy.dead_market_block_score,
                    detail=(
                        f"{trade.symbol} is too inactive for fresh risk right now with dead-market score "
                        f"{market_score.dead_market_score:.1f}/100."
                    ),
                    metric=market_score.dead_market_score,
                    threshold=policy.dead_market_block_score,
                )

            if trade.side == "BUY" and market_score.bearish_score > market_score.bullish_score:
                warnings.append("The current market tape is scoring more bearish than bullish for this symbol.")
            if trade.side == "SELL" and market_score.bullish_score > market_score.bearish_score:
                warnings.append("The current market tape is scoring more bullish than bearish for this symbol.")
            if market_score.quiet_rally_score >= 60 and trade.side == "BUY":
                warnings.append("This symbol is coming from a quiet-then-rally structure; avoid chasing if the latest leg is extended.")
        else:
            warnings.append("No fresh market score was found for this symbol, so setup filters could not be applied.")

        if available_margin > 0 and margin_required > available_margin:
            blocked_reasons.append("Estimated required margin exceeds currently available margin.")
            checks.append(
                RiskCheckLine(
                    name="Available Margin",
                    passed=False,
                    detail="Estimated required margin exceeds currently available margin.",
                    metric=margin_required,
                    threshold=available_margin,
                )
            )

        allowed = not blocked_reasons
        return TradeEvaluation(
            allowed=allowed,
            blocked_reasons=blocked_reasons,
            warnings=warnings,
            estimated_risk_amount=risk_amount,
            estimated_risk_pct=risk_pct if risk_pct != inf else 0.0,
            estimated_position_notional=position_notional,
            estimated_margin_required=margin_required,
            estimated_portfolio_heat_pct=projected_heat_pct if projected_heat_pct != inf else 0.0,
            estimated_symbol_exposure_pct=projected_symbol_exposure_pct if projected_symbol_exposure_pct != inf else 0.0,
            stop_distance_pct=stop_distance_pct,
            checks=checks,
            market_score=market_score,
        )
