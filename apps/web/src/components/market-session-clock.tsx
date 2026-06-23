"use client";

import { useEffect, useMemo, useState } from "react";

type SessionState = {
  label: string;
  detail: string;
  isOffSession: boolean;
  nextLabel: string;
};

const sessionFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "full",
  timeStyle: "medium",
});

const utcFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
  timeZoneName: "short",
});

function getSessionState(date: Date): SessionState {
  const day = date.getUTCDay();
  const hour = date.getUTCHours();
  const isWeekend = day === 0 || day === 6;

  if (isWeekend) {
    return {
      label: "Off Session",
      detail: "Weekend liquidity watch",
      isOffSession: true,
      nextLabel: "Asian session resumes at 23:00 UTC on Sunday",
    };
  }

  if (hour >= 23 || hour < 7) {
    return {
      label: "Asian Session",
      detail: "23:00-07:00 UTC early-flow bucket",
      isOffSession: false,
      nextLabel: "London session at 07:00 UTC",
    };
  }

  if (hour >= 7 && hour < 15) {
    return {
      label: "London Session",
      detail: "07:00-15:00 UTC early-flow bucket",
      isOffSession: false,
      nextLabel: "New York session at 15:00 UTC",
    };
  }

  return {
    label: "New York Session",
    detail: "15:00-23:00 UTC early-flow bucket",
    isOffSession: false,
    nextLabel: "Asian session at 23:00 UTC",
  };
}

export function MarketSessionClock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const session = useMemo(() => (now ? getSessionState(now) : null), [now]);

  return (
    <section className="radar-card overflow-hidden p-4 sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="radar-chip">Live Market Clock</div>
          <div className="mt-3 text-xl font-semibold text-[var(--radar-ink)]">
            {now ? sessionFormatter.format(now) : "Syncing market clock..."}
          </div>
          <div className="mt-1 text-sm text-[var(--radar-muted)]">
            UTC reference: {now ? utcFormatter.format(now) : "--"}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[520px]">
          <div
            className={`rounded-[20px] border p-4 transition hover:-translate-y-0.5 ${
              session?.isOffSession
                ? "border-amber-300/25 bg-amber-400/10 text-amber-100"
                : "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"
            }`}
          >
            <div className="text-xs font-semibold uppercase tracking-[0.16em] opacity-75">Current session</div>
            <div className="mt-2 text-lg font-bold">{session?.label ?? "Loading"}</div>
            <div className="mt-1 text-sm opacity-80">{session?.detail ?? "Calculating session window"}</div>
          </div>

          <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 transition hover:-translate-y-0.5 hover:border-[color:var(--radar-line-strong)]">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--radar-muted)]">Next marker</div>
            <div className="mt-2 text-lg font-bold text-[var(--radar-ink)]">
              {session?.isOffSession ? "Off-session mode" : "Session rotation"}
            </div>
            <div className="mt-1 text-sm text-[var(--radar-muted)]">{session?.nextLabel ?? "Waiting for browser clock"}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
