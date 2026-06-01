import Link from "next/link";

import { HubControlButtons } from "@/components/hub-control-buttons";
import { ManualOrderWorkspace } from "@/components/manual-order-workspace";
import { TradingViewWebhookTester } from "@/components/tradingview-webhook-tester";
import { getAutomationSummary, getCopilotOverview, getExchangeStatus, getPaperSummary, getSignalHeatmap } from "@/lib/api";
import { formatCompactNumber, formatCurrency, formatPercent, formatPrice, formatTimestamp } from "@/lib/formatters";
import type { CopilotSignal } from "@/lib/types";

function symbolName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "").replace("USDT", "");
}

function biasClass(bias: CopilotSignal["direction"]): string {
  switch (bias) {
    case "LONG":
      return "border-emerald-400/20 bg-emerald-500/70 text-white hover:bg-emerald-400/85";
    case "SHORT":
      return "border-rose-400/20 bg-rose-500/75 text-white hover:bg-rose-400/85";
    default:
      return "border-amber-400/20 bg-amber-500/70 text-white hover:bg-amber-400/85";
  }
}

function metric(label: string, value: string, tone = "text-[var(--radar-ink)]") {
  return (
    <div className="min-w-0 rounded-[22px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 transition hover:-translate-y-0.5 hover:border-[color:var(--radar-line-strong)] hover:bg-[var(--radar-panel)]">
      <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
      <div className={`mt-1 truncate text-sm font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function miniAccountCard(label: string, value: string, tone: string) {
  return (
    <div className={`min-h-24 rounded-[24px] border border-[color:rgba(238,248,244,0.16)] p-4 shadow-[0_18px_60px_-34px_rgba(0,0,0,0.8)] transition hover:-translate-y-0.5 hover:border-white/30 ${tone}`}>
      <div className="text-[10px] uppercase tracking-[0.14em] text-white/70">{label}</div>
      <div className="mt-2 text-xl font-semibold text-white">{value}</div>
    </div>
  );
}

function statusDot(active: boolean) {
  return <span className={`h-2.5 w-2.5 rounded-full ${active ? "bg-emerald-400" : "bg-rose-400"}`} />;
}

export async function TradingViewPage() {
  const [automation, exchangeStatus, overview, heatmap, paper] = await Promise.all([
    getAutomationSummary(),
    getExchangeStatus(),
    getCopilotOverview(),
    getSignalHeatmap(),
    getPaperSummary(),
  ]);

  const activeExchange = exchangeStatus.exchanges.find((exchange) => exchange.configured) ?? exchangeStatus.exchanges[0];
  const topSignals = heatmap.rows
    .flatMap((row) => row.cells.map((cell) => ({ ...cell, rowConfidence: row.confidence })))
    .sort((first, second) => second.confidence - first.confidence)
    .slice(0, 6);
  const deployedPct = overview.total_account_value > 0 ? (overview.holdings_margin_used / overview.total_account_value) * 100 : 0;
  const allowedSignals = automation.recent_signals.filter((signal) => ["paper_executed", "pending_approval", "executed"].includes(signal.status)).length;
  const blockedSignals = automation.recent_signals.filter((signal) => ["blocked", "failed", "rejected"].includes(signal.status)).length;
  const avgConfidence = heatmap.rows.length > 0 ? heatmap.rows.reduce((total, row) => total + row.confidence, 0) / heatmap.rows.length : 0;

  return (
    <div className="min-h-screen text-[var(--radar-ink)]">
      <div className="radar-shell py-6 sm:py-8">
        <header className="radar-card mb-6 overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[var(--radar-sun)] via-[var(--radar-sea)] to-[var(--radar-rose)]" />
          <div className="flex flex-wrap items-center gap-4 p-4 text-xs sm:p-5">
          <div className="text-lg font-semibold text-[var(--radar-ink)]">Evans&apos; Futures Trading Copilot</div>
          <div className="flex items-center gap-2">
            <span>Exchange:</span>
            <span className="rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-3 py-1">{activeExchange.label}</span>
          </div>
          <div className={`flex items-center gap-2 ${activeExchange.configured ? "text-emerald-300" : "text-amber-300"}`}>{statusDot(activeExchange.configured)} {activeExchange.configured ? "Connected" : "Read-only / setup"}</div>
          <div className="text-cyan-300">[{automation.control.mode.toUpperCase().replaceAll("_", " ")}]</div>
          <div>AI Signals: <span className={overview.ai_signals_running ? "text-emerald-300" : "text-rose-300"}>{overview.ai_signals_running ? "Running" : "Stopped"}</span></div>
          <div>Trader: <span className={overview.trader_engine_running ? "text-emerald-300" : "text-amber-300"}>{overview.trader_engine_running ? "Running" : "Stopped"}</span></div>
          <div>Mode: <span className="text-cyan-300">{overview.mode.replaceAll("_", " ")}</span></div>
          <div className="ml-auto flex items-center gap-2">
            <Link className="nav-link text-slate-300" href="/dashboard">Dashboard</Link>
            <Link className="nav-link text-slate-300" href="/risk">Risk</Link>
            <HubControlButtons compact killSwitchEnabled={automation.control.kill_switch_enabled} />
          </div>
        </div>
        </header>

      <ManualOrderWorkspace />

      <section className="my-6 grid grid-cols-2 gap-3 md:grid-cols-5 xl:grid-cols-9">
          {metric("Total P&L", formatCurrency(overview.realized_pnl + overview.unrealized_pnl), overview.realized_pnl + overview.unrealized_pnl >= 0 ? "text-emerald-300" : "text-rose-300")}
          {metric("Unrealized P&L", formatCurrency(overview.unrealized_pnl), overview.unrealized_pnl >= 0 ? "text-emerald-300" : "text-rose-300")}
          {metric("Today P&L", formatCurrency(overview.today_pnl), overview.today_pnl >= 0 ? "text-emerald-300" : "text-rose-300")}
          {metric("Allowed Signals", formatCompactNumber(allowedSignals), "text-emerald-300")}
          {metric("Blocked Signals", formatCompactNumber(blockedSignals), blockedSignals > 0 ? "text-rose-300" : "text-emerald-300")}
          {metric("Best Coin", overview.best_coin ? symbolName(overview.best_coin) : "Waiting", "text-emerald-300")}
          {metric("Worst Coin", overview.worst_coin ? symbolName(overview.worst_coin) : "Waiting", "text-rose-300")}
          {metric("Avg Hold", overview.average_hold_minutes ? `${Math.round(overview.average_hold_minutes)}m` : "Waiting")}
          {metric("Open Positions", formatCompactNumber(overview.open_positions))}
      </section>

      <main className="grid gap-6 xl:grid-cols-[500px_1fr]">
        <aside className="space-y-3">
          <section className="radar-card p-5">
            <div className="radar-chip mb-4">Account</div>
            <div className="grid grid-cols-2 gap-1">
              {miniAccountCard("Total Account Value", formatCurrency(overview.total_account_value), "bg-[#3b82f6]")}
              {miniAccountCard("Holdings / Margin Used", formatCurrency(overview.holdings_margin_used), "bg-[#22c55e]")}
              {miniAccountCard("Buying Power", formatCurrency(overview.buying_power), "bg-[#06b6d4]")}
              {miniAccountCard("Percent In Trade", formatPercent(deployedPct, 1), "bg-[#a855f7]")}
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
              <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-3 transition hover:border-[color:var(--radar-line-strong)]">Win Rate<br /><span className="text-cyan-300">{formatPercent(overview.win_rate, 1)}</span></div>
              <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-3 transition hover:border-[color:var(--radar-line-strong)]">Trades<br /><span className="text-emerald-300">{overview.number_of_trades}</span></div>
              <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-3 transition hover:border-[color:var(--radar-line-strong)]">Avg Signal<br /><span className="text-cyan-300">{avgConfidence.toFixed(0)}%</span></div>
            </div>
            <div className="mt-2 text-xs text-slate-300">Paper starting balance: {formatCurrency(paper.account.starting_balance)}</div>
          </section>

          <section className="radar-card min-h-[450px] p-5">
            <div className="radar-chip mb-4">Controls / Health</div>
            <div className="grid gap-2 text-xs">
              <div className="flex justify-between rounded-[16px] px-3 py-2 transition hover:bg-[var(--radar-panel-soft)]"><span>AI Signals running</span><span className="text-emerald-300">[OK]</span></div>
              <div className="flex justify-between rounded-[16px] px-3 py-2 transition hover:bg-[var(--radar-panel-soft)]"><span>Trader: {overview.trader_engine_running ? "running" : "stopped"}</span><span>{formatTimestamp(automation.control.last_watchdog_at)}</span></div>
              <div className="flex justify-between rounded-[16px] px-3 py-2 transition hover:bg-[var(--radar-panel-soft)]"><span>Bot last checked</span><span>{formatTimestamp(automation.control.last_reconciliation_at)}</span></div>
              <div className="flex justify-between rounded-[16px] px-3 py-2 transition hover:bg-[var(--radar-panel-soft)]"><span>Webhook secret</span><span className={automation.webhook_secret_configured ? "text-emerald-300" : "text-rose-300"}>{automation.webhook_secret_configured ? "Configured" : "Missing"}</span></div>
              <div className="flex justify-between rounded-[16px] px-3 py-2 transition hover:bg-[var(--radar-panel-soft)]">
                <span>Circuit Breaker</span>
                <span className={automation.control.kill_switch_enabled ? "text-rose-300" : "text-emerald-300"}>
                  {automation.control.kill_switch_enabled ? "LOCKED" : "OK"}
                </span>
              </div>
              <div className="flex justify-between rounded-[16px] px-3 py-2 transition hover:bg-[var(--radar-panel-soft)]"><span>Live mode lock</span><span className={overview.live_mode_locked ? "text-amber-300" : "text-emerald-300"}>{overview.live_mode_locked ? "Locked" : "Unlocked"}</span></div>
              <div className="flex justify-between rounded-[16px] px-3 py-2 transition hover:bg-[var(--radar-panel-soft)]"><span>Logs</span><span>{automation.alerts.length} active</span></div>
            </div>
            <div className="mt-4 flex gap-2">
              <HubControlButtons compact killSwitchEnabled={automation.control.kill_switch_enabled} />
              <Link className="ml-auto rounded-full border border-[color:var(--radar-line-strong)] px-3 py-1 text-xs transition hover:bg-[var(--radar-panel)]" href="/risk">Risk</Link>
            </div>
            <div className="mt-5 text-xs font-semibold text-cyan-300">Strong Movers</div>
            <div className="mt-2 grid gap-2 text-xs">
              {topSignals.slice(0, 5).map((signal) => (
                <div key={`${signal.symbol}-${signal.timeframe}-strong-mover`} className="grid grid-cols-[1fr_70px_70px] rounded-[16px] border border-transparent px-3 py-2 transition hover:border-[color:var(--radar-line)] hover:bg-[var(--radar-panel-soft)]">
                  <span className="font-semibold text-white">{symbolName(signal.symbol)}</span>
                  <span className={signal.direction === "SHORT" ? "text-rose-300" : "text-emerald-300"}>{signal.direction}</span>
                  <span className="text-cyan-300">{signal.confidence.toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </section>
        </aside>

        <section className="radar-card min-h-[730px] p-5">
          <div className="mb-2 flex flex-wrap gap-2 text-xs">
            {[
              ["Dashboard", "/dashboard"],
              ["AI Scanner", "#signal-matrix"],
              ["Risk", "/risk"],
              ["Logs", "#top-signals"],
              ["Docs", "#webhook-test"],
            ].map(([tab, href], index) => (
              <Link key={tab} className={`rounded-full border border-[color:var(--radar-line-strong)] px-5 py-2 transition hover:bg-[var(--radar-panel)] ${index === 1 ? "bg-[var(--radar-panel)] text-cyan-300" : ""}`} href={href}>
                {tab}
              </Link>
            ))}
          </div>
          <div className="mb-2 flex flex-wrap gap-2 text-[11px]">
            {["Overview", "Trades", "Account", "Analysis"].map((tab, index) => (
              <span key={tab} className={`rounded-full border border-[color:var(--radar-line)] px-3 py-1 transition hover:bg-[var(--radar-panel-soft)] ${index === 0 ? "text-emerald-300" : ""}`}>{tab}</span>
            ))}
          </div>

          <div id="signal-matrix" className="rounded-[26px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4 transition hover:border-[color:var(--radar-line-strong)]">
            <div className="mb-3 text-xs text-slate-300">Real Signal Matrix</div>
            <div className="grid grid-cols-[70px_repeat(7,minmax(72px,1fr))_120px] gap-1 text-center text-[11px]">
              <div />
              {heatmap.timeframes.map((column) => <div key={column} className="text-slate-300">{column}</div>)}
              <div className="text-slate-300">Summary</div>
              {heatmap.rows.map((row) => {
                return (
                  <div key={row.symbol} className="contents">
                    <div className="py-1 text-left font-semibold text-white">{symbolName(row.symbol)}</div>
                    {row.cells.map((cell) => (
                      <div key={`${row.symbol}-${cell.timeframe}`} className={`rounded-[10px] border py-1 font-semibold transition ${biasClass(cell.direction)}`}>{cell.direction}</div>
                    ))}
                    <div className="rounded-[10px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] py-1 font-semibold text-cyan-100 transition hover:border-[color:var(--radar-line-strong)]">
                      {row.summary}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div id="top-signals" className="mt-3 rounded-[26px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4 transition hover:border-[color:var(--radar-line-strong)]">
            <div className="mb-3 text-xs text-slate-300">Top Signals</div>
            <div className="grid gap-2 text-xs">
              {topSignals.map((signal) => {
                return (
                  <div key={`top-${signal.symbol}-${signal.timeframe}`} className="grid gap-1 rounded-[20px] border border-transparent p-3 transition hover:border-[color:var(--radar-line)] hover:bg-[var(--radar-panel-soft)] xl:grid-cols-[80px_1fr]">
                    <div className="font-semibold text-white">{symbolName(signal.symbol)}<br /><span className="text-[10px] text-slate-400">{signal.timeframe}</span></div>
                    <div>
                      <div className={signal.direction === "LONG" ? "text-emerald-300" : signal.direction === "SHORT" ? "text-rose-300" : "text-amber-300"}>
                        {signal.direction} ({Math.round(signal.confidence)}/100)
                      </div>
                      <div className="text-slate-300">
                        Stop: {signal.suggested_stop_loss ? formatPrice(signal.suggested_stop_loss) : "n/a"} &nbsp; Target: {signal.suggested_take_profit ? formatPrice(signal.suggested_take_profit) : "n/a"} &nbsp; Invalid: {signal.invalidation_level ? formatPrice(signal.invalidation_level) : "n/a"}
                      </div>
                      <div className="text-slate-400">
                        R/R: {signal.risk_reward_ratio?.toFixed(2) ?? "n/a"} &nbsp; {signal.reasons[0] ?? "No reason recorded."} &nbsp; Risk gate: required
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div id="webhook-test" className="mt-3">
            <TradingViewWebhookTester webhookSecretConfigured={automation.webhook_secret_configured} />
          </div>
        </section>
      </main>
      </div>
    </div>
  );
}
