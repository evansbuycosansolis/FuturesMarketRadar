# Local OpenAI trading desk

This local application extends the existing Python desk with a browser interface and direct OpenAI Responses API integration. Grok, Vercel, Node.js, npm, and a Hyperliquid wallet are not required. Python 3.10 or newer and an internet connection are sufficient; there are no additional Python dependencies.

## Start

On Windows, double-click `Start-Desk.cmd` in the project folder. It starts the local server and opens the browser. Keep its terminal open while using the app; Ctrl+C stops it.

Alternatively, run from the project folder:

```powershell
python -m local_app.server --open
```

Open `http://127.0.0.1:8765`. If that port is occupied, use `python -m local_app.server --port 8766 --open`.

In Settings, enter your OpenAI API key and a model ID with Responses API and function calling access. The default is `gpt-5.4`; availability depends on your OpenAI project. A key already set as `OPENAI_API_KEY` in the launching process is loaded automatically; `OPENAI_MODEL` can override the initial model. The app does not load `.env` files. Keys entered in Settings stay in server memory until disconnected or the server stops; no key is written to the browser's persistent storage, conversation database, or repository. Settings changes are session-only. If an environment key remains configured, restarting the server loads it again.

Market snapshots work without an OpenAI key. A configured key has not necessarily been validated; the first chat request verifies access through a real API call. Model, authentication, quota and network failures appear in the interface. Messages, loaded instructions, and tool results needed for the request go to OpenAI. Calls use `store: false`; this does not promise zero provider-side retention. API usage is charged to your OpenAI project. Each turn displays aggregate input/output token usage, including successful specialist consultations.

## What works

- Desk chat with any of the seven source role profiles, loaded from this checkout.
- Desk Lead consultations with at most two specialists per turn, as labelled model passes. Specialists cannot delegate again. All passes share a ten-request budget per turn.
- Current Hyperliquid mainnet perp snapshots, including supported HIP-3 markets. The market lens refreshes on page load and on request, not continuously.
- Optional FuturesMarketRadar integration: `radar_evidence` reads only the fixed public-evidence route at `AGENTIC_RADAR_URL` (default `http://127.0.0.1:8010`). Only loopback HTTP origins are accepted; trading routes are never exposed. Stored scanner and sentiment observations retain their own venue, observation times, and coverage limitations.
- Source evidence, coverage flags, observation times, and tool results visible in the interface.
- Stressed stop-cost estimates using the existing public-data script and the user's explicit plan and equity. These estimates are not a complete Risk PASS.
- Local saved conversations and evidence. Failed turns are not recorded as completed conversations; the input remains available for retry.

The Research Analyst can explain methods and evaluate provided evidence, but no live news or browser tool is connected. No historical dataset collection, code execution, backtest runner, account reader, autonomous monitoring, or order sender is exposed through this app. Execution Trader is available for research and process questions only. The application cannot create or approve a live ticket, sign an order, change leverage, cancel an order, or call an exchange write endpoint. Trading remains a separate future implementation subject to the project's existing financial controls.

## Local data and access

On Windows, conversations live in `%LOCALAPPDATA%/AgenticTradingDesk/desk.sqlite3`, outside the source checkout. Other systems use `~/.local/share/AgenticTradingDesk/desk.sqlite3`. `--data-dir` selects another directory. The database contains plaintext conversations and evidence, so protect it as personal local data. No trading credentials are requested or used.

The server binds only to `127.0.0.1`. It checks the Host header, browser origin and a per-run token on mutations, uses a fixed static-file map, and executes only allowlisted read-only scripts without a shell. It is a single-user local app, not a hosted or multi-user service. Other software running under your local user account may access local data. Do not expose its port through a proxy or network tunnel.

## Verification

```powershell
python -m unittest local_app.test_journeys
```

These offline loopback journeys cover API-key non-disclosure, failed turns, persistence, Responses tool handoffs, specialist boundaries, cross-origin rejection, and refusal of exchange routes. The original repository check remains `bash scripts/check.sh`; on Windows use Git Bash with a working `python3` command rather than an unconfigured WSL launcher.

Implementation references: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) and [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4). Original project authorship and MIT notice remain in [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md). The local application has not been published to the upstream package or runtime marketplaces.
