# Personal Trading Management App Plan

This project is already a strong base for a private trading command center. It has a Pionex futures scanner, account sync, risk policies, trade checks, optional execution, TradingView webhook intake, automation modes, and managed exits.

The next version should become a personal multi-exchange trading manager for:

- Monitoring Pionex and Binance account state in one place
- Managing balances, positions, orders, risk limits, and daily loss limits
- Planning trades before execution
- Executing only after deterministic risk checks pass
- Keeping live trading disabled by default until explicitly enabled

## Guiding Rules

- Treat execution as the last step, not the first feature.
- Keep exchange credentials only in backend environment variables.
- Use read-only API keys first, then enable trading keys later.
- Keep Pionex and Binance behind exchange adapters with a shared internal model.
- Store every sync, order intent, risk decision, execution result, and automation action.
- Preserve paper mode, supervised live mode, kill switch, and manual approvals.

## Current App Shape

Already present:

- Pionex public futures market scanner
- Pionex private futures client
- Account snapshots, position snapshots, order snapshots
- Risk policy editor
- Trade risk checker
- Optional live order route
- Managed stop-loss and take-profit automation
- TradingView webhook route
- Dashboard, Reports, and Risk pages

Needs to be added or generalized:

- Exchange selector and unified exchange identity
- Binance futures private client
- Binance market data adapter, if we want Binance-native scans
- Combined portfolio dashboard
- Multi-exchange risk aggregation
- Per-exchange execution toggles
- Trade journal and performance review
- Credential setup/status page
- Audit log page

## Target Architecture

Add an internal exchange interface instead of tying all trading logic directly to Pionex.

Suggested backend modules:

```text
apps/api/app/exchanges/
  __init__.py
  base.py
  pionex.py
  binance.py
  registry.py
```

The shared adapter should expose:

- `exchange_id`
- `is_configured`
- `get_account_state()`
- `get_open_orders(symbol=None)`
- `place_order(order)`
- `cancel_all_orders(symbol)`
- `get_order_by_client_order_id(symbol, client_order_id)`
- `close()`

The app should normalize exchange-specific records into internal models:

- `AccountState`
- `AccountBalance`
- `Position`
- `OpenOrder`
- `ExecutionOrder`
- `ExecutionResult`

## Data Model Changes

Add an `exchange` column to exchange-owned tables:

- `account_snapshots`
- `position_snapshots`
- `order_snapshots`
- `managed_exit_plans`
- `managed_exit_events`
- `automation_signals`
- `webhook_receipts`, if routing by source exchange

Future tables worth adding:

- `trade_journal_entries`
- `execution_audit_events`
- `exchange_connections`
- `daily_performance_snapshots`

Because this app currently uses SQLite with `create_all`, migrations should be introduced before the schema gets much more complex. Alembic would be the natural fit.

## Environment Variables

Keep the current Pionex values:

```text
FMR_PIONEX_API_KEY=
FMR_PIONEX_API_SECRET=
FMR_ENABLE_PRIVATE_API=false
FMR_ENABLE_TRADING=false
```

Add Binance-specific values:

```text
FMR_ENABLE_BINANCE=false
FMR_BINANCE_BASE_URL=https://fapi.binance.com
FMR_BINANCE_API_KEY=
FMR_BINANCE_API_SECRET=
FMR_ENABLE_BINANCE_TRADING=false
```

For safety, live trading should require both a global switch and an exchange-specific switch:

```text
FMR_ENABLE_TRADING=true
FMR_ENABLE_BINANCE_TRADING=true
```

## Implementation Phases

### Phase 1: Personal Control Center

- Rename UI copy from Pionex-only language to personal multi-exchange language.
- Add an exchange status panel showing Pionex connected, Binance not configured, paper/live state, and kill-switch state.
- Add a setup checklist page for API keys, read-only mode, trading mode, and webhook secret.
- Keep execution disabled.

### Phase 2: Exchange Abstraction

- Introduce exchange adapter interfaces.
- Wrap the current Pionex private client in a Pionex adapter.
- Update risk sync to store `exchange`.
- Update summaries to return per-exchange and combined totals.
- Keep all current behavior working for Pionex.

### Phase 3: Binance Read-Only Sync

- Add Binance USD-M futures client.
- Sync Binance account info, balances, positions, and open orders.
- Display Binance data in the Risk page.
- Add combined account equity, margin, unrealized PnL, open position count, and exposure.
- Keep Binance execution disabled.

### Phase 4: Unified Risk Engine

- Apply global rules across all exchanges.
- Apply optional exchange-specific limits.
- Add per-symbol combined exposure where symbols map across exchanges, for example `BTC_USDT_PERP` and `BTCUSDT`.
- Add daily and weekly loss controls using combined equity snapshots.
- Add audit logs for every blocked or allowed trade.

### Phase 5: Supervised Execution

- Add Binance order placement behind `FMR_ENABLE_BINANCE_TRADING`.
- Add an exchange selector to the trade ticket.
- Require risk check before execution.
- Add manual approval flow for webhook or automation signals.
- Record execution results and reconciliation status.

### Phase 6: Personal Trade Journal

- Add journal entries linked to signals, risk checks, orders, and positions.
- Track setup, thesis, mistake tags, screenshots or notes, planned R, realized R, and emotional state.
- Add review filters by exchange, symbol, strategy, session, and day.

## Safety Checklist Before Any Live Execution

- Use IP-whitelisted API keys where supported.
- Start with read-only keys.
- Keep withdrawals disabled on all API keys.
- Test Binance through testnet or paper mode before live mode.
- Keep `FMR_ENABLE_TRADING=false` until account sync and risk checks are verified.
- Keep automation in `paper`, then `supervised_live`, then only later `unattended_live`.
- Require stop-loss for all non-reduce-only trades.
- Keep the kill switch visible on the Risk page.

## Official API References Checked

- Pionex Futures API docs: https://www.pionex.com/docs/api-docs/futures-api/general-info/basic-info
- Pionex Futures account docs: https://www.pionex.com/docs/api-docs/futures-api/account
- Pionex Futures private stream docs: https://www.pionex.com/docs/api-docs/futures-websocket/private-stream
- Binance USD-M Futures new order docs: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order
- Binance USD-M Futures account info docs: https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Account-Information-V3
- Binance USD-M Futures user data stream docs: https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams

