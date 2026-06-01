"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { approveAutomationSignal, rejectAutomationSignal } from "@/lib/api";
import { formatCompactNumber, formatPrice, formatTimestamp } from "@/lib/formatters";
import { AutomationAlert, AutomationSignal, AutomationSummary } from "@/lib/types";

type AutomationSignalPanelProps = {
  summary: AutomationSummary;
};

function alertTone(severity: AutomationAlert["severity"]): string {
  switch (severity) {
    case "critical":
      return "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] text-rose-100";
    case "high":
      return "border-[color:rgba(244,173,61,0.24)] bg-[rgba(80,54,15,0.34)] text-amber-100";
    case "warning":
      return "border-[color:rgba(108,152,255,0.24)] bg-[rgba(20,30,54,0.4)] text-sky-100";
    default:
      return "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] text-emerald-100";
  }
}

function signalTone(status: string): string {
  switch (status) {
    case "executed":
    case "paper_executed":
      return "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.34)]";
    case "pending_approval":
      return "border-[color:rgba(108,152,255,0.24)] bg-[rgba(20,30,54,0.4)]";
    case "blocked":
    case "failed":
      return "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)]";
    default:
      return "border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)]";
  }
}

function signalSummary(signal: AutomationSignal): string {
  const parts: string[] = [];
  if (signal.requested_size > 0) {
    parts.push(`size ${formatCompactNumber(signal.requested_size)}`);
  }
  if (signal.requested_entry_price > 0) {
    parts.push(`entry ${formatPrice(signal.requested_entry_price)}`);
  }
  if (signal.requested_stop_price > 0) {
    parts.push(`stop ${formatPrice(signal.requested_stop_price)}`);
  }
  if (signal.requested_take_profit_price > 0) {
    parts.push(`tp ${formatPrice(signal.requested_take_profit_price)}`);
  }
  return parts.join(" · ") || "No normalized plan fields were stored.";
}

export function AutomationSignalPanel({ summary }: AutomationSignalPanelProps) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function runSignalAction(action: () => Promise<{ message: string }>) {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await action();
        setMessage(response.message);
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Signal action failed.");
      }
    });
  }

  const pendingSignals = summary.recent_signals.filter((signal) => signal.status === "pending_approval");

  return (
    <section className="radar-card p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">Signal Inbox</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Webhook alerts, approvals, and health warnings</h2>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--radar-muted)]">
            TradingView alerts land here first. The app normalizes them, applies deterministic sizing and risk checks, then either stores them, queues them, or blocks them.
          </p>
        </div>
        <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm leading-7 text-[var(--radar-muted)]">
          <div>Webhook secret: {summary.webhook_secret_configured ? "Configured" : "Missing"}</div>
          <div>Websocket monitoring: {summary.websocket_monitoring_enabled ? "Enabled" : "Off"}</div>
          <div>Pending approvals: {summary.pending_approval_count}</div>
        </div>
      </div>

      {message ? <p className="mt-4 text-sm leading-7 text-[var(--radar-muted)]">{message}</p> : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-4">
          <h3 className="text-lg font-semibold tracking-tight text-[var(--radar-ink)]">Active alerts</h3>
          {summary.alerts.length > 0 ? (
            summary.alerts.map((alert) => (
              <div key={alert.id} className={`rounded-[20px] border p-4 text-sm leading-7 ${alertTone(alert.severity)}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs uppercase tracking-[0.16em] opacity-80">{alert.code.replaceAll("_", " ")}</div>
                  <div className="text-xs opacity-80">{formatTimestamp(alert.updated_at)}</div>
                </div>
                <div className="mt-2 font-medium">{alert.message}</div>
              </div>
            ))
          ) : (
            <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 text-sm text-[var(--radar-muted)]">
              No active automation alerts right now.
            </div>
          )}

          <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-5">
            <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Stream Health</div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {[
                ["Private connected", summary.private_stream_connected ? "Yes" : "No"],
                ["Public connected", summary.public_stream_connected ? "Yes" : "No"],
                ["Private stream error", summary.private_stream_last_error ?? "None"],
                ["Public stream error", summary.public_stream_last_error ?? "None"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.48)] p-3">
                  <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
                  <div className="mt-2 text-sm leading-6 text-[var(--radar-ink)]">{value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="text-lg font-semibold tracking-tight text-[var(--radar-ink)]">Recent signals</h3>
          {summary.recent_signals.length > 0 ? (
            summary.recent_signals.map((signal) => (
              <div key={signal.id} className={`rounded-[22px] border p-4 ${signalTone(signal.status)}`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{signal.status.replaceAll("_", " ")}</div>
                    <h4 className="mt-2 text-lg font-semibold tracking-tight text-[var(--radar-ink)]">
                      {signal.symbol} {signal.side}
                    </h4>
                    <div className="mt-1 text-sm text-[var(--radar-muted)]">
                      {signal.strategy_name || "TradingView"} · {signal.mode_at_receipt.replaceAll("_", " ")}
                    </div>
                  </div>
                  <div className="text-right text-sm text-[var(--radar-muted)]">
                    <div>{formatTimestamp(signal.created_at)}</div>
                    <div>{signal.requested_order_type || "MARKET_QTY"}</div>
                  </div>
                </div>

                <div className="mt-4 rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] px-4 py-3 text-sm leading-7 text-[var(--radar-ink)]">
                  {signalSummary(signal)}
                </div>

                <div className="mt-3 text-sm leading-7 text-[var(--radar-muted)]">
                  {signal.status_reason || "No status note recorded."}
                </div>

                {signal.order_id ? (
                  <div className="mt-2 text-sm text-[var(--radar-muted)]">
                    Exchange order: <span className="font-mono text-[var(--radar-ink)]">{signal.order_id}</span>
                  </div>
                ) : null}

                {signal.status === "pending_approval" ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      className="inline-flex items-center justify-center rounded-full border border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:border-[color:rgba(46,183,154,0.42)] disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={isPending}
                      onClick={() => runSignalAction(() => approveAutomationSignal(signal.id))}
                      type="button"
                    >
                      Approve
                    </button>
                    <button
                      className="inline-flex items-center justify-center rounded-full border border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] px-4 py-2 text-sm font-semibold text-rose-100 transition hover:border-[color:rgba(255,126,115,0.42)] disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={isPending}
                      onClick={() => runSignalAction(() => rejectAutomationSignal(signal.id, "Rejected from the Risk tab."))}
                      type="button"
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 text-sm text-[var(--radar-muted)]">
              No webhook signals have been stored yet.
            </div>
          )}
        </div>
      </div>

      {pendingSignals.length > 0 ? (
        <div className="mt-4 rounded-[18px] border border-[color:rgba(108,152,255,0.24)] bg-[rgba(20,30,54,0.4)] px-4 py-3 text-sm leading-7 text-sky-100">
          {pendingSignals.length} signal(s) are waiting for supervisor approval before any live order is sent.
        </div>
      ) : null}
    </section>
  );
}
