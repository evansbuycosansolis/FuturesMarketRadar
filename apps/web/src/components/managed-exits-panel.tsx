"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { disarmManagedExit, runExitAutomationNow } from "@/lib/api";
import { formatPrice, formatTimestamp } from "@/lib/formatters";
import { ManagedExitEvent, ManagedExitPlan } from "@/lib/types";

type ManagedExitsPanelProps = {
  enabled: boolean;
  running: boolean;
  lastRunAt: string | null;
  lastError: string | null;
  privateStreamConnected: boolean;
  publicStreamConnected: boolean;
  privateStreamLastError: string | null;
  publicStreamLastError: string | null;
  plans: ManagedExitPlan[];
  events: ManagedExitEvent[];
};

function statusTone(status: string): string {
  switch (status) {
    case "armed":
      return "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.34)] text-emerald-100";
    case "pending_fill":
      return "border-[color:rgba(108,152,255,0.24)] bg-[rgba(20,30,54,0.4)] text-sky-100";
    case "exit_submitted":
      return "border-[color:rgba(244,173,61,0.24)] bg-[rgba(80,54,15,0.34)] text-amber-100";
    case "closed":
      return "border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] text-[var(--radar-muted)]";
    default:
      return "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] text-rose-100";
  }
}

function eventTone(severity: ManagedExitEvent["severity"]): string {
  switch (severity) {
    case "critical":
      return "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] text-rose-100";
    case "error":
      return "border-[color:rgba(255,126,115,0.16)] bg-[rgba(74,23,19,0.28)] text-rose-100";
    case "warning":
      return "border-[color:rgba(244,173,61,0.24)] bg-[rgba(80,54,15,0.34)] text-amber-100";
    default:
      return "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.34)] text-emerald-100";
  }
}

export function ManagedExitsPanel({
  enabled,
  running,
  lastRunAt,
  lastError,
  privateStreamConnected,
  publicStreamConnected,
  privateStreamLastError,
  publicStreamLastError,
  plans,
  events,
}: ManagedExitsPanelProps) {
  const router = useRouter();
  const [isRunning, startRun] = useTransition();
  const [message, setMessage] = useState("");
  const [disarmingPlanId, setDisarmingPlanId] = useState<number | null>(null);

  function handleRunNow() {
    setMessage("");
    startRun(async () => {
      try {
        const response = await runExitAutomationNow();
        setMessage(`${response.message} Checked ${response.plans_checked} plan(s), triggered ${response.triggered}.`);
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Exit engine run failed.");
      }
    });
  }

  function handleDisarm(planId: number) {
    setMessage("");
    setDisarmingPlanId(planId);
    void (async () => {
      try {
        const response = await disarmManagedExit(planId);
        setMessage(response.message);
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Disarm failed.");
      } finally {
        setDisarmingPlanId(null);
      }
    })();
  }

  return (
    <section className="radar-card p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">Managed Exit Automation</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">App-managed live stop and take-profit supervision</h2>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--radar-muted)]">
            The engine watches armed one-way positions and, if a stop or target is touched, it sends a reduce-only market exit. Every state change is logged below.
          </p>
        </div>
        <button
          className="inline-flex items-center justify-center rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sea)] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={!enabled || isRunning}
          onClick={handleRunNow}
          type="button"
        >
          {isRunning ? "Running..." : "Run Exit Engine"}
        </button>
      </div>

      <div className="mt-4 rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm leading-7 text-[var(--radar-muted)]">
        <div>Automation enabled: {enabled ? "Yes" : "No"}</div>
        <div>Engine running: {running ? "Yes" : "No"}</div>
        <div>Last engine cycle: {formatTimestamp(lastRunAt)}</div>
        <div>Last engine error: {lastError ?? "None"}</div>
        <div>Private stream: {privateStreamConnected ? "Connected" : "Idle / Down"}</div>
        <div>Public stream: {publicStreamConnected ? "Connected" : "Idle / Down"}</div>
        <div>Private stream error: {privateStreamLastError ?? "None"}</div>
        <div>Public stream error: {publicStreamLastError ?? "None"}</div>
      </div>

      {!enabled ? (
        <div className="mt-4 rounded-[20px] border border-[color:rgba(244,173,61,0.24)] bg-[rgba(80,54,15,0.34)] px-4 py-3 text-sm leading-7 text-amber-100">
          Set <span className="font-mono">FMR_ENABLE_EXIT_AUTOMATION=true</span> to arm live stop-loss and take-profit automation.
        </div>
      ) : null}

      {message ? <p className="mt-4 text-sm leading-7 text-[var(--radar-muted)]">{message}</p> : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-4">
          <h3 className="text-lg font-semibold tracking-tight text-[var(--radar-ink)]">Managed plans</h3>
          {plans.length > 0 ? (
            plans.map((plan) => {
              const active = ["pending_fill", "armed", "exit_submitted"].includes(plan.status);
              return (
                <div key={plan.id} className={`rounded-[22px] border p-4 ${statusTone(plan.status)}`}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="text-xs uppercase tracking-[0.16em] opacity-80">{plan.status.replaceAll("_", " ")}</div>
                      <h4 className="mt-2 text-lg font-semibold tracking-tight">{plan.symbol}</h4>
                      <div className="mt-2 text-sm opacity-90">
                        Entry side: {plan.entry_side} · Position side: {plan.position_side}
                      </div>
                    </div>
                    {active ? (
                      <button
                        className="inline-flex items-center justify-center rounded-full border border-current/25 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] transition hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={disarmingPlanId === plan.id}
                        onClick={() => handleDisarm(plan.id)}
                        type="button"
                      >
                        {disarmingPlanId === plan.id ? "Disarming..." : "Disarm"}
                      </button>
                    ) : null}
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {[
                      ["Stop", formatPrice(plan.stop_price)],
                      ["Take Profit", formatPrice(plan.take_profit_price)],
                      ["Live Mark", plan.last_mark_price > 0 ? formatPrice(plan.last_mark_price) : "Waiting"],
                      ["Retries", `${plan.retries_used}`],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-[18px] border border-current/10 bg-[rgba(6,14,12,0.18)] p-3">
                        <div className="text-[11px] uppercase tracking-[0.16em] opacity-75">{label}</div>
                        <div className="mt-2 text-base font-semibold">{value}</div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 grid gap-2 text-sm opacity-90">
                    <div>Created: {formatTimestamp(plan.created_at)}</div>
                    <div>Last checked: {formatTimestamp(plan.last_checked_at)}</div>
                    <div>Trigger reason: {plan.trigger_reason || "Waiting"}</div>
                    <div>Last error: {plan.last_error || "None"}</div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 text-sm text-[var(--radar-muted)]">
              No managed exit plans are stored yet.
            </div>
          )}
        </div>

        <div className="space-y-4">
          <h3 className="text-lg font-semibold tracking-tight text-[var(--radar-ink)]">Recent engine events</h3>
          {events.length > 0 ? (
            events.map((event) => (
              <div key={event.id} className={`rounded-[20px] border p-4 text-sm leading-7 ${eventTone(event.severity)}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs uppercase tracking-[0.16em] opacity-80">{event.event_type.replaceAll("_", " ")}</div>
                  <div className="text-xs opacity-80">{formatTimestamp(event.created_at)}</div>
                </div>
                <div className="mt-2 font-medium">{event.message}</div>
                <div className="mt-2 text-xs opacity-80">Plan #{event.plan_id}</div>
              </div>
            ))
          ) : (
            <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 text-sm text-[var(--radar-muted)]">
              No managed exit events yet.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
