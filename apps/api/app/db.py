from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    from . import models

    Base.metadata.create_all(bind=engine)
    _apply_schema_updates()


def _apply_schema_updates() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    required_columns = {
        "coin_scores": [
            ("buyer_absence_score", "FLOAT DEFAULT 0.0"),
            ("dead_market_score", "FLOAT DEFAULT 0.0"),
            ("quiet_rally_score", "FLOAT DEFAULT 0.0"),
            ("buyer_volume_share", "FLOAT DEFAULT 0.0"),
            ("green_candle_ratio", "FLOAT DEFAULT 0.0"),
        ],
        "reports": [
            ("top_buyers_left_json", "JSON"),
            ("top_dead_markets_json", "JSON"),
            ("top_quiet_rallies_json", "JSON"),
        ],
        "automation_controls": [
            ("mode", "VARCHAR(24) DEFAULT 'paper'"),
            ("kill_switch_enabled", "BOOLEAN DEFAULT 0"),
            ("kill_switch_reason", "TEXT DEFAULT ''"),
            ("consecutive_failures", "INTEGER DEFAULT 0"),
            ("last_automation_error", "TEXT DEFAULT ''"),
            ("last_webhook_at", "DATETIME"),
            ("last_reconciliation_at", "DATETIME"),
            ("last_watchdog_at", "DATETIME"),
            ("last_private_stream_event_at", "DATETIME"),
            ("last_public_stream_event_at", "DATETIME"),
            ("created_at", "DATETIME"),
            ("updated_at", "DATETIME"),
        ],
        "webhook_receipts": [
            ("source", "VARCHAR(32)"),
            ("delivery_key", "VARCHAR(128)"),
            ("payload_hash", "VARCHAR(128) DEFAULT ''"),
            ("payload_json", "JSON"),
            ("created_at", "DATETIME"),
        ],
        "automation_signals": [
            ("source", "VARCHAR(32) DEFAULT 'tradingview'"),
            ("source_signal_id", "VARCHAR(128)"),
            ("strategy_name", "VARCHAR(128) DEFAULT ''"),
            ("symbol", "VARCHAR(64)"),
            ("side", "VARCHAR(16) DEFAULT ''"),
            ("mode_at_receipt", "VARCHAR(24) DEFAULT 'paper'"),
            ("status", "VARCHAR(32) DEFAULT 'received'"),
            ("status_reason", "TEXT DEFAULT ''"),
            ("requested_order_type", "VARCHAR(24) DEFAULT ''"),
            ("requested_size", "FLOAT DEFAULT 0.0"),
            ("requested_entry_price", "FLOAT DEFAULT 0.0"),
            ("requested_stop_price", "FLOAT DEFAULT 0.0"),
            ("requested_take_profit_price", "FLOAT DEFAULT 0.0"),
            ("planned_order_json", "JSON"),
            ("risk_check_json", "JSON"),
            ("raw_payload_json", "JSON"),
            ("execution_result_json", "JSON"),
            ("order_id", "VARCHAR(96) DEFAULT ''"),
            ("client_order_id", "VARCHAR(96) DEFAULT ''"),
            ("created_at", "DATETIME"),
            ("updated_at", "DATETIME"),
            ("acted_at", "DATETIME"),
        ],
        "automation_alerts": [
            ("code", "VARCHAR(64)"),
            ("severity", "VARCHAR(16) DEFAULT 'info'"),
            ("message", "TEXT DEFAULT ''"),
            ("active", "BOOLEAN DEFAULT 1"),
            ("payload_json", "JSON"),
            ("created_at", "DATETIME"),
            ("updated_at", "DATETIME"),
            ("resolved_at", "DATETIME"),
        ],
        "paper_accounts": [
            ("starting_balance", "FLOAT DEFAULT 800.0"),
            ("cash_balance", "FLOAT DEFAULT 800.0"),
            ("realized_pnl", "FLOAT DEFAULT 0.0"),
            ("commission_paid", "FLOAT DEFAULT 0.0"),
            ("default_trade_size", "FLOAT DEFAULT 25.0"),
            ("default_leverage", "FLOAT DEFAULT 3.0"),
            ("commission_rate", "FLOAT DEFAULT 0.0005"),
            ("default_stop_loss_pct", "FLOAT DEFAULT 1.0"),
            ("default_take_profit_pct", "FLOAT DEFAULT 2.0"),
            ("default_trailing_stop_pct", "FLOAT DEFAULT 0.0"),
            ("created_at", "DATETIME"),
            ("updated_at", "DATETIME"),
        ],
        "paper_positions": [
            ("symbol", "VARCHAR(64)"),
            ("side", "VARCHAR(16)"),
            ("status", "VARCHAR(24) DEFAULT 'open'"),
            ("entry_price", "FLOAT DEFAULT 0.0"),
            ("current_price", "FLOAT DEFAULT 0.0"),
            ("size", "FLOAT DEFAULT 0.0"),
            ("leverage", "FLOAT DEFAULT 1.0"),
            ("margin_used", "FLOAT DEFAULT 0.0"),
            ("stop_loss", "FLOAT DEFAULT 0.0"),
            ("take_profit", "FLOAT DEFAULT 0.0"),
            ("trailing_stop_pct", "FLOAT DEFAULT 0.0"),
            ("highest_price", "FLOAT DEFAULT 0.0"),
            ("lowest_price", "FLOAT DEFAULT 0.0"),
            ("realized_pnl", "FLOAT DEFAULT 0.0"),
            ("fees_paid", "FLOAT DEFAULT 0.0"),
            ("close_price", "FLOAT DEFAULT 0.0"),
            ("close_reason", "VARCHAR(64) DEFAULT ''"),
            ("opened_at", "DATETIME"),
            ("closed_at", "DATETIME"),
            ("updated_at", "DATETIME"),
        ],
        "copilot_logs": [
            ("category", "VARCHAR(32)"),
            ("severity", "VARCHAR(16) DEFAULT 'info'"),
            ("message", "TEXT DEFAULT ''"),
            ("payload_json", "JSON"),
            ("created_at", "DATETIME"),
        ],
        "market_intelligence_runs": [
            ("status", "VARCHAR(24) DEFAULT 'running'"),
            ("reason", "VARCHAR(32) DEFAULT 'scheduled'"),
            ("sources_checked", "INTEGER DEFAULT 0"),
            ("articles_scanned", "INTEGER DEFAULT 0"),
            ("matched_articles", "INTEGER DEFAULT 0"),
            ("error", "TEXT DEFAULT ''"),
            ("created_at", "DATETIME"),
            ("completed_at", "DATETIME"),
        ],
        "asset_sentiment_snapshots": [
            ("run_id", "INTEGER DEFAULT 0"),
            ("asset", "VARCHAR(16)"),
            ("symbol", "VARCHAR(32)"),
            ("sentiment_score", "FLOAT DEFAULT 0.0"),
            ("confidence", "FLOAT DEFAULT 0.0"),
            ("article_count", "INTEGER DEFAULT 0"),
            ("positive_count", "INTEGER DEFAULT 0"),
            ("negative_count", "INTEGER DEFAULT 0"),
            ("neutral_count", "INTEGER DEFAULT 0"),
            ("ma_3_score", "FLOAT DEFAULT 0.0"),
            ("ma_8_score", "FLOAT DEFAULT 0.0"),
            ("ma_56_score", "FLOAT DEFAULT 0.0"),
            ("themes_json", "JSON"),
            ("source_counts_json", "JSON"),
            ("example_links_json", "JSON"),
            ("created_at", "DATETIME"),
        ],
    }

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in required_columns.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }
            for column_name, column_definition in columns:
                if column_name not in existing_columns:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
                    )
