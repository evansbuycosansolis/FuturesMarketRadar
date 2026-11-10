export type ScoreBreakdown = Record<string, Record<string, number>>;

export type ScoreEntry = {
  symbol: string;
  price: number;
  price_change_24h: number;
  volume_24h: number;
  quote_volume_24h: number;
  high_24h: number;
  low_24h: number;
  open_interest: number;
  open_interest_change_pct: number;
  activity_score: number;
  bullish_score: number;
  bearish_score: number;
  buyer_absence_score: number;
  dead_market_score: number;
  quiet_rally_score: number;
  volume_spike_ratio: number;
  price_change_5m: number;
  price_change_15m: number;
  atr_percent: number;
  buyer_volume_share: number;
  green_candle_ratio: number;
  trend_label: string;
  breakdown: ScoreBreakdown;
};

export type Report = {
  id: number;
  title: string;
  summary: string;
  top_active: ScoreEntry[];
  top_bullish: ScoreEntry[];
  top_bearish: ScoreEntry[];
  top_buyers_left: ScoreEntry[];
  top_dead_markets: ScoreEntry[];
  top_quiet_rallies: ScoreEntry[];
  watchlist: ScoreEntry[];
  ai_commentary: string;
  scan_reason: string;
  created_at: string;
};

export type HealthStatus = {
  status: string;
  scheduler_running: boolean;
  scanner_running: boolean;
  last_run_started_at: string | null;
  last_run_completed_at: string | null;
  last_error: string | null;
  latest_report_at: string | null;
  tracked_symbol_count: number;
  automation_mode: string | null;
  kill_switch_enabled: boolean;
  watchdog_last_run_at: string | null;
  last_private_stream_event_at: string | null;
  last_public_stream_event_at: string | null;
};

export type ExchangeStatus = {
  exchange: "pionex" | "binance";
  label: string;
  enabled: boolean;
  configured: boolean;
  private_sync_enabled: boolean;
  trading_enabled: boolean;
  execution_available: boolean;
  base_url: string;
  mode: "disabled" | "needs_keys" | "read_only" | "guardrail" | "live_enabled";
  message: string;
};

export type ExchangeStatusResponse = {
  global_trading_enabled: boolean;
  exchanges: ExchangeStatus[];
};

export type ReportHistoryResponse = {
  items: Report[];
};

export type MarketOverviewResponse = {
  latest_report_at: string | null;
  latest_age_minutes: number | null;
  is_stale: boolean;
  data_source: string;
  data_warning: string | null;
  coin_cap: ScoreEntry[];
  gainers: ScoreEntry[];
  losers: ScoreEntry[];
  futures: ScoreEntry[];
};

export type MarketSessionMomentumCell = {
  session: "Asian" | "London" | "New York";
  start_hour_utc: number;
  end_hour_utc: number;
  samples: number;
  net_delta: number;
  average_5m_delta: number;
  direction: "up" | "down" | "flat" | "insufficient";
};

export type MarketSessionMomentumItem = {
  symbol: string;
  price: number;
  latest_change_24h: number;
  dominant_session: string;
  summary: string;
  sessions: MarketSessionMomentumCell[];
};

export type MarketSessionMomentumResponse = {
  latest_report_at: string | null;
  lookback_hours: number;
  interval_minutes: number;
  note: string;
  items: MarketSessionMomentumItem[];
};

export type MarketChangeMomentumItem = {
  symbol: string;
  price: number;
  anchor_price: number | null;
  latest_change_24h: number;
  previous_change_24h: number | null;
  delta_5m: number | null;
  delta_window: number | null;
  price_delta_5m_pct: number | null;
  price_delta_window_pct: number | null;
  samples: number;
  expected_samples: number | null;
  sample_coverage_pct: number | null;
  max_gap_minutes: number | null;
  data_quality: "strong" | "partial" | "thin";
  direction: "increasing" | "decreasing" | "flat" | "new";
  strength: "strong" | "moderate" | "weak" | "none";
  sparkline: number[];
  latest_timestamp: string | null;
  previous_timestamp: string | null;
  dominant_session: string;
  session_summary: string;
  sessions: MarketSessionMomentumCell[];
};

export type MarketChangeTrajectoryResponse = {
  latest_report_at: string | null;
  lookback_hours: number;
  interval_minutes: number;
  improving: MarketChangeMomentumItem[];
  fading: MarketChangeMomentumItem[];
  note: string;
};

export type SleepingGiantSetup = {
  symbol: string;
  direction: "bullish" | "bearish";
  awakening_phase: "watch" | "pressure_building" | "giant_awakening" | "liquidity_spike";
  average_candle_size: number;
  latest_candle_size: number;
  median_candle_height_pct: number;
  latest_candle_height_pct: number;
  height_ratio: number;
  volume_ratio: number;
  body_strength: number;
  two_candle_pressure: number;
  range_burst_score: number;
  volume_burst_score: number;
  compression_score: number;
  breakout_score: number;
  volume_expansion_ratio: number;
  range_expansion_ratio: number;
  distance_from_box_breakout: number;
  current_price: number;
  timestamp: string | null;
  score: number;
  compression_candles: number;
  box_high: number;
  box_low: number;
  notes: string[];
};

export type SleepingGiantResponse = {
  latest_report_at: string | null;
  timeframe: string;
  lookback_days: number;
  baseline_candles: number;
  scanned_symbols: number;
  candidates: SleepingGiantSetup[];
  note: string;
};

export type FuturesAnomaly = {
  symbol: string;
  direction: "breakout" | "breakdown";
  score: number;
  current_price: number;
  ret_1m: number;
  ret_5m: number;
  ret_15m: number;
  z_move_5m: number;
  volume_ratio_1m: number;
  accel_score: number;
  range_position_24h: number;
  wick_signal: number;
  order_imbalance: number;
  isolation_bonus: number;
  funding_extreme: number;
  open_interest_change_pct: number;
  liquidity_score: number;
  timestamp: string | null;
  reason_tags: string[];
};

export type FuturesAnomalyResponse = {
  latest_report_at: string | null;
  interval_seconds: number;
  lookback_hours: number;
  source: string;
  top_breakouts: FuturesAnomaly[];
  top_breakdowns: FuturesAnomaly[];
  note: string;
};

export type OneHourSpike = {
  symbol: string;
  direction: "bullish" | "bearish";
  score: number;
  current_price: number;
  latest_price_change_pct: number;
  latest_range_pct: number;
  baseline_range_pct: number;
  range_ratio: number;
  volume_ratio: number;
  latest_volume: number;
  baseline_volume: number;
  timestamp: string | null;
  reason_tags: string[];
};

export type OneHourSpikeResponse = {
  latest_report_at: string | null;
  interval_seconds: number;
  baseline_candles: number;
  scanned_symbols: number;
  candidates: OneHourSpike[];
  source: string;
  note: string;
};

export type SimulatorAnalyzeRequest = {
  symbol: string;
  side: "long" | "short";
  entry_type: "market" | "limit";
  entry_price: number;
  mark_price: number;
  margin: number;
  leverage: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  order_type: "maker" | "taker";
  timeframe: string;
};

export type SimulatorAnalyzeResponse = {
  symbol: string;
  model: string;
  used_ai: boolean;
  analysis: string;
  warnings: string[];
};

export type MarketQualityCheck = {
  name: string;
  status: "pass" | "warn" | "fail";
  detail: string;
  metric: number | null;
  threshold: number | null;
};

export type MarketQualityResponse = {
  status: "healthy" | "degraded" | "unavailable";
  score: number;
  latest_report_at: string | null;
  source: string;
  checks: MarketQualityCheck[];
  caveats: string[];
};

export type AssetResearchSource = {
  title: string;
  source: string;
  url: string;
};

export type AssetResearchSession = {
  matched_symbol: string | null;
  dominant_session: string;
  summary: string;
  latest_change_24h: number | null;
  sessions: MarketSessionMomentumCell[];
};

export type AssetResearchResponse = {
  query: string;
  normalized_query: string;
  asset_type: string;
  name: string;
  symbol: string | null;
  what: string;
  who: string;
  where: string;
  when: string;
  session_support: AssetResearchSession;
  recent_themes: string[];
  risk_notes: string[];
  what_to_watch_next: string[];
  confidence: number;
  summary_text: string;
  sources: AssetResearchSource[];
};

export type RiskPolicy = {
  id: number;
  name: string;
  max_risk_per_trade_pct: number;
  max_daily_loss_pct: number;
  max_weekly_loss_pct: number;
  max_portfolio_heat_pct: number;
  max_symbol_exposure_pct: number;
  max_open_positions: number;
  max_allowed_leverage: number;
  min_liquidation_buffer_pct: number;
  min_stop_distance_pct: number;
  buyer_absence_block_score: number;
  dead_market_block_score: number;
  require_stop_loss: boolean;
  block_new_trades_in_dead_market: boolean;
  block_longs_when_buyers_left: boolean;
  created_at: string;
  updated_at: string;
};

export type RiskQuoteState = {
  quote: string;
  risk_state: string;
};

export type AccountBalance = {
  coin: string;
  assets: number;
  free: number;
  frozen: number;
  transferable: number;
  available: number;
  unrealized_pnl: number;
  total_initial_margin: number;
  debts: number;
};

export type PositionSnapshot = {
  symbol: string;
  position_id: string;
  isolated_mode: string;
  risk_state: string;
  position_side: string;
  net_size: number;
  avg_price: number;
  mark_price: number;
  notional_value: number;
  initial_margin: number;
  maint_margin: number;
  liquidation_price: number;
  liquidation_buffer_pct: number;
  leverage: number;
  unrealized_pnl: number;
  snapshot_time: string;
};

export type OrderSnapshot = {
  symbol: string;
  order_id: string;
  client_order_id: string;
  side: string;
  position_side: string;
  order_type: string;
  price: number;
  size: number;
  filled_size: number;
  reduce_only: boolean;
  status: string;
  snapshot_time: string;
  created_time: string | null;
  updated_time: string | null;
};

export type RiskBreach = {
  code: string;
  severity: "info" | "warning" | "high" | "critical";
  message: string;
};

export type RiskSummary = {
  private_api_enabled: boolean;
  private_api_configured: boolean;
  trading_enabled: boolean;
  exit_automation_enabled: boolean;
  sync_running: boolean;
  exit_engine_running: boolean;
  last_synced_at: string | null;
  last_exit_engine_at: string | null;
  last_sync_error: string | null;
  last_exit_engine_error: string | null;
  message: string | null;
  account_currency: string;
  total_assets: number;
  account_equity: number;
  free_balance: number;
  available_margin: number;
  unrealized_pnl: number;
  total_initial_margin: number;
  debts: number;
  daily_pnl: number;
  weekly_pnl: number;
  daily_loss_used_pct: number;
  weekly_loss_used_pct: number;
  daily_loss_remaining_pct: number;
  weekly_loss_remaining_pct: number;
  portfolio_heat_pct: number;
  open_position_count: number;
  open_order_count: number;
  balances: AccountBalance[];
  risk_states: RiskQuoteState[];
  positions: PositionSnapshot[];
  orders: OrderSnapshot[];
  breaches: RiskBreach[];
  managed_exits: ManagedExitPlan[];
  exit_events: ManagedExitEvent[];
  policy: RiskPolicy;
};

export type TradeCheckRequest = {
  symbol: string;
  side: "BUY" | "SELL";
  size: number;
  entry_price: number;
  stop_price?: number;
  order_type: "LIMIT" | "MARKET_QTY" | "IOC" | "FOK" | "POSTONLY";
  position_side: "BOTH" | "LONG" | "SHORT";
  planned_leverage?: number;
  reduce_only: boolean;
};

export type ManagedExitPlan = {
  id: number;
  symbol: string;
  entry_side: string;
  position_side: string;
  stop_price: number;
  take_profit_price: number;
  expected_entry_price: number;
  expected_size: number;
  active_size: number;
  status: string;
  trigger_reason: string;
  entry_order_id: string;
  exit_order_id: string;
  retries_used: number;
  reduce_only_required: boolean;
  last_mark_price: number;
  last_trigger_price: number;
  last_error: string;
  created_at: string;
  activated_at: string | null;
  last_checked_at: string | null;
  last_exit_attempt_at: string | null;
  closed_at: string | null;
  updated_at: string;
};

export type ManagedExitEvent = {
  id: number;
  plan_id: number;
  event_type: string;
  severity: "info" | "warning" | "error" | "critical";
  message: string;
  payload_json: Record<string, unknown>;
  created_at: string;
};

export type MarketRiskContext = {
  symbol: string;
  trend_label: string;
  activity_score: number;
  bullish_score: number;
  bearish_score: number;
  buyer_absence_score: number;
  dead_market_score: number;
  quiet_rally_score: number;
  price_change_5m: number;
  price_change_15m: number;
};

export type TradeCheckLine = {
  name: string;
  passed: boolean;
  detail: string;
  metric: number | null;
  threshold: number | null;
};

export type TradeCheckResponse = {
  allowed: boolean;
  trading_enabled: boolean;
  execution_available: boolean;
  blocked_reasons: string[];
  warnings: string[];
  estimated_risk_amount: number;
  estimated_risk_pct: number;
  estimated_position_notional: number;
  estimated_margin_required: number;
  estimated_portfolio_heat_pct: number;
  estimated_symbol_exposure_pct: number;
  stop_distance_pct: number;
  market_context: MarketRiskContext | null;
  checks: TradeCheckLine[];
};

export type TradePlanRequest = {
  symbol: string;
  side: "BUY" | "SELL";
  entry_price?: number;
  size?: number;
  planned_leverage?: number;
};

export type TradePlanResponse = {
  symbol: string;
  side: "BUY" | "SELL";
  entry_price: number;
  stop_price: number;
  take_profit_price: number;
  stop_distance_pct: number;
  take_profit_distance_pct: number;
  risk_reward_ratio: number;
  atr_percent: number;
  max_risk_amount: number | null;
  suggested_size: number | null;
  market_context: MarketRiskContext | null;
  notes: string[];
};

export type OrderExecutionResponse = {
  ok: boolean;
  order_id: string;
  message: string;
  check: TradeCheckResponse;
  managed_exit_plan: ManagedExitPlan | null;
};

export type ArmManagedExitRequest = {
  symbol: string;
  side: "BUY" | "SELL";
  stop_price: number;
  take_profit_price: number;
  position_side: "BOTH";
  entry_price?: number;
  expected_size?: number;
};

export type ArmManagedExitResponse = {
  ok: boolean;
  plan: ManagedExitPlan;
  message: string;
};

export type DisarmManagedExitResponse = {
  ok: boolean;
  plan: ManagedExitPlan;
  message: string;
};

export type RunExitAutomationResponse = {
  ok: boolean;
  plans_checked: number;
  triggered: number;
  message: string;
};

export type AutomationMode = "paper" | "supervised_live" | "unattended_live";

export type AutomationControl = {
  id: number;
  mode: AutomationMode;
  kill_switch_enabled: boolean;
  kill_switch_reason: string;
  consecutive_failures: number;
  last_automation_error: string;
  last_webhook_at: string | null;
  last_reconciliation_at: string | null;
  last_watchdog_at: string | null;
  last_private_stream_event_at: string | null;
  last_public_stream_event_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AutomationAlert = {
  id: number;
  code: string;
  severity: "info" | "warning" | "high" | "critical";
  message: string;
  active: boolean;
  payload_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

export type AutomationSignal = {
  id: number;
  source: string;
  source_signal_id: string;
  strategy_name: string;
  symbol: string;
  side: string;
  mode_at_receipt: string;
  status: string;
  status_reason: string;
  requested_order_type: string;
  requested_size: number;
  requested_entry_price: number;
  requested_stop_price: number;
  requested_take_profit_price: number;
  planned_order_json: Record<string, unknown>;
  risk_check_json: Record<string, unknown>;
  execution_result_json: Record<string, unknown>;
  order_id: string;
  client_order_id: string;
  created_at: string;
  updated_at: string;
  acted_at: string | null;
};

export type AutomationSummary = {
  control: AutomationControl;
  webhook_secret_configured: boolean;
  websocket_monitoring_enabled: boolean;
  private_stream_connected: boolean;
  public_stream_connected: boolean;
  private_stream_last_error: string | null;
  public_stream_last_error: string | null;
  pending_approval_count: number;
  recent_signals: AutomationSignal[];
  alerts: AutomationAlert[];
};

export type AutomationActionResponse = {
  ok: boolean;
  message: string;
  summary: AutomationSummary;
};

export type SignalActionResponse = {
  ok: boolean;
  signal: AutomationSignal;
  message: string;
};

export type TradingViewWebhookResponse = {
  ok: boolean;
  signal: AutomationSignal;
  message: string;
};

export type ManualSignalRequest = {
  symbol: string;
  side: "BUY" | "SELL";
  order_type: "LIMIT" | "MARKET_QTY" | "IOC" | "FOK" | "POSTONLY";
  size: number;
  entry_price: number;
  stop_price?: number;
  take_profit_price?: number;
  planned_leverage?: number;
  position_side: "BOTH" | "LONG" | "SHORT";
  reduce_only: boolean;
  strategy?: string;
};

export type CopilotSignal = {
  symbol: string;
  timeframe: string;
  direction: "LONG" | "SHORT" | "NEUTRAL";
  confidence: number;
  reasons: string[];
  invalidation_level: number | null;
  suggested_stop_loss: number | null;
  suggested_take_profit: number | null;
  risk_reward_ratio: number | null;
  indicators: {
    name: string;
    value: number | string;
    direction: "LONG" | "SHORT" | "NEUTRAL";
    reason: string;
  }[];
};

export type SignalHeatmapRow = {
  symbol: string;
  cells: CopilotSignal[];
  summary: string;
  confidence: number;
};

export type SignalHeatmap = {
  symbols: string[];
  timeframes: string[];
  rows: SignalHeatmapRow[];
};

export type PaperPosition = {
  id: number;
  symbol: string;
  side: "LONG" | "SHORT";
  status: string;
  entry_price: number;
  current_price: number;
  size: number;
  leverage: number;
  margin_used: number;
  unrealized_pnl: number;
  realized_pnl: number;
  stop_loss: number;
  take_profit: number;
  trailing_stop_pct: number;
  liquidation_warning: string | null;
  opened_at: string;
  closed_at: string | null;
};

export type PaperSummary = {
  account: {
    starting_balance: number;
    cash_balance: number;
    realized_pnl: number;
    unrealized_pnl: number;
    equity: number;
    commission_paid: number;
    default_trade_size: number;
    default_leverage: number;
    commission_rate: number;
    default_stop_loss_pct: number;
    default_take_profit_pct: number;
    default_trailing_stop_pct: number;
  };
  open_positions: PaperPosition[];
  closed_positions: PaperPosition[];
  win_rate: number;
  trade_count: number;
  average_hold_minutes: number | null;
};

export type CopilotOverview = {
  app_name: string;
  mode: string;
  live_mode_locked: boolean;
  ai_signals_running: boolean;
  trader_engine_running: boolean;
  circuit_breaker_ok: boolean;
  total_account_value: number;
  buying_power: number;
  holdings_margin_used: number;
  unrealized_pnl: number;
  realized_pnl: number;
  today_pnl: number;
  win_rate: number;
  number_of_trades: number;
  best_coin: string | null;
  worst_coin: string | null;
  average_hold_minutes: number | null;
  open_positions: number;
  warnings: string[];
};

export type AssetSentiment = {
  asset: string;
  symbol: string;
  sentiment_score: number;
  confidence: number;
  article_count: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  ma_3_score: number;
  ma_8_score: number;
  ma_56_score: number;
  label: string;
  themes: string[];
  source_counts: Record<string, number>;
  example_links: {
    title: string;
    source: string;
    url: string;
  }[];
  created_at: string | null;
};

export type MarketIntelligenceRun = {
  id: number;
  status: string;
  reason: string;
  sources_checked: number;
  articles_scanned: number;
  matched_articles: number;
  error: string;
  created_at: string;
  completed_at: string | null;
};

export type MarketIntelligenceSummary = {
  enabled: boolean;
  interval_minutes: number;
  latest_run: MarketIntelligenceRun | null;
  assets: AssetSentiment[];
  note: string;
};
