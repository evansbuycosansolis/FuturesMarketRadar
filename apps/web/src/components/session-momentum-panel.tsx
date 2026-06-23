import { formatPrice, formatTimestamp } from "@/lib/formatters";
import type { MarketSessionMomentumCell, MarketSessionMomentumResponse } from "@/lib/types";

type SessionMomentumPanelProps = {
  momentum: MarketSessionMomentumResponse;
};

function assetName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "");
}

function directionClass(direction: MarketSessionMomentumCell["direction"]): string {
  switch (direction) {
    case "up":
      return "border-emerald-400/20 bg-emerald-500/12 text-emerald-200";
    case "down":
      return "border-rose-400/20 bg-rose-500/12 text-rose-200";
    case "flat":
      return "border-amber-400/20 bg-amber-500/12 text-amber-100";
    default:
      return "border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] text-[var(--radar-muted)]";
  }
}

function signed(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)} pts`;
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
  return "Balanced flow";
}

export function SessionMomentumPanel({ momentum }: SessionMomentumPanelProps) {
  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="radar-chip">5-Minute 8H Change Momentum</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
            Session momentum from your own 24H Change history
          </h2>
          <p className="mt-2 max-w-4xl text-sm leading-7 text-[var(--radar-muted)]">
            Asian, London, and New York cells compare each coin&apos;s stored 24H Change readings across 5-minute snapshots.
            This is computed from your database history, not from a new Pionex pull.
          </p>
        </div>
        <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
          <div>Latest: {formatTimestamp(momentum.latest_report_at)}</div>
          <div>Lookback: {momentum.lookback_hours}h · interval: {momentum.interval_minutes}m</div>
        </div>
      </div>

      <div className="grid gap-3">
        {momentum.items.slice(0, 40).map((item) => (
          <div
            className="grid gap-3 rounded-[24px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4 transition hover:-translate-y-0.5 hover:border-[color:var(--radar-line-strong)] hover:bg-[var(--radar-panel-soft)] xl:grid-cols-[180px_1fr_260px]"
            key={item.symbol}
          >
            <div>
              <div className="text-sm font-semibold text-[var(--radar-ink)]">{assetName(item.symbol)}</div>
              <div className="mt-1 text-xs text-[var(--radar-muted)]">{item.symbol}</div>
              <div className="mt-3 text-sm font-semibold text-[var(--radar-ink)]">{formatPrice(item.price)}</div>
              <div className={item.latest_change_24h >= 0 ? "text-xs font-semibold text-emerald-300" : "text-xs font-semibold text-rose-300"}>
                {item.latest_change_24h >= 0 ? "+" : ""}{item.latest_change_24h.toFixed(2)}% 24H
              </div>
            </div>

            <div className="grid gap-2 md:grid-cols-3">
              {item.sessions.map((session) => (
                <div className={`rounded-[18px] border p-3 transition hover:border-[color:var(--radar-sea)] ${directionClass(session.direction)}`} key={`${item.symbol}-${session.session}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold">{session.session}</div>
                    <div className="rounded-full bg-black/20 px-2 py-1 text-[11px]">{pressureLabel(session.net_delta, session.samples)}</div>
                  </div>
                  <div className="mt-3 text-lg font-semibold">{signed(session.net_delta)}</div>
                  <div className="mt-1 text-xs opacity-80">Avg 5m: {signed(session.average_5m_delta)}</div>
                  <div className="mt-1 text-xs opacity-70">Samples: {session.samples}</div>
                </div>
              ))}
            </div>

            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-3">
              <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Session read</div>
              <div className="mt-2 text-sm font-semibold text-[var(--radar-ink)]">Strongest pressure: {item.dominant_session}</div>
              <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">{item.summary}</p>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-4 text-xs leading-6 text-[var(--radar-muted)]">{momentum.note}</p>
    </section>
  );
}
