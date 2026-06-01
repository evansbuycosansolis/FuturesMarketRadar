from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    base_asset: Mapped[str] = mapped_column(String(64), index=True)
    quote_asset: Mapped[str] = mapped_column(String(64), index=True)
    market_type: Mapped[str] = mapped_column(String(16), default="PERP")
    status: Mapped[str] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", "timestamp", name="uq_market_snapshot_symbol_timestamp"),
        Index("ix_market_snapshots_timestamp_symbol", "timestamp", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    price: Mapped[float] = mapped_column(Float)
    price_change_24h: Mapped[float] = mapped_column(Float)
    volume_24h: Mapped[float] = mapped_column(Float)
    quote_volume_24h: Mapped[float] = mapped_column(Float)
    high_24h: Mapped[float] = mapped_column(Float)
    low_24h: Mapped[float] = mapped_column(Float)
    open_interest: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class CoinScore(Base):
    __tablename__ = "coin_scores"
    __table_args__ = (
        UniqueConstraint("symbol", "report_time", name="uq_coin_scores_symbol_report_time"),
        Index("ix_coin_scores_report_time_symbol", "report_time", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    activity_score: Mapped[float] = mapped_column(Float)
    bullish_score: Mapped[float] = mapped_column(Float)
    bearish_score: Mapped[float] = mapped_column(Float)
    buyer_absence_score: Mapped[float] = mapped_column(Float, default=0.0)
    dead_market_score: Mapped[float] = mapped_column(Float, default=0.0)
    quiet_rally_score: Mapped[float] = mapped_column(Float, default=0.0)
    volume_spike_ratio: Mapped[float] = mapped_column(Float)
    price_change_5m: Mapped[float] = mapped_column(Float)
    price_change_15m: Mapped[float] = mapped_column(Float)
    atr_percent: Mapped[float] = mapped_column(Float)
    open_interest_change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    buyer_volume_share: Mapped[float] = mapped_column(Float, default=0.0)
    green_candle_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    trend_label: Mapped[str] = mapped_column(String(48), index=True)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
    report_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    top_active_json: Mapped[list] = mapped_column(JSON, default=list)
    top_bullish_json: Mapped[list] = mapped_column(JSON, default=list)
    top_bearish_json: Mapped[list] = mapped_column(JSON, default=list)
    top_buyers_left_json: Mapped[list] = mapped_column(JSON, default=list)
    top_dead_markets_json: Mapped[list] = mapped_column(JSON, default=list)
    top_quiet_rallies_json: Mapped[list] = mapped_column(JSON, default=list)
    watchlist_json: Mapped[list] = mapped_column(JSON, default=list)
    ai_commentary: Mapped[str] = mapped_column(Text, default="")
    scan_reason: Mapped[str] = mapped_column(String(24), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class RiskPolicy(Base):
    __tablename__ = "risk_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(64), unique=True, default="default")
    max_risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=1.0)
    max_daily_loss_pct: Mapped[float] = mapped_column(Float, default=3.0)
    max_weekly_loss_pct: Mapped[float] = mapped_column(Float, default=6.0)
    max_portfolio_heat_pct: Mapped[float] = mapped_column(Float, default=25.0)
    max_symbol_exposure_pct: Mapped[float] = mapped_column(Float, default=20.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=5)
    max_allowed_leverage: Mapped[float] = mapped_column(Float, default=5.0)
    min_liquidation_buffer_pct: Mapped[float] = mapped_column(Float, default=12.0)
    min_stop_distance_pct: Mapped[float] = mapped_column(Float, default=0.35)
    buyer_absence_block_score: Mapped[float] = mapped_column(Float, default=70.0)
    dead_market_block_score: Mapped[float] = mapped_column(Float, default=75.0)
    require_stop_loss: Mapped[bool] = mapped_column(default=True)
    block_new_trades_in_dead_market: Mapped[bool] = mapped_column(default=True)
    block_longs_when_buyers_left: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"
    __table_args__ = (
        Index("ix_account_snapshots_snapshot_time", "snapshot_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_currency: Mapped[str] = mapped_column(String(16), default="USDT")
    total_assets: Mapped[float] = mapped_column(Float, default=0.0)
    account_equity: Mapped[float] = mapped_column(Float, default=0.0)
    free_balance: Mapped[float] = mapped_column(Float, default=0.0)
    available_margin: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_initial_margin: Mapped[float] = mapped_column(Float, default=0.0)
    debts: Mapped[float] = mapped_column(Float, default=0.0)
    balances_json: Mapped[list] = mapped_column(JSON, default=list)
    quote_risks_json: Mapped[list] = mapped_column(JSON, default=list)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"
    __table_args__ = (
        Index("ix_position_snapshots_snapshot_time_symbol", "snapshot_time", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    position_id: Mapped[str] = mapped_column(String(96), default="")
    isolated_mode: Mapped[str] = mapped_column(String(32), default="")
    risk_state: Mapped[str] = mapped_column(String(32), default="")
    position_side: Mapped[str] = mapped_column(String(16), default="")
    net_size: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    mark_price: Mapped[float] = mapped_column(Float, default=0.0)
    notional_value: Mapped[float] = mapped_column(Float, default=0.0)
    initial_margin: Mapped[float] = mapped_column(Float, default=0.0)
    maint_margin: Mapped[float] = mapped_column(Float, default=0.0)
    liquidation_price: Mapped[float] = mapped_column(Float, default=0.0)
    leverage: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    created_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrderSnapshot(Base):
    __tablename__ = "order_snapshots"
    __table_args__ = (
        Index("ix_order_snapshots_snapshot_time_symbol", "snapshot_time", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(String(96), index=True, default="")
    client_order_id: Mapped[str] = mapped_column(String(96), default="")
    side: Mapped[str] = mapped_column(String(16), default="")
    position_side: Mapped[str] = mapped_column(String(16), default="")
    order_type: Mapped[str] = mapped_column(String(24), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    size: Mapped[float] = mapped_column(Float, default=0.0)
    filled_size: Mapped[float] = mapped_column(Float, default=0.0)
    reduce_only: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(24), default="")
    created_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ManagedExitPlan(Base):
    __tablename__ = "managed_exit_plans"
    __table_args__ = (
        Index("ix_managed_exit_plans_status_symbol", "status", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    entry_side: Mapped[str] = mapped_column(String(16))
    position_side: Mapped[str] = mapped_column(String(16), default="BOTH")
    stop_price: Mapped[float] = mapped_column(Float)
    take_profit_price: Mapped[float] = mapped_column(Float)
    expected_entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    expected_size: Mapped[float] = mapped_column(Float, default=0.0)
    active_size: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="pending_fill", index=True)
    trigger_reason: Mapped[str] = mapped_column(String(32), default="")
    entry_order_id: Mapped[str] = mapped_column(String(96), default="")
    exit_order_id: Mapped[str] = mapped_column(String(96), default="")
    retries_used: Mapped[int] = mapped_column(Integer, default=0)
    reduce_only_required: Mapped[bool] = mapped_column(default=True)
    last_mark_price: Mapped[float] = mapped_column(Float, default=0.0)
    last_trigger_price: Mapped[float] = mapped_column(Float, default=0.0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_exit_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ManagedExitEvent(Base):
    __tablename__ = "managed_exit_events"
    __table_args__ = (
        Index("ix_managed_exit_events_plan_created", "plan_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(32), default="info")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class AutomationControl(Base):
    __tablename__ = "automation_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    mode: Mapped[str] = mapped_column(String(24), default="paper")
    kill_switch_enabled: Mapped[bool] = mapped_column(default=False)
    kill_switch_reason: Mapped[str] = mapped_column(Text, default="")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_automation_error: Mapped[str] = mapped_column(Text, default="")
    last_webhook_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconciliation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_watchdog_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_private_stream_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_public_stream_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class WebhookReceipt(Base):
    __tablename__ = "webhook_receipts"
    __table_args__ = (
        UniqueConstraint("source", "delivery_key", name="uq_webhook_receipts_source_delivery"),
        Index("ix_webhook_receipts_created_source", "created_at", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    delivery_key: Mapped[str] = mapped_column(String(128), index=True)
    payload_hash: Mapped[str] = mapped_column(String(128), default="")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class AutomationSignal(Base):
    __tablename__ = "automation_signals"
    __table_args__ = (
        UniqueConstraint("source", "source_signal_id", name="uq_automation_signals_source_signal"),
        Index("ix_automation_signals_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True, default="tradingview")
    source_signal_id: Mapped[str] = mapped_column(String(128), index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), default="")
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    side: Mapped[str] = mapped_column(String(16), default="")
    mode_at_receipt: Mapped[str] = mapped_column(String(24), default="paper")
    status: Mapped[str] = mapped_column(String(32), default="received", index=True)
    status_reason: Mapped[str] = mapped_column(Text, default="")
    requested_order_type: Mapped[str] = mapped_column(String(24), default="")
    requested_size: Mapped[float] = mapped_column(Float, default=0.0)
    requested_entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    requested_stop_price: Mapped[float] = mapped_column(Float, default=0.0)
    requested_take_profit_price: Mapped[float] = mapped_column(Float, default=0.0)
    planned_order_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_check_json: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    order_id: Mapped[str] = mapped_column(String(96), default="")
    client_order_id: Mapped[str] = mapped_column(String(96), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AutomationAlert(Base):
    __tablename__ = "automation_alerts"
    __table_args__ = (
        UniqueConstraint("code", name="uq_automation_alerts_code"),
        Index("ix_automation_alerts_active_created", "active", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    starting_balance: Mapped[float] = mapped_column(Float, default=800.0)
    cash_balance: Mapped[float] = mapped_column(Float, default=800.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    commission_paid: Mapped[float] = mapped_column(Float, default=0.0)
    default_trade_size: Mapped[float] = mapped_column(Float, default=25.0)
    default_leverage: Mapped[float] = mapped_column(Float, default=3.0)
    commission_rate: Mapped[float] = mapped_column(Float, default=0.0005)
    default_stop_loss_pct: Mapped[float] = mapped_column(Float, default=1.0)
    default_take_profit_pct: Mapped[float] = mapped_column(Float, default=2.0)
    default_trailing_stop_pct: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        Index("ix_paper_positions_status_symbol", "status", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    side: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    leverage: Mapped[float] = mapped_column(Float, default=1.0)
    margin_used: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0)
    take_profit: Mapped[float] = mapped_column(Float, default=0.0)
    trailing_stop_pct: Mapped[float] = mapped_column(Float, default=0.0)
    highest_price: Mapped[float] = mapped_column(Float, default=0.0)
    lowest_price: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    fees_paid: Mapped[float] = mapped_column(Float, default=0.0)
    close_price: Mapped[float] = mapped_column(Float, default=0.0)
    close_reason: Mapped[str] = mapped_column(String(64), default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class CopilotLog(Base):
    __tablename__ = "copilot_logs"
    __table_args__ = (
        Index("ix_copilot_logs_created_category", "created_at", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class MarketIntelligenceRun(Base):
    __tablename__ = "market_intelligence_runs"
    __table_args__ = (
        Index("ix_market_intelligence_runs_created_status", "created_at", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    reason: Mapped[str] = mapped_column(String(32), default="scheduled")
    sources_checked: Mapped[int] = mapped_column(Integer, default=0)
    articles_scanned: Mapped[int] = mapped_column(Integer, default=0)
    matched_articles: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssetSentimentSnapshot(Base):
    __tablename__ = "asset_sentiment_snapshots"
    __table_args__ = (
        UniqueConstraint("asset", "run_id", name="uq_asset_sentiment_snapshot_asset_run"),
        Index("ix_asset_sentiment_snapshots_asset_created", "asset", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    asset: Mapped[str] = mapped_column(String(16), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    ma_3_score: Mapped[float] = mapped_column(Float, default=0.0)
    ma_8_score: Mapped[float] = mapped_column(Float, default=0.0)
    ma_56_score: Mapped[float] = mapped_column(Float, default=0.0)
    themes_json: Mapped[list] = mapped_column(JSON, default=list)
    source_counts_json: Mapped[dict] = mapped_column(JSON, default=dict)
    example_links_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
