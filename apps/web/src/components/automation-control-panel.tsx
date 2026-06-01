"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import {
  engageKillSwitch,
  reconcileAutomationNow,
  releaseKillSwitch,
  runAutomationWatchdogNow,
  updateAutomationMode,
} from "@/lib/api";
import { formatTimestamp } from "@/lib/formatters";
import { AutomationSummary, AutomationMode } from "@/lib/types";

type AutomationControlPanelProps = {
  summary: AutomationSummary;
};

const modeCopy: Record<AutomationMode, { label: string; detail: string }> = {
  paper: {
    label: "Paper",
    detail: "Signals are scored and journaled, but nothing is sent to Pionex.",
  },
  supervised_live: {
    label: "Supervised Live",
    detail: "Signals queue for approval after they pass the deterministic risk gate.",
  },
  unattended_live: {
    label: "Unattended Live",
    detail: "Passing signals can auto-enter as long as the circuit breakers stay clear.",
  },
};

export function AutomationControlPanel({ summary }: AutomationControlPanelProps) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function runAction(action: () => Promise<{ message: string }>) {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await action();
        setMessage(response.message);
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Automation action failed.");
      }
    });
  }

  return (
    <section className="radar-card p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">Automation Control</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Choose how much authority the app has</h2>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--radar-muted)]">
            The mode decides whether signals stay as paper notes, queue for approval, or execute on their own after the full risk gate.
          </p>
        </div>
        <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm leading-7 text-[var(--radar-muted)]">
          <div>Last webhook: {formatTimestamp(summary.control.last_webhook_at)}</div>
          <div>Last reconcile: {formatTimestamp(summary.control.last_reconciliation_at)}</div>
          <div>Last watchdog: {formatTimestamp(summary.control.last_watchdog_at)}</div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {(Object.keys(modeCopy) as AutomationMode[]).map((mode) => {
          const active = summary.control.mode === mode;
          return (
            <button
              key={mode}
              className={`rounded-[22px] border p-5 text-left transition ${
                active
                  ? "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)]"
                  : "border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] hover:border-[color:var(--radar-sea)]"
              }`}
              disabled={isPending}
              onClick={() => runAction(() => updateAutomationMode(mode).then(() => ({ message: `${modeCopy[mode].label} mode enabled.` })))}
              type="button"
            >
              <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{active ? "Current Mode" : "Available Mode"}</div>
              <div className="mt-3 text-xl font-semibold tracking-tight text-[var(--radar-ink)]">{modeCopy[mode].label}</div>
              <p className="mt-2 text-sm leading-7 text-[var(--radar-muted)]">{modeCopy[mode].detail}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-5">
          <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Kill-Switch</div>
          <h3 className="mt-3 text-xl font-semibold tracking-tight text-[var(--radar-ink)]">
            {summary.control.kill_switch_enabled ? "Hard stop is engaged" : "Hard stop is clear"}
          </h3>
          <p className="mt-2 text-sm leading-7 text-[var(--radar-muted)]">
            When engaged, live orders from this app stay blocked even if the rest of the stack is healthy.
          </p>
          <textarea
            className="mt-4 min-h-24 w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.48)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => setReason(event.target.value)}
            placeholder="Reason for engaging or clearing the kill-switch"
            value={reason}
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              className="inline-flex items-center justify-center rounded-full border border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] px-4 py-2 text-sm font-semibold text-rose-100 transition hover:border-[color:rgba(255,126,115,0.42)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isPending || summary.control.kill_switch_enabled}
              onClick={() => runAction(() => engageKillSwitch(reason))}
              type="button"
            >
              Engage
            </button>
            <button
              className="inline-flex items-center justify-center rounded-full border border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:border-[color:rgba(46,183,154,0.42)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isPending || !summary.control.kill_switch_enabled}
              onClick={() => runAction(() => releaseKillSwitch(reason))}
              type="button"
            >
              Release
            </button>
          </div>
          {summary.control.kill_switch_reason ? (
            <div className="mt-4 rounded-[18px] border border-[color:rgba(255,126,115,0.18)] bg-[rgba(74,23,19,0.28)] px-4 py-3 text-sm leading-7 text-rose-100">
              {summary.control.kill_switch_reason}
            </div>
          ) : null}
        </div>

        <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-5">
          <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Housekeeping</div>
          <h3 className="mt-3 text-xl font-semibold tracking-tight text-[var(--radar-ink)]">Restart-safe maintenance loops</h3>
          <p className="mt-2 text-sm leading-7 text-[var(--radar-muted)]">
            Reconcile checks what the exchange thinks is open after restarts. Watchdog checks staleness, failure streaks, and stream health.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <button
              className="inline-flex items-center justify-center rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sea)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isPending}
              onClick={() => runAction(reconcileAutomationNow)}
              type="button"
            >
              Run Reconcile
            </button>
            <button
              className="inline-flex items-center justify-center rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sea)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isPending}
              onClick={() => runAction(runAutomationWatchdogNow)}
              type="button"
            >
              Run Watchdog
            </button>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              ["Failure Streak", `${summary.control.consecutive_failures}`],
              ["Pending Approvals", `${summary.pending_approval_count}`],
              ["Private Stream", summary.private_stream_connected ? "Connected" : "Idle / Down"],
              ["Public Stream", summary.public_stream_connected ? "Connected" : "Idle / Down"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.48)] p-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
                <div className="mt-2 text-lg font-semibold text-[var(--radar-ink)]">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {message ? <p className="mt-4 text-sm leading-7 text-[var(--radar-muted)]">{message}</p> : null}
    </section>
  );
}
