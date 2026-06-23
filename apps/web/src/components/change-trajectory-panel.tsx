"use client";

import { useState } from "react";

import type { MarketChangeMomentumItem, MarketChangeTrajectoryResponse, MarketSessionMomentumCell } from "@/lib/types";

type ChangeTrajectoryPanelProps = {
  trajectory: MarketChangeTrajectoryResponse;
};

function assetName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "");
}

function pairName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "/USDT Perp");
}

function pionexFuturesUrl(symbol: string): string {
  const base = symbol.replace("_USDT_PERP", "");
  return `https://www.pionex.com/en/futures/${base}.PERP_USDT/Bot`;
}

function signed(value: number | null, digits = 2): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)} pts`;
}

function percent(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function optionalPercent(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return percent(value);
}

function sparkline(values: number[]): string {
  if (!values.length) {
    return "Waiting";
  }
  return values.map((value) => `${value > 0 ? "+" : ""}${value.toFixed(1)}`).join("  ");
}

function qualityClass(quality: MarketChangeMomentumItem["data_quality"]): string {
  if (quality === "strong") {
    return "border-emerald-300/25 bg-emerald-400/12 text-emerald-100";
  }
  if (quality === "partial") {
    return "border-amber-300/25 bg-amber-400/12 text-amber-100";
  }
  return "border-rose-300/25 bg-rose-400/12 text-rose-100";
}

function directionClass(direction: MarketSessionMomentumCell["direction"], mode: "improving" | "fading"): string {
  switch (direction) {
    case "up":
      return "border-emerald-300/25 bg-emerald-400/12 text-emerald-100";
    case "down":
      return "border-rose-300/25 bg-rose-400/12 text-rose-100";
    case "flat":
      return "border-amber-300/20 bg-amber-400/10 text-amber-100";
    default:
      return mode === "improving"
        ? "border-emerald-300/12 bg-black/15 text-[var(--radar-muted)]"
        : "border-rose-300/12 bg-black/15 text-[var(--radar-muted)]";
  }
}

function pressureLabel(value: number, samples: number): string {
  if (samples < 2) {
    return "Waiting";
  }
  if (value > 0) {
    return "Buying pressure";
  }
  if (value < 0) {
    return "Selling pressure";
  }
  return "Balanced";
}

function SessionCells({ item, mode }: { item: MarketChangeMomentumItem; mode: "improving" | "fading" }) {
  return (
    <div className="mt-3 grid gap-2 lg:grid-cols-[1fr_1fr_1fr_1.2fr]">
      {item.sessions.map((session) => (
        <div
          className={`rounded-[14px] border p-3 transition hover:-translate-y-0.5 ${directionClass(session.direction, mode)}`}
          key={`${item.symbol}-${mode}-${session.session}`}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold">{session.session}</div>
            <div className="rounded-full bg-black/20 px-2 py-1 text-[10px]">{pressureLabel(session.net_delta, session.samples)}</div>
          </div>
          <div className="mt-2 text-base font-semibold">{signed(session.net_delta)}</div>
          <div className="mt-1 text-[11px] opacity-80">Avg 5m: {signed(session.average_5m_delta)}</div>
          <div className="mt-1 text-[11px] opacity-70">5m moves: {session.samples}</div>
        </div>
      ))}

      <div className="rounded-[14px] border border-[color:var(--radar-line)] bg-black/15 p-3 transition hover:border-[color:var(--radar-line-strong)]">
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">Session Read</div>
        <div className="mt-2 text-xs font-semibold text-[var(--radar-ink)]">Strongest pressure: {item.dominant_session}</div>
        <p className="mt-1 line-clamp-3 text-[11px] leading-5 text-[var(--radar-muted)]">{item.session_summary}</p>
      </div>
    </div>
  );
}

function TrajectoryList({
  items,
  mode,
  title,
}: {
  items: MarketChangeMomentumItem[];
  mode: "improving" | "fading";
  title: string;
}) {
  const columnTone =
    mode === "improving"
      ? "border-emerald-300/25 bg-emerald-400/10"
      : "border-rose-300/25 bg-rose-400/10";
  const chipTone =
    mode === "improving"
      ? "border-emerald-300/25 bg-emerald-400/12 text-emerald-100"
      : "border-rose-300/25 bg-rose-400/12 text-rose-100";
  const cardTone =
    mode === "improving"
      ? "border-emerald-300/18 bg-emerald-400/8 hover:border-emerald-300/35"
      : "border-rose-300/18 bg-rose-400/8 hover:border-rose-300/35";

  return (
    <div className={`rounded-[24px] border p-4 sm:p-5 ${columnTone}`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="radar-chip">{title}</div>
          <p className="mt-2 text-sm text-[var(--radar-muted)]">
            {mode === "improving"
              ? "Coins recovering from negative or near-zero 24H Change readings."
            : "Coins cooling down after previously reaching high 24H Change readings."}
          </p>
        </div>
        <div className={`rounded-full border px-3 py-1 text-xs font-semibold ${chipTone}`}>{items.length}</div>
      </div>

      <div className="space-y-3">
        {items.map((item) => (
          <div
            className={`rounded-[18px] border p-4 transition hover:-translate-y-0.5 sm:p-5 ${cardTone}`}
            key={`${mode}-${item.symbol}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <a
                  className="inline-flex max-w-full items-center gap-2 font-semibold text-[var(--radar-ink)] underline-offset-4 transition hover:text-[var(--radar-sea)] hover:underline focus:outline-none focus-visible:rounded-md focus-visible:ring-2 focus-visible:ring-[var(--radar-sea)]"
                  href={pionexFuturesUrl(item.symbol)}
                  rel="noreferrer"
                  target="_blank"
                  title={`Open ${pairName(item.symbol)} on Pionex`}
                >
                  <span className="truncate">{pairName(item.symbol)}</span>
                  <span aria-hidden="true" className="text-xs opacity-70">open</span>
                </a>
                <div className="mt-1 text-xs text-[var(--radar-muted)]">
                  {assetName(item.symbol)} · samples {item.samples}
                  {item.expected_samples ? `/${item.expected_samples}` : ""}
                </div>
              </div>
              <div className="text-right">
                <div className={item.latest_change_24h >= 0 ? "font-semibold text-emerald-300" : "font-semibold text-rose-300"}>
                  {percent(item.latest_change_24h)}
                </div>
                <div className={mode === "improving" ? "text-xs text-emerald-200" : "text-xs text-rose-200"}>
                  {signed(item.delta_window)}
                </div>
              </div>
            </div>

            <div className="mt-3 grid gap-2 text-xs text-[var(--radar-muted)] sm:grid-cols-3">
              <div>5m change: {signed(item.delta_5m)}</div>
              <div>{mode === "improving" ? "Trough" : "Peak"}: {item.previous_change_24h === null ? "--" : percent(item.previous_change_24h)}</div>
              <div>Strength: {item.strength}</div>
            </div>

            <div className="mt-3 grid gap-2 text-xs text-[var(--radar-muted)] sm:grid-cols-3">
              <div>Snapshot price move: {optionalPercent(item.price_delta_window_pct)}</div>
              <div>Snapshot price 5m: {optionalPercent(item.price_delta_5m_pct)}</div>
              <div>
                <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase ${qualityClass(item.data_quality)}`}>
                  {item.data_quality} data
                </span>
                <span className="ml-2">
                  {item.sample_coverage_pct === null ? "--" : `${item.sample_coverage_pct.toFixed(0)}%`} coverage
                  {item.max_gap_minutes === null ? "" : ` · max gap ${item.max_gap_minutes.toFixed(0)}m`}
                </span>
              </div>
            </div>

            <SessionCells item={item} mode={mode} />

            <div className="mt-3 overflow-x-auto rounded-[14px] border border-white/10 bg-black/20 px-3 py-2 font-mono text-xs leading-6 text-[var(--radar-muted)]">
              {sparkline(item.sparkline)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChangeTrajectoryPanel({ trajectory }: ChangeTrajectoryPanelProps) {
  const [activeTab, setActiveTab] = useState<"improving" | "fading">(
    trajectory.improving.length > 0 || trajectory.fading.length === 0 ? "improving" : "fading",
  );
  const activeItems = activeTab === "improving" ? trajectory.improving : trajectory.fading;
  const activeTitle = activeTab === "improving" ? "Recovery From Negative / Zero" : "Fading From High Readings";
  const tabTone =
    activeTab === "improving"
      ? "border-emerald-300/25 bg-emerald-400/10"
      : "border-rose-300/25 bg-rose-400/10";

  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-5">
        <div className="radar-chip">24H Change Trajectory</div>
        <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
          Improving versus fading market condition
        </h2>
        <p className="mt-2 max-w-5xl text-sm leading-7 text-[var(--radar-muted)]">
          This compares each coin&apos;s current 24H Change against your stored snapshots. Recovery candidates are improving from
          negative or near-zero readings, while fade candidates are cooling down from earlier high readings. Snapshot price context
          helps confirm whether the stored price moved with the 24H Change reading.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 rounded-[22px] border border-[color:var(--radar-line)] bg-black/15 p-2">
        <button
          className={`rounded-[16px] border px-4 py-3 text-left transition hover:-translate-y-0.5 hover:border-emerald-300/35 ${
            activeTab === "improving"
              ? "border-emerald-300/30 bg-emerald-400/14 text-emerald-100"
              : "border-transparent text-[var(--radar-muted)] hover:bg-[var(--radar-panel-soft)] hover:text-[var(--radar-ink)]"
          }`}
          onClick={() => setActiveTab("improving")}
          type="button"
        >
          <span className="block text-xs font-semibold uppercase tracking-[0.16em]">Recovery From Negative / Zero</span>
          <span className="mt-1 block text-sm">{trajectory.improving.length} long-scout candidates</span>
        </button>
        <button
          className={`rounded-[16px] border px-4 py-3 text-left transition hover:-translate-y-0.5 hover:border-rose-300/35 ${
            activeTab === "fading"
              ? "border-rose-300/30 bg-rose-400/14 text-rose-100"
              : "border-transparent text-[var(--radar-muted)] hover:bg-[var(--radar-panel-soft)] hover:text-[var(--radar-ink)]"
          }`}
          onClick={() => setActiveTab("fading")}
          type="button"
        >
          <span className="block text-xs font-semibold uppercase tracking-[0.16em]">Fading From High Readings</span>
          <span className="mt-1 block text-sm">{trajectory.fading.length} short-scout candidates</span>
        </button>
      </div>

      <div className={`rounded-[26px] border p-3 sm:p-4 ${tabTone}`}>
        <TrajectoryList items={activeItems} mode={activeTab} title={activeTitle} />
      </div>

      <p className="mt-4 text-xs leading-6 text-[var(--radar-muted)]">{trajectory.note}</p>
    </section>
  );
}
