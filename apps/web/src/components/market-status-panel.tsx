"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { formatTimestamp } from "@/lib/formatters";
import type { MarketQualityCheck, MarketQualityResponse } from "@/lib/types";

type MarketStatusPanelProps = {
  quality: MarketQualityResponse;
  title: string;
  subtitle: string;
};

type SessionState = {
  label: string;
  detail: string;
  isOffSession: boolean;
  nextTitle: string;
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
      nextTitle: "Off-session mode",
      nextLabel: "Asian session resumes at 23:00 UTC on Sunday",
    };
  }

  if (hour >= 23 || hour < 7) {
    return {
      label: "Asian Session",
      detail: "23:00-07:00 UTC early-flow bucket",
      isOffSession: false,
      nextTitle: "Session rotation",
      nextLabel: "London session at 07:00 UTC",
    };
  }

  if (hour >= 7 && hour < 15) {
    return {
      label: "London Session",
      detail: "07:00-15:00 UTC early-flow bucket",
      isOffSession: false,
      nextTitle: "Session rotation",
      nextLabel: "New York session at 15:00 UTC",
    };
  }

  return {
    label: "New York Session",
    detail: "15:00-23:00 UTC early-flow bucket",
    isOffSession: false,
    nextTitle: "Session rotation",
    nextLabel: "Asian session at 23:00 UTC",
  };
}

function statusTone(status: MarketQualityResponse["status"] | MarketQualityCheck["status"]): string {
  switch (status) {
    case "healthy":
    case "pass":
      return "border-emerald-300/25 bg-emerald-400/10 text-emerald-100";
    case "degraded":
    case "warn":
      return "border-amber-300/25 bg-amber-400/10 text-amber-100";
    default:
      return "border-rose-300/25 bg-rose-400/10 text-rose-100";
  }
}

function statusLabel(status: string): string {
  return status.replace("_", " ").toUpperCase();
}

function NavLink({ active, href, label }: { active: boolean; href: string; label: string }) {
  return (
    <Link className={active ? "nav-link nav-link-active" : "nav-link"} href={href}>
      {label}
    </Link>
  );
}

export function MarketStatusPanel({ quality, title, subtitle }: MarketStatusPanelProps) {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => setNow(new Date()), 0);
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, []);

  const session = useMemo(() => (now ? getSessionState(now) : null), [now]);

  return (
    <section className="radar-card mb-6 overflow-hidden p-5 sm:p-6">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[var(--radar-sun)] via-[var(--radar-sea)] to-[var(--radar-rose)]" />

      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-3">
          <span className="radar-chip">Personal Trading Copilot</span>
          <nav className="flex flex-wrap items-center gap-2 text-sm font-medium text-[var(--radar-muted)]">
            <NavLink active={false} href="/dashboard" label="Dashboard" />
            <NavLink active href="/markets" label="Markets" />
            <NavLink active={false} href="/scanners" label="Scanners" />
            <NavLink active={false} href="/recovery-fade" label="Recovery/Fade" />
            <NavLink active={false} href="/research" label="Research" />
            <NavLink active={false} href="/reports" label="Reports" />
            <NavLink active={false} href="/risk" label="Risk" />
            <NavLink active={false} href="/tradingview" label="TradingView" />
          </nav>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
          <div>
            <h1 className="max-w-4xl text-3xl font-semibold tracking-tight text-[var(--radar-ink)] sm:text-4xl">
              {title}
            </h1>
            <p className="mt-3 max-w-4xl text-sm leading-7 text-[var(--radar-muted)] sm:text-base">{subtitle}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.46)] p-4">
              <div className="radar-chip">Live Market Clock</div>
              <div className="mt-3 text-base font-semibold text-[var(--radar-ink)]">
                {now ? sessionFormatter.format(now) : "Syncing market clock..."}
              </div>
              <div className="mt-1 text-xs text-[var(--radar-muted)]">UTC reference: {now ? utcFormatter.format(now) : "--"}</div>
            </div>

            <div className={`rounded-[18px] border p-4 ${statusTone(quality.status)}`}>
              <div className="text-xs font-semibold uppercase tracking-[0.14em]">System status</div>
              <div className="mt-1 text-xl font-semibold">{statusLabel(quality.status)}</div>
              <div className="mt-1 text-xs opacity-80">Quality score: {quality.score.toFixed(0)}/100</div>
            </div>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1.25fr]">
          <div
            className={`rounded-[18px] border p-4 ${
              session?.isOffSession
                ? "border-amber-300/25 bg-amber-400/10 text-amber-100"
                : "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"
            }`}
          >
            <div className="text-xs font-semibold uppercase tracking-[0.16em] opacity-75">Current session</div>
            <div className="mt-2 text-lg font-bold">{session?.label ?? "Loading"}</div>
            <div className="mt-1 text-sm opacity-80">{session?.detail ?? "Calculating session window"}</div>
          </div>

          <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--radar-muted)]">Next marker</div>
            <div className="mt-2 text-lg font-bold text-[var(--radar-ink)]">{session?.nextTitle ?? "Session rotation"}</div>
            <div className="mt-1 text-sm text-[var(--radar-muted)]">{session?.nextLabel ?? "Waiting for browser clock"}</div>
          </div>

          <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <div>
                <span className="font-semibold text-[var(--radar-ink)]">Sources: </span>
                <span className="text-[var(--radar-muted)]">{quality.source}</span>
              </div>
              <div className="text-[var(--radar-muted)]">Latest: {formatTimestamp(quality.latest_report_at)}</div>
            </div>
            <p className="mt-2 text-xs leading-5 text-[var(--radar-muted)]">
              Shows whether the market dashboard is fresh, covered, and safe to use as decision support. This does not certify any trade idea.
            </p>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-3">
          {quality.checks.map((check) => (
            <div className={`rounded-[16px] border p-3 ${statusTone(check.status)}`} key={check.name}>
              <div className="flex items-start justify-between gap-3">
                <div className="text-sm font-semibold text-[var(--radar-ink)]">{check.name}</div>
                <span className="rounded-full bg-black/20 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]">
                  {check.status}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 opacity-85">{check.detail}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-2 text-xs leading-5 text-[var(--radar-muted)] lg:grid-cols-2">
          {quality.caveats.map((caveat) => (
            <div className="rounded-[12px] border border-white/10 bg-black/15 px-3 py-2" key={caveat}>
              {caveat}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
