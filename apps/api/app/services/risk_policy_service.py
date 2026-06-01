from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from ..config import Settings
from ..db import SessionLocal
from ..schemas import RiskPolicyUpdate


class RiskPolicyService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def ensure_policy(self, db: Session) -> models.RiskPolicy:
        policy = db.get(models.RiskPolicy, 1)
        if policy is None:
            policy = models.RiskPolicy(
                id=1,
                name="default",
                max_risk_per_trade_pct=self._settings.default_max_risk_per_trade_pct,
                max_daily_loss_pct=self._settings.default_max_daily_loss_pct,
                max_weekly_loss_pct=self._settings.default_max_weekly_loss_pct,
                max_portfolio_heat_pct=self._settings.default_max_portfolio_heat_pct,
                max_symbol_exposure_pct=self._settings.default_max_symbol_exposure_pct,
                max_open_positions=self._settings.default_max_open_positions,
                max_allowed_leverage=self._settings.default_max_allowed_leverage,
                min_liquidation_buffer_pct=self._settings.default_min_liquidation_buffer_pct,
                min_stop_distance_pct=self._settings.default_min_stop_distance_pct,
                buyer_absence_block_score=self._settings.default_buyer_absence_block_score,
                dead_market_block_score=self._settings.default_dead_market_block_score,
                require_stop_loss=self._settings.default_require_stop_loss,
                block_new_trades_in_dead_market=self._settings.default_block_new_trades_in_dead_market,
                block_longs_when_buyers_left=self._settings.default_block_longs_when_buyers_left,
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
        return policy

    def get_policy(self) -> models.RiskPolicy:
        with SessionLocal() as db:
            return self.ensure_policy(db)

    def update_policy(self, payload: RiskPolicyUpdate) -> models.RiskPolicy:
        with SessionLocal() as db:
            policy = self.ensure_policy(db)
            for field, value in payload.model_dump().items():
                setattr(policy, field, value)
            db.commit()
            db.refresh(policy)
            return policy
