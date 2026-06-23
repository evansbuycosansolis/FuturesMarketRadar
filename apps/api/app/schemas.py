from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SymbolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    base_asset: str
    quote_asset: str
    market_type: str
    status: str
    created_at: datetime


class ScoreEntry(BaseModel):
    symbol: str
    price: float
    price_change_24h: float
    volume_24h: float
    quote_volume_24h: float
    high_24h: float
    low_24h: float
    open_interest: float
    open_interest_change_pct: float
    activity_score: float
    bullish_score: float
    bearish_score: float
    buyer_absence_score: float = 0.0
    dead_market_score: float = 0.0
    quiet_rally_score: float = 0.0
    volume_spike_ratio: float
    price_change_5m: float
    price_change_15m: float
    atr_percent: float
    buyer_volume_share: float = 0.0
    green_candle_ratio: float = 0.0
    trend_label: str
    breakdown: dict[str, dict[str, float]] = Field(default_factory=dict)


class ReportRead(BaseModel):
    id: int
    title: str
    summary: str
    top_active: list[ScoreEntry]
    top_bullish: list[ScoreEntry]
    top_bearish: list[ScoreEntry]
    top_buyers_left: list[ScoreEntry]
    top_dead_markets: list[ScoreEntry]
    top_quiet_rallies: list[ScoreEntry]
    watchlist: list[ScoreEntry]
    ai_commentary: str
    scan_reason: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    scheduler_running: bool
    scanner_running: bool
    last_run_started_at: datetime | None
    last_run_completed_at: datetime | None
    last_error: str | None
    latest_report_at: datetime | None
    tracked_symbol_count: int
    automation_mode: str | None = None
    kill_switch_enabled: bool = False
    watchdog_last_run_at: datetime | None = None
    last_private_stream_event_at: datetime | None = None
    last_public_stream_event_at: datetime | None = None


class ExchangeStatusRead(BaseModel):
    exchange: Literal["pionex", "binance"]
    label: str
    enabled: bool
    configured: bool
    private_sync_enabled: bool
    trading_enabled: bool
    execution_available: bool
    base_url: str
    mode: Literal["disabled", "needs_keys", "read_only", "guardrail", "live_enabled"]
    message: str


class ExchangeStatusResponse(BaseModel):
    global_trading_enabled: bool
    exchanges: list[ExchangeStatusRead]


class RunScanResponse(BaseModel):
    ok: bool
    report: ReportRead | None = None
    message: str = ""


class SymbolListResponse(BaseModel):
    total: int
    items: list[SymbolRead]


class MarketOverviewResponse(BaseModel):
    latest_report_at: datetime | None
    latest_age_minutes: float | None = None
    is_stale: bool = False
    data_source: str = "pionex-public-api"
    data_warning: str | None = None
    coin_cap: list[ScoreEntry]
    gainers: list[ScoreEntry]
    losers: list[ScoreEntry]
    futures: list[ScoreEntry]


class MarketChangeMomentumRead(BaseModel):
    symbol: str
    price: float
    anchor_price: float | None = None
    latest_change_24h: float
    previous_change_24h: float | None
    delta_5m: float | None
    delta_window: float | None
    price_delta_5m_pct: float | None = None
    price_delta_window_pct: float | None = None
    samples: int
    expected_samples: int | None = None
    sample_coverage_pct: float | None = None
    max_gap_minutes: float | None = None
    data_quality: Literal["strong", "partial", "thin"] = "thin"
    direction: Literal["increasing", "decreasing", "flat", "new"]
    strength: Literal["strong", "moderate", "weak", "none"]
    sparkline: list[float] = Field(default_factory=list)
    latest_timestamp: datetime | None
    previous_timestamp: datetime | None
    dominant_session: str = "Waiting"
    session_summary: str = ""
    sessions: list["MarketSessionMomentumCellRead"] = Field(default_factory=list)


class MarketChangeMomentumResponse(BaseModel):
    latest_report_at: datetime | None
    interval_minutes: int
    lookback_samples: int
    items: list[MarketChangeMomentumRead]


class MarketChangeTrajectoryResponse(BaseModel):
    latest_report_at: datetime | None
    lookback_hours: int
    interval_minutes: int
    improving: list[MarketChangeMomentumRead]
    fading: list[MarketChangeMomentumRead]
    note: str


class MarketSessionMomentumCellRead(BaseModel):
    session: Literal["Asian", "London", "New York"]
    start_hour_utc: int
    end_hour_utc: int
    samples: int
    net_delta: float
    average_5m_delta: float
    direction: Literal["up", "down", "flat", "insufficient"]


class MarketSessionMomentumRead(BaseModel):
    symbol: str
    price: float
    latest_change_24h: float
    dominant_session: str
    summary: str
    sessions: list[MarketSessionMomentumCellRead]


class MarketSessionMomentumResponse(BaseModel):
    latest_report_at: datetime | None
    lookback_hours: int
    interval_minutes: int
    note: str
    items: list[MarketSessionMomentumRead]


class SleepingGiantSetupRead(BaseModel):
    symbol: str
    direction: Literal["bullish", "bearish"]
    awakening_phase: Literal["watch", "pressure_building", "giant_awakening", "liquidity_spike"]
    average_candle_size: float
    latest_candle_size: float
    median_candle_height_pct: float
    latest_candle_height_pct: float
    height_ratio: float
    volume_ratio: float
    body_strength: float
    two_candle_pressure: float
    range_burst_score: float
    volume_burst_score: float
    compression_score: float
    breakout_score: float
    volume_expansion_ratio: float
    range_expansion_ratio: float
    distance_from_box_breakout: float
    current_price: float
    timestamp: datetime | None
    score: float
    compression_candles: int
    box_high: float
    box_low: float
    notes: list[str] = Field(default_factory=list)


class SleepingGiantResponse(BaseModel):
    latest_report_at: datetime | None
    timeframe: str
    lookback_days: int
    baseline_candles: int
    scanned_symbols: int
    candidates: list[SleepingGiantSetupRead]
    note: str


class FuturesAnomalyRead(BaseModel):
    symbol: str
    direction: Literal["breakout", "breakdown"]
    score: float
    current_price: float
    ret_1m: float
    ret_5m: float
    ret_15m: float
    z_move_5m: float
    volume_ratio_1m: float
    accel_score: float
    range_position_24h: float
    wick_signal: float
    order_imbalance: float
    isolation_bonus: float
    funding_extreme: float
    open_interest_change_pct: float
    liquidity_score: float
    timestamp: datetime | None
    reason_tags: list[str] = Field(default_factory=list)


class FuturesAnomalyResponse(BaseModel):
    latest_report_at: datetime | None
    interval_seconds: int
    lookback_hours: int
    source: str
    top_breakouts: list[FuturesAnomalyRead]
    top_breakdowns: list[FuturesAnomalyRead]
    note: str


class MarketQualityCheckRead(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str
    metric: float | None = None
    threshold: float | None = None


class MarketQualityResponse(BaseModel):
    status: Literal["healthy", "degraded", "unavailable"]
    score: float
    latest_report_at: datetime | None
    source: str
    checks: list[MarketQualityCheckRead]
    caveats: list[str] = Field(default_factory=list)


class AssetResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=120)


class AssetResearchSourceRead(BaseModel):
    title: str
    source: str
    url: str


class AssetResearchSessionRead(BaseModel):
    matched_symbol: str | None
    dominant_session: str
    summary: str
    latest_change_24h: float | None = None
    sessions: list[MarketSessionMomentumCellRead] = Field(default_factory=list)


class AssetResearchResponse(BaseModel):
    query: str
    normalized_query: str
    asset_type: str
    name: str
    symbol: str | None
    what: str
    who: str
    where: str
    when: str
    session_support: AssetResearchSessionRead
    recent_themes: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    what_to_watch_next: list[str] = Field(default_factory=list)
    confidence: float
    summary_text: str
    sources: list[AssetResearchSourceRead] = Field(default_factory=list)


class ReportHistoryResponse(BaseModel):
    items: list[ReportRead]


class RiskPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    max_weekly_loss_pct: float
    max_portfolio_heat_pct: float
    max_symbol_exposure_pct: float
    max_open_positions: int
    max_allowed_leverage: float
    min_liquidation_buffer_pct: float
    min_stop_distance_pct: float
    buyer_absence_block_score: float
    dead_market_block_score: float
    require_stop_loss: bool
    block_new_trades_in_dead_market: bool
    block_longs_when_buyers_left: bool
    created_at: datetime
    updated_at: datetime


class RiskPolicyUpdate(BaseModel):
    max_risk_per_trade_pct: float = Field(ge=0.1, le=100.0)
    max_daily_loss_pct: float = Field(ge=0.1, le=100.0)
    max_weekly_loss_pct: float = Field(ge=0.1, le=100.0)
    max_portfolio_heat_pct: float = Field(ge=0.1, le=1000.0)
    max_symbol_exposure_pct: float = Field(ge=0.1, le=1000.0)
    max_open_positions: int = Field(ge=1, le=100)
    max_allowed_leverage: float = Field(ge=1.0, le=500.0)
    min_liquidation_buffer_pct: float = Field(ge=0.0, le=1000.0)
    min_stop_distance_pct: float = Field(ge=0.0, le=1000.0)
    buyer_absence_block_score: float = Field(ge=0.0, le=100.0)
    dead_market_block_score: float = Field(ge=0.0, le=100.0)
    require_stop_loss: bool
    block_new_trades_in_dead_market: bool
    block_longs_when_buyers_left: bool


class RiskQuoteStateRead(BaseModel):
    quote: str
    risk_state: str


class AccountBalanceRead(BaseModel):
    coin: str
    assets: float
    free: float
    frozen: float
    transferable: float = 0.0
    available: float = 0.0
    unrealized_pnl: float = 0.0
    total_initial_margin: float = 0.0
    debts: float = 0.0


class PositionSnapshotRead(BaseModel):
    symbol: str
    position_id: str
    isolated_mode: str
    risk_state: str
    position_side: str
    net_size: float
    avg_price: float
    mark_price: float
    notional_value: float
    initial_margin: float
    maint_margin: float
    liquidation_price: float
    liquidation_buffer_pct: float
    leverage: float
    unrealized_pnl: float
    snapshot_time: datetime


class OrderSnapshotRead(BaseModel):
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
    snapshot_time: datetime
    created_time: datetime | None
    updated_time: datetime | None


class RiskBreachRead(BaseModel):
    code: str
    severity: Literal["info", "warning", "high", "critical"]
    message: str


class RiskSummaryResponse(BaseModel):
    private_api_enabled: bool
    private_api_configured: bool
    trading_enabled: bool
    exit_automation_enabled: bool
    sync_running: bool
    exit_engine_running: bool
    last_synced_at: datetime | None
    last_exit_engine_at: datetime | None
    last_sync_error: str | None
    last_exit_engine_error: str | None
    message: str | None = None
    account_currency: str
    total_assets: float
    account_equity: float
    free_balance: float
    available_margin: float
    unrealized_pnl: float
    total_initial_margin: float
    debts: float
    daily_pnl: float
    weekly_pnl: float
    daily_loss_used_pct: float
    weekly_loss_used_pct: float
    daily_loss_remaining_pct: float
    weekly_loss_remaining_pct: float
    portfolio_heat_pct: float
    open_position_count: int
    open_order_count: int
    balances: list[AccountBalanceRead]
    risk_states: list[RiskQuoteStateRead]
    positions: list[PositionSnapshotRead]
    orders: list[OrderSnapshotRead]
    breaches: list[RiskBreachRead]
    managed_exits: list["ManagedExitPlanRead"]
    exit_events: list["ManagedExitEventRead"]
    policy: RiskPolicyRead


class RiskSyncResponse(BaseModel):
    ok: bool
    summary: RiskSummaryResponse


class MarketRiskContextRead(BaseModel):
    symbol: str
    trend_label: str
    activity_score: float
    bullish_score: float
    bearish_score: float
    buyer_absence_score: float
    dead_market_score: float
    quiet_rally_score: float
    price_change_5m: float
    price_change_15m: float


class TradeCheckLineRead(BaseModel):
    name: str
    passed: bool
    detail: str
    metric: float | None = None
    threshold: float | None = None


class TradeCheckRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    size: float = Field(gt=0.0)
    entry_price: float = Field(gt=0.0)
    stop_price: float | None = Field(default=None, gt=0.0)
    order_type: Literal["LIMIT", "MARKET_QTY", "IOC", "FOK", "POSTONLY"] = "LIMIT"
    position_side: Literal["BOTH", "LONG", "SHORT"] = "BOTH"
    planned_leverage: float | None = Field(default=None, gt=0.0)
    reduce_only: bool = False


class TradeCheckResponse(BaseModel):
    allowed: bool
    trading_enabled: bool
    execution_available: bool
    blocked_reasons: list[str]
    warnings: list[str]
    estimated_risk_amount: float
    estimated_risk_pct: float
    estimated_position_notional: float
    estimated_margin_required: float
    estimated_portfolio_heat_pct: float
    estimated_symbol_exposure_pct: float
    stop_distance_pct: float
    market_context: MarketRiskContextRead | None
    checks: list[TradeCheckLineRead]


class TradePlanRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    entry_price: float | None = Field(default=None, gt=0.0)
    size: float | None = Field(default=None, gt=0.0)
    planned_leverage: float | None = Field(default=None, gt=0.0)


class TradePlanResponse(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    entry_price: float
    stop_price: float
    take_profit_price: float
    stop_distance_pct: float
    take_profit_distance_pct: float
    risk_reward_ratio: float
    atr_percent: float
    max_risk_amount: float | None
    suggested_size: float | None
    market_context: MarketRiskContextRead | None
    notes: list[str]


class ExecutionOrderRequest(TradeCheckRequest):
    client_order_id: str | None = Field(default=None, max_length=64)
    take_profit_price: float | None = Field(default=None, gt=0.0)
    arm_exit_automation: bool = False


class ManagedExitPlanRead(BaseModel):
    id: int
    symbol: str
    entry_side: str
    position_side: str
    stop_price: float
    take_profit_price: float
    expected_entry_price: float
    expected_size: float
    active_size: float
    status: str
    trigger_reason: str
    entry_order_id: str
    exit_order_id: str
    retries_used: int
    reduce_only_required: bool
    last_mark_price: float
    last_trigger_price: float
    last_error: str
    created_at: datetime
    activated_at: datetime | None
    last_checked_at: datetime | None
    last_exit_attempt_at: datetime | None
    closed_at: datetime | None
    updated_at: datetime


class ManagedExitEventRead(BaseModel):
    id: int
    plan_id: int
    event_type: str
    severity: Literal["info", "warning", "error", "critical"]
    message: str
    payload_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class ArmManagedExitRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    stop_price: float = Field(gt=0.0)
    take_profit_price: float = Field(gt=0.0)
    position_side: Literal["BOTH"] = "BOTH"
    entry_price: float | None = Field(default=None, gt=0.0)
    expected_size: float | None = Field(default=None, gt=0.0)


class ArmManagedExitResponse(BaseModel):
    ok: bool
    plan: ManagedExitPlanRead
    message: str


class DisarmManagedExitResponse(BaseModel):
    ok: bool
    plan: ManagedExitPlanRead
    message: str


class RunExitAutomationResponse(BaseModel):
    ok: bool
    plans_checked: int
    triggered: int
    message: str


class OrderExecutionResponse(BaseModel):
    ok: bool
    order_id: str
    message: str
    check: TradeCheckResponse
    managed_exit_plan: ManagedExitPlanRead | None = None


class CancelAllOrdersRequest(BaseModel):
    symbol: str


class CancelAllOrdersResponse(BaseModel):
    ok: bool
    symbol: str
    message: str


class AutomationControlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: Literal["paper", "supervised_live", "unattended_live"]
    kill_switch_enabled: bool
    kill_switch_reason: str
    consecutive_failures: int
    last_automation_error: str
    last_webhook_at: datetime | None
    last_reconciliation_at: datetime | None
    last_watchdog_at: datetime | None
    last_private_stream_event_at: datetime | None
    last_public_stream_event_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AutomationControlUpdate(BaseModel):
    mode: Literal["paper", "supervised_live", "unattended_live"]


class AutomationAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    severity: Literal["info", "warning", "high", "critical"]
    message: str
    active: bool
    payload_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class AutomationSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_signal_id: str
    strategy_name: str
    symbol: str
    side: str
    mode_at_receipt: str
    status: str
    status_reason: str
    requested_order_type: str
    requested_size: float
    requested_entry_price: float
    requested_stop_price: float
    requested_take_profit_price: float
    planned_order_json: dict[str, object] = Field(default_factory=dict)
    risk_check_json: dict[str, object] = Field(default_factory=dict)
    execution_result_json: dict[str, object] = Field(default_factory=dict)
    order_id: str
    client_order_id: str
    created_at: datetime
    updated_at: datetime
    acted_at: datetime | None


class AutomationSummaryResponse(BaseModel):
    control: AutomationControlRead
    webhook_secret_configured: bool
    websocket_monitoring_enabled: bool
    private_stream_connected: bool
    public_stream_connected: bool
    private_stream_last_error: str | None
    public_stream_last_error: str | None
    pending_approval_count: int
    recent_signals: list[AutomationSignalRead]
    alerts: list[AutomationAlertRead]


class AutomationToggleResponse(BaseModel):
    ok: bool
    control: AutomationControlRead
    message: str


class AutomationActionResponse(BaseModel):
    ok: bool
    message: str
    summary: AutomationSummaryResponse


class SignalActionResponse(BaseModel):
    ok: bool
    signal: AutomationSignalRead
    message: str


class KillSwitchRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


class RejectSignalRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


class TradingViewWebhookResponse(BaseModel):
    ok: bool
    signal: AutomationSignalRead
    message: str


class ManualSignalRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET_QTY", "IOC", "FOK", "POSTONLY"] = "MARKET_QTY"
    size: float = Field(gt=0.0)
    entry_price: float = Field(gt=0.0)
    stop_price: float | None = Field(default=None, gt=0.0)
    take_profit_price: float | None = Field(default=None, gt=0.0)
    planned_leverage: float | None = Field(default=None, gt=0.0)
    position_side: Literal["BOTH", "LONG", "SHORT"] = "BOTH"
    reduce_only: bool = False
    strategy: str = Field(default="manual-copilot-ticket", max_length=128)


class SignalIndicatorRead(BaseModel):
    name: str
    value: float | str
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    reason: str


class CopilotSignalRead(BaseModel):
    symbol: str
    timeframe: str
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    confidence: float
    reasons: list[str]
    invalidation_level: float | None
    suggested_stop_loss: float | None
    suggested_take_profit: float | None
    risk_reward_ratio: float | None
    indicators: list[SignalIndicatorRead]


class SignalHeatmapRowRead(BaseModel):
    symbol: str
    cells: list[CopilotSignalRead]
    summary: str
    confidence: float


class SignalHeatmapResponse(BaseModel):
    symbols: list[str]
    timeframes: list[str]
    rows: list[SignalHeatmapRowRead]


class PaperAccountRead(BaseModel):
    starting_balance: float
    cash_balance: float
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    commission_paid: float
    default_trade_size: float
    default_leverage: float
    commission_rate: float
    default_stop_loss_pct: float
    default_take_profit_pct: float
    default_trailing_stop_pct: float


class PaperPositionRead(BaseModel):
    id: int
    symbol: str
    side: Literal["LONG", "SHORT"]
    status: str
    entry_price: float
    current_price: float
    size: float
    leverage: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: float
    take_profit: float
    trailing_stop_pct: float
    liquidation_warning: str | None
    opened_at: datetime
    closed_at: datetime | None


class PaperOrderRequest(BaseModel):
    symbol: str
    side: Literal["LONG", "SHORT"]
    entry_price: float = Field(gt=0.0)
    size: float | None = Field(default=None, gt=0.0)
    leverage: float | None = Field(default=None, gt=0.0)
    stop_loss: float | None = Field(default=None, gt=0.0)
    take_profit: float | None = Field(default=None, gt=0.0)
    trailing_stop_pct: float | None = Field(default=None, ge=0.0)


class PaperCloseRequest(BaseModel):
    close_price: float = Field(gt=0.0)
    reason: str = Field(default="manual", max_length=64)


class PaperTradeResponse(BaseModel):
    ok: bool
    position: PaperPositionRead
    message: str


class PaperSummaryResponse(BaseModel):
    account: PaperAccountRead
    open_positions: list[PaperPositionRead]
    closed_positions: list[PaperPositionRead]
    win_rate: float
    trade_count: int
    average_hold_minutes: float | None


class CopilotLogRead(BaseModel):
    id: int
    category: str
    severity: str
    message: str
    payload_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class CopilotOverviewResponse(BaseModel):
    app_name: str
    mode: str
    live_mode_locked: bool
    ai_signals_running: bool
    trader_engine_running: bool
    circuit_breaker_ok: bool
    total_account_value: float
    buying_power: float
    holdings_margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    today_pnl: float
    win_rate: float
    number_of_trades: int
    best_coin: str | None
    worst_coin: str | None
    average_hold_minutes: float | None
    open_positions: int
    warnings: list[str]


class AssetSentimentRead(BaseModel):
    asset: str
    symbol: str
    sentiment_score: float
    confidence: float
    article_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    ma_3_score: float
    ma_8_score: float
    ma_56_score: float
    label: str
    themes: list[str] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    example_links: list[dict[str, str]] = Field(default_factory=list)
    created_at: datetime | None


class MarketIntelligenceRunRead(BaseModel):
    id: int
    status: str
    reason: str
    sources_checked: int
    articles_scanned: int
    matched_articles: int
    error: str
    created_at: datetime
    completed_at: datetime | None


class MarketIntelligenceSummaryResponse(BaseModel):
    enabled: bool
    interval_minutes: int
    latest_run: MarketIntelligenceRunRead | None
    assets: list[AssetSentimentRead]
    note: str


class MarketIntelligenceRunResponse(BaseModel):
    ok: bool
    run: MarketIntelligenceRunRead
    assets: list[AssetSentimentRead]
    message: str
