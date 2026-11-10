# Evans' Futures Trading Copilot

## Integrated OpenAI workspace

Double-click `Start-Integrated-Desk.cmd` to launch the sidebar-based workspace at `http://127.0.0.1:3000/desk`. It combines Radar's existing tools with the local Agentic OpenAI research desk, saved conversations, a Hyperliquid market lens, and explicitly sourced Radar evidence. The launcher starts with exchange execution and private sync disabled. See [Desk integration](DESK_INTEGRATION.md) for source-checkout configuration, service boundaries, and verification.

The research runtime is included in `vendor/agentic`, with its MIT license and source attribution. After cloning this branch, install the backend requirements in a virtual environment and run `npm ci` in `apps/web`, then use the launcher. Your OpenAI key is configured locally through the desk connection settings or process environment. See [third-party notices](THIRD_PARTY_NOTICES.md).

Evans' Futures Trading Copilot is a personal Pionex futures trading management system. It is designed as a professional, risk-first dashboard for monitoring markets, reviewing deterministic signals, managing paper trades, checking risk, and controlling live-trading authority.

This is not a reckless auto-trading bot. Live execution is locked behind explicit backend flags, deterministic risk checks, kill-switch controls, and supervised rollout steps.

The project is intentionally deterministic:

- The scanner computes numerical activity, bullish, and bearish scores.
- The market intelligence agent reads public crypto/news feeds every three hours, scores BTC/ETH/XRP/SOL sentiment, and stores only aggregate decision-support snapshots.
- The report layer explains the scores in plain English.
- The risk layer syncs private account state, enforces hard limits, and blocks trades that violate policy.
- Live order execution exists, but it is disabled by default behind explicit backend flags.
- Binance support is being introduced behind separate configuration flags so account monitoring can arrive before any live execution.
- Paper trading exists before real trading so entries, exits, fees, P&L, win rate, average hold time, and logs can be tested with a default starting balance of `$800`.
- News sentiment is never used to place, approve, or size trades.

Futures trading is high risk. This app is software support for monitoring and risk control; it is not financial advice.

## Stack

- Frontend: Next.js 16 + TypeScript + Tailwind CSS 4
- Backend: FastAPI + Python
- Database: SQLite
- Scheduler: APScheduler
- Market data: Pionex Futures REST API
- Private account and trading: Pionex Futures private REST API
- Planned second exchange: Binance USD-M Futures REST API

## Project Layout

```text
.
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── db.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── routes/
│   │   │   └── services/
│   │   ├── .env.example
│   │   └── requirements.txt
│   └── web/
│       ├── .env.local.example
│       ├── package.json
│       └── src/
│           ├── app/
│           ├── components/
│           └── lib/
└── README.md
```

## What The Scanner Does

Every run:

1. Pulls futures symbol metadata from Pionex.
2. Pulls 24h ticker data and open interest snapshots.
3. Filters to a liquid scan universe by quote asset and quote volume.
4. Pulls recent 1-minute candles for that liquid subset.
5. Derives 5-minute and 15-minute momentum from those 1-minute candles.
6. Computes activity, bullish, bearish, buyer-absence, dead-market, and watchlist signals.
7. Stores snapshots, scores, and a report in SQLite.
8. Exposes the latest report and history through FastAPI.

## What The Market Intelligence Agent Does

Every three hours, the read-only intelligence agent:

1. Reads public RSS/news feeds from configured crypto and financial sources.
2. Fetches matching public article pages for more NLP context.
3. Scores title-confirmed BTC, ETH, XRP, and SOL mentions with a crypto-aware sentiment engine.
4. Aggregates per-asset sentiment, confidence, positive/neutral/negative counts, themes, and source counts.
5. Computes moving averages for the last 3, 8, and 56 runs, which roughly map to 9 hours, 24 hours, and 7 days at the default interval.
6. Stores only aggregate sentiment snapshots plus source/link metadata for auditability; it does not store full article bodies.

This layer is decision support only. It is intentionally separate from the TradingView webhook, risk gate, paper engine, and live execution paths.

## What The Risk Layer Adds

- Private account sync for balances, positions, and open orders
- Deterministic risk policy storage in SQLite
- Pre-trade risk checks for size, stop, leverage, portfolio heat, symbol concentration, and daily or weekly lockouts
- Market-aware trade blocking, such as rejecting longs when buyer-absence conditions are active
- Optional live order routing through Pionex, disabled by default until you explicitly enable it
- Automation modes for `paper`, `supervised_live`, and `unattended_live`
- A hard kill-switch, watchdog alerts, restart-safe reconciliation, and websocket-backed managed-exit monitoring
- TradingView webhook intake with secret verification, replay protection, signal normalization, and a full risk gate before execution

## Why The Scanner Uses 1-Minute Candles

Pionex futures is still marked Beta, and a naive implementation that requests separate 1m, 5m, and 15m candle sets for every contract would create far more API traffic than we need.

This build uses one 1-minute candle stream per symbol and derives:

- `price_change_5m`
- `price_change_15m`
- `volume_spike_ratio`
- `ATR %`
- `EMA 20`
- `EMA 50`

That keeps the code aligned with the Version 1 goal while being gentler on API limits.

## Verified Pionex Endpoints

These public endpoints were verified against live responses on May 6, 2026:

- `GET https://api.pionex.com/api/v1/common/symbols`
- `GET https://api.pionex.com/api/v1/market/tickers`
- `GET https://api.pionex.com/api/v1/market/klines`
- `GET https://api.pionex.com/api/v1/market/depth`
- `GET https://api.pionex.com/api/v1/market/bookTicker`
- `GET https://api.pionex.com/api/v1/market/fundingRates`
- `GET https://api.pionex.com/api/v1/market/indexes`
- `GET https://api.pionex.com/api/v1/market/openInterests`

Reference docs:

- https://www.pionex.com/docs/api-docs/futures-api/general-info/basic-info
- https://www.pionex.com/docs/api-docs/futures-api/common
- https://www.pionex.com/docs/api-docs/futures-api/market
- https://www.pionex.com/docs/api-docs/futures-websocket/public-stream

## Backend Setup

```powershell
cd apps/api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8010
```

Important:

- Backend env vars are prefixed with `FMR_` to avoid collisions with machine-wide variables like `DEBUG`.
- The default database path is `apps/api/market_radar.db`.

Useful backend routes:

- `GET /api/health`
- `GET /api/copilot/overview`
- `GET /api/copilot/signal-heatmap`
- `GET /api/copilot/logs`
- `GET /api/intelligence/summary`
- `POST /api/intelligence/run-now`
- `GET /api/paper/summary`
- `POST /api/paper/positions`
- `POST /api/paper/positions/{id}/close`
- `GET /api/symbols`
- `GET /api/market/top-active`
- `GET /api/market/top-bullish`
- `GET /api/market/top-bearish`
- `GET /api/market/top-buyers-left`
- `GET /api/market/top-dead-markets`
- `GET /api/market/watchlist`
- `GET /api/reports/latest`
- `GET /api/reports/history`
- `POST /api/scanner/run-now`
- `GET /api/exchanges/status`
- `GET /api/risk/summary`
- `POST /api/risk/sync-now`
- `GET /api/risk/policies`
- `PUT /api/risk/policies`
- `POST /api/risk/check-trade`
- `POST /api/trading/order`
- `POST /api/trading/cancel-all`
- `GET /api/automation/summary`
- `PUT /api/automation/control`
- `POST /api/automation/kill-switch/engage`
- `POST /api/automation/kill-switch/release`
- `POST /api/automation/reconcile-now`
- `POST /api/automation/watchdog/run-now`
- `POST /api/automation/signals/{id}/approve`
- `POST /api/automation/signals/{id}/reject`
- `POST /api/webhooks/tradingview`

Risk and private-trading env vars:

```text
FMR_ENABLE_PRIVATE_API=false
FMR_ENABLE_TRADING=false
FMR_ENABLE_EXIT_AUTOMATION=false
FMR_ENABLE_WEBSOCKET_MONITORING=true
FMR_ENABLE_BINANCE=false
FMR_ENABLE_BINANCE_TRADING=false
FMR_PIONEX_API_KEY=
FMR_PIONEX_API_SECRET=
FMR_BINANCE_API_KEY=
FMR_BINANCE_API_SECRET=
FMR_TRADINGVIEW_WEBHOOK_SECRET=
FMR_AUTOMATION_DEFAULT_MODE=paper
FMR_AUTOMATION_MAX_CONSECUTIVE_FAILURES=3
FMR_AUTOMATION_SYNC_STALE_SECONDS=180
FMR_AUTOMATION_STREAM_STALE_SECONDS=45
FMR_PAPER_STARTING_BALANCE=800
FMR_PAPER_DEFAULT_TRADE_SIZE=25
FMR_PAPER_DEFAULT_LEVERAGE=3
FMR_PAPER_COMMISSION_RATE=0.0005
FMR_PAPER_DEFAULT_STOP_LOSS_PCT=1.0
FMR_PAPER_DEFAULT_TAKE_PROFIT_PCT=2.0
FMR_PAPER_DEFAULT_TRAILING_STOP_PCT=0.0
```

Recommended rollout:

- Start with `FMR_ENABLE_PRIVATE_API=true` and `FMR_ENABLE_TRADING=false`
- Confirm the Risk page is syncing balances, positions, and orders correctly
- Test the policy editor and pre-trade checker
- If you want live app-managed stop-loss and take-profit supervision, set `FMR_ENABLE_EXIT_AUTOMATION=true`
- Managed exit automation currently supports one-way mode only because Pionex documents `reduceOnly` for `BOTH` mode, not hedge mode
- Add `FMR_TRADINGVIEW_WEBHOOK_SECRET` before exposing `POST /api/webhooks/tradingview`
- Keep the automation mode on `paper` first, then move to `supervised_live`, then `unattended_live`
- Only then consider setting `FMR_ENABLE_TRADING=true`

Security requirements:

- Never expose API secrets to the frontend.
- Never commit real `.env` files or API secrets to GitHub.
- Use read-only exchange keys first.
- Disable withdrawals on exchange API keys.
- Use an IP whitelist on Pionex API keys before private sync.
- Keep `FMR_ENABLE_TRADING=false` until paper mode, risk checks, and supervised approval are verified.

## Frontend Setup

```powershell
cd apps/web
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Frontend env values:

```text
API_BASE_URL=http://127.0.0.1:8010
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010
```

Open:

- Dashboard: http://localhost:3000/dashboard
- Reports: http://localhost:3000/reports
- Risk: http://localhost:3000/risk
- TradingView: http://localhost:3000/tradingview

## TradingView Webhook Flow

The webhook route is:

```text
POST /api/webhooks/tradingview
```

Inside the app, the TradingView workspace is:

```text
http://localhost:3000/tradingview
```

The app verifies a shared secret from either:

- the `X-FMR-Webhook-Secret` header
- or a `secret` field in the JSON payload

Suggested TradingView payload shape:

```json
{
  "id": "tv-setup-001",
  "strategy": "quiet-rally-breakout",
  "symbol": "BTC_USDT_PERP",
  "action": "BUY",
  "order_type": "MARKET_QTY",
  "size": 0.01,
  "entry_price": 103250,
  "stop_price": 102400,
  "take_profit_price": 104950,
  "leverage": 3,
  "secret": "your-shared-secret"
}
```

If `stop_price`, `take_profit_price`, `entry_price`, or `size` are missing, the app tries to fill the gaps deterministically from the current market context and your policy budget before it decides whether to queue or execute the signal.

## Scoring Model

### Activity Score

- Volume spike: 35 points
- 5-minute move: 20 points
- 15-minute move: 15 points
- ATR volatility: 15 points
- Open-interest change: 15 points

### Bullish Score

- Positive 5-minute move: 20 points
- Positive 15-minute move: 20 points
- Price above EMA 20: 15 points
- Price above EMA 50: 15 points
- Volume spike: 15 points
- Open interest rising: 10 points
- Strong close: 5 points

### Bearish Score

- Negative 5-minute move: 20 points
- Negative 15-minute move: 20 points
- Price below EMA 20: 15 points
- Price below EMA 50: 15 points
- Volume spike during weakness: 15 points
- Open interest rising during selloff: 10 points
- Strong bearish close: 5 points

### Buyer Absence Score

- Low green-volume share: 25 points
- Red-over-green volume imbalance: 20 points
- Repeated close-near-low candles: 15 points
- Failed EMA reclaim / lower-high structure: 15 points
- Open-interest pressure during a down move: 15 points
- Too few green candles: 10 points

### Dead Market Score

- Little to no 15-minute movement: 20 points
- ATR compression: 25 points
- Relative volume dryness: 25 points
- Flat open interest: 15 points
- Range compression: 15 points

## Notes

- The current AI explanation layer is local and deterministic. It is structured as a service so you can swap in an LLM later without changing the scoring engine.
- The scheduler runs every five minutes and also supports manual scans through `POST /api/scanner/run-now`.
- The risk sync scheduler runs independently when private API access is enabled.
- The managed exit engine runs on its own short polling loop when `FMR_ENABLE_EXIT_AUTOMATION=true`.
- The automation watchdog and reconciliation loops run independently when the API starts.
- Public futures websocket monitoring uses Pionex `TRADE` updates, and private websocket monitoring uses `ORDER`, `FILL`, and `POSITION` updates.
- Private execution uses the current Pionex futures API, which is still marked Beta in the official docs, so keep live trading disabled until you are comfortable with the guardrails.
- The automation stack still keeps the polling loop as a fallback, but it now uses the documented Pionex websocket feeds for faster exit awareness.

## Verification Completed

These checks passed in the current workspace:

- `npm run lint` in `apps/web`
- `npm run build` in `apps/web`
- `python -m compileall app` in `apps/api`
- `python -c "from app.main import app; print(app.title)"` in `apps/api`
