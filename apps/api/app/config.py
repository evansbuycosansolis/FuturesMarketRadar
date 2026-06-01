from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parent
API_DIR = APP_DIR.parent
DEFAULT_DATABASE_URL = f"sqlite:///{(API_DIR / 'market_radar.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="FMR_",
    )

    app_name: str = "Futures Market Radar API"
    api_prefix: str = "/api"
    debug: bool = False

    pionex_base_url: str = "https://api.pionex.com"
    pionex_timeout_seconds: float = 20.0
    pionex_max_concurrent_requests: int = 16
    pionex_rate_limit_retries: int = 2
    pionex_rate_limit_backoff_seconds: float = 1.0
    binance_base_url: str = "https://fapi.binance.com"
    binance_timeout_seconds: float = 20.0

    database_url: str = DEFAULT_DATABASE_URL

    scan_interval_minutes: int = 5
    scanner_kline_limit: int = 120
    scanner_max_symbols: int = 120
    scanner_min_quote_volume: float = 50_000.0
    scanner_quote_assets: str = "USDT"
    run_initial_scan: bool = True
    enable_market_intelligence: bool = True
    run_initial_market_intelligence: bool = False
    market_intelligence_interval_minutes: int = 180
    market_intelligence_source_limit: int = 32
    market_intelligence_articles_per_source: int = 8
    market_intelligence_article_timeout_seconds: float = 8.0
    market_intelligence_fetch_article_bodies: bool = True
    risk_sync_interval_minutes: int = 1
    risk_sync_min_interval_seconds: int = 20
    risk_account_quote: str = "USDT"

    activity_threshold: float = 60.0
    bullish_threshold: float = 62.0
    bearish_threshold: float = 62.0
    watchlist_threshold: float = 46.0
    report_timezone: str = "America/Toronto"

    enable_ai_commentary: bool = False
    enable_private_api: bool = False
    enable_trading: bool = False
    enable_exit_automation: bool = False
    enable_websocket_monitoring: bool = True
    enable_binance: bool = False
    enable_binance_trading: bool = False

    pionex_api_key: str = ""
    pionex_api_secret: str = ""
    binance_api_key: str = ""
    binance_api_secret: str = ""
    exit_automation_poll_seconds: int = 10
    exit_automation_retry_cooldown_seconds: int = 8
    exit_automation_max_retries: int = 3
    exit_automation_fill_confirmation_seconds: int = 60
    tradingview_webhook_secret: str = ""
    automation_default_mode: str = "paper"
    automation_max_consecutive_failures: int = 3
    automation_sync_stale_seconds: int = 180
    automation_stream_stale_seconds: int = 45
    automation_watchdog_interval_seconds: int = 30
    automation_reconcile_interval_seconds: int = 30
    automation_signal_history_limit: int = 24

    paper_starting_balance: float = 800.0
    paper_default_trade_size: float = 25.0
    paper_default_leverage: float = 3.0
    paper_commission_rate: float = 0.0005
    paper_default_stop_loss_pct: float = 1.0
    paper_default_take_profit_pct: float = 2.0
    paper_default_trailing_stop_pct: float = 0.0

    default_max_risk_per_trade_pct: float = 1.0
    default_max_daily_loss_pct: float = 3.0
    default_max_weekly_loss_pct: float = 6.0
    default_max_portfolio_heat_pct: float = 25.0
    default_max_symbol_exposure_pct: float = 20.0
    default_max_open_positions: int = 5
    default_max_allowed_leverage: float = 5.0
    default_min_liquidation_buffer_pct: float = 12.0
    default_min_stop_distance_pct: float = 0.35
    default_stop_atr_multiplier: float = 1.2
    default_take_profit_r_multiple: float = 2.0
    default_buyer_absence_block_score: float = 70.0
    default_dead_market_block_score: float = 75.0
    default_require_stop_loss: bool = True
    default_block_new_trades_in_dead_market: bool = True
    default_block_longs_when_buyers_left: bool = True

    allow_origins: str = "http://localhost:3000"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allow_origins.split(",") if origin.strip()]

    @property
    def quote_assets(self) -> set[str]:
        return {asset.strip().upper() for asset in self.scanner_quote_assets.split(",") if asset.strip()}

    @property
    def private_api_configured(self) -> bool:
        return bool(self.pionex_api_key.strip() and self.pionex_api_secret.strip())

    @property
    def binance_configured(self) -> bool:
        return bool(self.binance_api_key.strip() and self.binance_api_secret.strip())

    @property
    def tradingview_webhook_configured(self) -> bool:
        return bool(self.tradingview_webhook_secret.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
