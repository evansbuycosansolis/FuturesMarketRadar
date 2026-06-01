import { AppFrame } from "@/components/app-frame";
import { AutomationControlPanel } from "@/components/automation-control-panel";
import { AutomationSignalPanel } from "@/components/automation-signal-panel";
import { ExchangeStatusPanel } from "@/components/exchange-status-panel";
import { ManagedExitsPanel } from "@/components/managed-exits-panel";
import { RiskPolicyPanel } from "@/components/risk-policy-panel";
import { RiskSyncButton } from "@/components/risk-sync-button";
import { TradeRiskChecker } from "@/components/trade-risk-checker";
import { getAutomationSummary, getExchangeStatus, getRiskSummary } from "@/lib/api";
import { formatCompactNumber, formatCurrency, formatPercent, formatSignedNumber, formatTimestamp } from "@/lib/formatters";

function statCard(label: string, value: string, detail: string) {
  return (
    <div className="radar-card min-w-0 p-5 sm:p-6">
      <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-[var(--radar-ink)]">{value}</div>
      <div className="mt-2 text-sm text-[var(--radar-muted)]">{detail}</div>
    </div>
  );
}

function severityTone(severity: "info" | "warning" | "high" | "critical"): string {
  switch (severity) {
    case "critical":
      return "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] text-rose-100";
    case "high":
      return "border-[color:rgba(244,173,61,0.24)] bg-[rgba(80,54,15,0.34)] text-amber-100";
    case "warning":
      return "border-[color:rgba(108,152,255,0.22)] bg-[rgba(20,30,54,0.4)] text-sky-100";
    default:
      return "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] text-emerald-100";
  }
}

export async function RiskPage() {
  const [summary, automation, exchangeStatus] = await Promise.all([getRiskSummary(), getAutomationSummary(), getExchangeStatus()]);

  return (
    <AppFrame
      current="risk"
      title="Trade through your risk playbook instead of a feelings-based platform."
      subtitle="Sync account state, enforce hard limits, route every entry through deterministic checks, and keep Pionex or Binance execution locked until you explicitly enable it."
      actions={<RiskSyncButton />}
    >
      <ExchangeStatusPanel status={exchangeStatus} />

      <section className="grid gap-4 xl:grid-cols-8">
        {statCard(
          "Private API",
          summary.private_api_enabled ? (summary.private_api_configured ? "Connected" : "Needs Keys") : "Off",
          summary.private_api_enabled
            ? summary.private_api_configured
              ? `Last sync ${formatTimestamp(summary.last_synced_at)}`
              : "Add Pionex API credentials to start syncing the account."
            : "Enable private sync in the backend env when you are ready.",
        )}
        {statCard(
          "Trading Mode",
          summary.trading_enabled ? "Live Enabled" : "Guardrail Only",
          summary.trading_enabled ? "Orders can be sent after a passing risk check." : "Execution is intentionally disabled by default.",
        )}
        {statCard(
          "Automation Mode",
          automation.control.mode.replaceAll("_", " "),
          automation.control.kill_switch_enabled
            ? `Kill-switch engaged: ${automation.control.kill_switch_reason || "manual hard stop"}`
            : "Signals route according to the current automation stage.",
        )}
        {statCard(
          "Exit Engine",
          summary.exit_automation_enabled ? "Armed" : "Off",
          summary.exit_automation_enabled
            ? `Last cycle ${formatTimestamp(summary.last_exit_engine_at)}`
            : "Live stop/TP automation is disabled by default.",
        )}
        {statCard(
          "Account Equity",
          summary.account_equity > 0 ? formatCurrency(summary.account_equity) : "Waiting",
          `${summary.account_currency} account view from the latest synced snapshot.`,
        )}
        {statCard(
          "Daily PnL",
          summary.account_equity > 0 ? `${summary.daily_pnl >= 0 ? "+" : ""}${formatCurrency(summary.daily_pnl)}` : "Waiting",
          `${formatPercent(summary.daily_loss_used_pct)} of the daily loss budget used.`,
        )}
        {statCard(
          "Portfolio Heat",
          summary.account_equity > 0 ? formatPercent(summary.portfolio_heat_pct) : "Waiting",
          `${formatCurrency(summary.total_initial_margin)} in initial margin across current positions.`,
        )}
        {statCard(
          "Open Risk",
          formatCompactNumber(summary.open_position_count),
          `${summary.open_order_count} live orders and ${summary.positions.length} tracked positions in the last snapshot.`,
        )}
      </section>

      {summary.message ? (
        <section className="radar-card p-6 sm:p-8">
          <div className="space-y-4">
            <div className="radar-chip">Setup</div>
            <h2 className="text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Account-aware risk mode still needs one more step</h2>
            <p className="max-w-4xl text-sm leading-7 text-[var(--radar-muted)]">{summary.message}</p>
            <div className="rounded-[22px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 text-sm leading-7 text-[var(--radar-ink)]">
              Backend envs to know: <span className="font-mono">FMR_ENABLE_PRIVATE_API</span>,
              {" "}
              <span className="font-mono">FMR_PIONEX_API_KEY</span>,
              {" "}
              <span className="font-mono">FMR_PIONEX_API_SECRET</span>,
              {" "}
              <span className="font-mono">FMR_ENABLE_BINANCE</span>,
              {" "}
              <span className="font-mono">FMR_BINANCE_API_KEY</span>,
              {" "}
              <span className="font-mono">FMR_BINANCE_API_SECRET</span>,
              {" "}
              <span className="font-mono">FMR_ENABLE_TRADING</span>,
              {" "}
              <span className="font-mono">FMR_ENABLE_EXIT_AUTOMATION</span>.
            </div>
          </div>
        </section>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="radar-card p-6 sm:p-7">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="radar-chip">Breach Monitor</div>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Rules that are red right now</h2>
            </div>
            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
              <div>Last synced: {formatTimestamp(summary.last_synced_at)}</div>
              <div>Sync running: {summary.sync_running ? "Yes" : "No"}</div>
              <div>Last sync error: {summary.last_sync_error ?? "None"}</div>
            </div>
          </div>
          <div className="mt-6 grid gap-3">
            {summary.breaches.map((breach) => (
              <div key={breach.code} className={`rounded-[20px] border px-4 py-3 text-sm leading-7 ${severityTone(breach.severity)}`}>
                <div className="text-xs uppercase tracking-[0.16em] opacity-80">{breach.severity}</div>
                <div className="mt-1 font-medium">{breach.message}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="radar-card p-6 sm:p-7">
          <div className="radar-chip">Risk State</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Account pressure and loss runway</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {[
              ["Available Margin", formatCurrency(summary.available_margin)],
              ["Free Balance", formatCurrency(summary.free_balance)],
              ["Unrealized PnL", `${summary.unrealized_pnl >= 0 ? "+" : ""}${formatCurrency(summary.unrealized_pnl)}`],
              ["Weekly PnL", `${summary.weekly_pnl >= 0 ? "+" : ""}${formatCurrency(summary.weekly_pnl)}`],
              ["Daily Remaining", formatPercent(summary.daily_loss_remaining_pct)],
              ["Weekly Remaining", formatPercent(summary.weekly_loss_remaining_pct)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4">
                <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
                <div className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">{value}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-[22px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Quote Risk States</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {summary.risk_states.length > 0 ? (
                summary.risk_states.map((risk) => (
                  <span key={`${risk.quote}-${risk.risk_state}`} className="radar-chip">
                    {risk.quote}: {risk.risk_state || "NORMAL"}
                  </span>
                ))
              ) : (
                <span className="text-sm text-[var(--radar-muted)]">No exchange risk flags in the latest snapshot.</span>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <AutomationControlPanel summary={automation} />
        <AutomationSignalPanel summary={automation} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
        <RiskPolicyPanel policy={summary.policy} />
        <TradeRiskChecker defaultSymbol={summary.positions[0]?.symbol ?? ""} />
      </section>

      <ManagedExitsPanel
        enabled={summary.exit_automation_enabled}
        running={summary.exit_engine_running}
        lastError={summary.last_exit_engine_error}
        lastRunAt={summary.last_exit_engine_at}
        privateStreamConnected={automation.private_stream_connected}
        publicStreamConnected={automation.public_stream_connected}
        privateStreamLastError={automation.private_stream_last_error}
        publicStreamLastError={automation.public_stream_last_error}
        plans={summary.managed_exits}
        events={summary.exit_events}
      />

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="radar-card overflow-hidden p-6 sm:p-7">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="radar-chip">Open Positions</div>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Live futures exposure</h2>
            </div>
            <p className="max-w-xl text-sm leading-7 text-[var(--radar-muted)]">
              This table is your actual risk footprint: notional, leverage, unrealized PnL, and liquidation buffer at a glance.
            </p>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">
                <tr>
                  {["Symbol", "Side", "Notional", "Leverage", "uPnL", "Liq Buffer"].map((label) => (
                    <th key={label} className="px-3 py-3 font-medium">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {summary.positions.length > 0 ? (
                  summary.positions.map((position) => (
                    <tr key={`${position.symbol}-${position.position_id}`} className="border-t border-[color:var(--radar-line)]">
                      <td className="px-3 py-4 font-medium text-[var(--radar-ink)]">{position.symbol}</td>
                      <td className="px-3 py-4 text-[var(--radar-muted)]">{position.position_side}</td>
                      <td className="px-3 py-4 text-[var(--radar-ink)]">{formatCurrency(position.notional_value)}</td>
                      <td className="px-3 py-4 text-[var(--radar-ink)]">{formatSignedNumber(position.leverage, 2)}x</td>
                      <td className="px-3 py-4 text-[var(--radar-ink)]">{`${position.unrealized_pnl >= 0 ? "+" : ""}${formatCurrency(position.unrealized_pnl)}`}</td>
                      <td className="px-3 py-4 text-[var(--radar-ink)]">
                        {position.liquidation_buffer_pct > 0 ? formatPercent(position.liquidation_buffer_pct) : "n/a"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-4 text-[var(--radar-muted)]" colSpan={6}>
                      No open positions in the latest synced snapshot.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-6">
          <div className="radar-card p-6 sm:p-7">
            <div className="radar-chip">Balances</div>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Margin inventory</h2>
            <div className="mt-5 space-y-3">
              {summary.balances.length > 0 ? (
                summary.balances.map((balance) => (
                  <div key={balance.coin} className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4">
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-[var(--radar-ink)]">{balance.coin}</div>
                      <div className="text-sm text-[var(--radar-muted)]">{formatCurrency(balance.assets)}</div>
                    </div>
                    <div className="mt-3 grid gap-2 text-sm text-[var(--radar-muted)]">
                      <div>Available margin: {formatCurrency(balance.available)}</div>
                      <div>Free: {formatCurrency(balance.free)}</div>
                      <div>Unrealized PnL: {`${balance.unrealized_pnl >= 0 ? "+" : ""}${formatCurrency(balance.unrealized_pnl)}`}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 text-sm text-[var(--radar-muted)]">
                  No account balances available yet.
                </div>
              )}
            </div>
          </div>

          <div className="radar-card p-6 sm:p-7">
            <div className="radar-chip">Open Orders</div>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Working orders</h2>
            <div className="mt-5 space-y-3">
              {summary.orders.length > 0 ? (
                summary.orders.map((order) => (
                  <div key={`${order.order_id}-${order.symbol}`} className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-[var(--radar-ink)]">{order.symbol}</div>
                      <div className="text-sm text-[var(--radar-muted)]">{order.side} · {order.order_type}</div>
                    </div>
                    <div className="mt-3 grid gap-2 text-sm text-[var(--radar-muted)]">
                      <div>Size: {formatCompactNumber(order.size)}</div>
                      <div>Price: {order.price > 0 ? formatCurrency(order.price) : "Market / n/a"}</div>
                      <div>Status: {order.status || "OPEN"}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 text-sm text-[var(--radar-muted)]">
                  No working orders in the latest synced snapshot.
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </AppFrame>
  );
}
