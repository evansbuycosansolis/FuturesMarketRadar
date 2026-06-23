import { formatPrice, formatTimestamp } from "@/lib/formatters";
import { pionexFuturesUrl } from "@/lib/links";
import type { FuturesAnomaly, FuturesAnomalyResponse } from "@/lib/types";

type FuturesAnomalyPanelProps = {
  data: FuturesAnomalyResponse;
};

function pairName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "/USDT Perp");
}

function signedPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function directionTone(direction: FuturesAnomaly["direction"]): string {
  return direction === "breakout"
    ? "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"
    : "border-rose-300/25 bg-rose-400/10 text-rose-100";
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] border border-white/10 bg-black/15 px-3 py-2 transition hover:border-[color:var(--radar-line-strong)]">
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">{label}</div>
      <div className="mt-1 text-sm font-semibold text-[var(--radar-ink)]">{value}</div>
    </div>
  );
}

function AnomalyCard({ item }: { item: FuturesAnomaly }) {
  return (
    <article className={`rounded-[22px] border p-4 transition hover:-translate-y-0.5 ${directionTone(item.direction)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <a
            className="inline-flex max-w-full items-center gap-2 text-lg font-semibold text-[var(--radar-ink)] underline-offset-4 transition hover:text-[var(--radar-sea)] hover:underline focus:outline-none focus-visible:rounded-md focus-visible:ring-2 focus-visible:ring-[var(--radar-sea)]"
            href={pionexFuturesUrl(item.symbol)}
            rel="noreferrer"
            target="_blank"
            title={`Open ${pairName(item.symbol)} on Pionex`}
          >
            <span className="truncate">{pairName(item.symbol)}</span>
            <span aria-hidden="true" className="text-xs opacity-70">open</span>
          </a>
          <div className="mt-1 text-xs uppercase tracking-[0.14em] opacity-80">
            {item.direction === "breakout" ? "Breakout anomaly" : "Breakdown anomaly"}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold">{item.score.toFixed(0)}</div>
          <div className="text-[11px] uppercase tracking-[0.14em] opacity-75">Composite score</div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {item.reason_tags.map((tag) => (
          <span className="rounded-full border border-white/10 bg-black/20 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em]" key={tag}>
            {tag}
          </span>
        ))}
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Current Price" value={formatPrice(item.current_price)} />
        <Metric label="5m Move" value={signedPercent(item.ret_5m)} />
        <Metric label="15m Move" value={signedPercent(item.ret_15m)} />
        <Metric label="Z Move" value={`${item.z_move_5m.toFixed(2)}σ`} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Volume Ratio" value={`${item.volume_ratio_1m.toFixed(2)}x`} />
        <Metric label="Acceleration" value={`${item.accel_score.toFixed(2)}σ`} />
        <Metric label="24H Position" value={`${(item.range_position_24h * 100).toFixed(0)}%`} />
        <Metric label="Isolation" value={`${item.isolation_bonus.toFixed(2)}x`} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="OI Change" value={signedPercent(item.open_interest_change_pct)} />
        <Metric label="Liquidity" value={`${(item.liquidity_score * 100).toFixed(0)}%`} />
        <Metric label="Wick Signal" value={item.wick_signal > 0 ? "Yes" : "No"} />
        <Metric label="Detected" value={formatTimestamp(item.timestamp)} />
      </div>
    </article>
  );
}

function AnomalyColumn({ title, items }: { title: string; items: FuturesAnomaly[] }) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--radar-ink)]">{title}</h3>
        <span className="rounded-full border border-[color:var(--radar-line)] px-3 py-1 text-xs text-[var(--radar-muted)]">
          {items.length}
        </span>
      </div>
      {items.length > 0 ? (
        <div className="space-y-3">
          {items.map((item) => (
            <AnomalyCard item={item} key={`${item.symbol}-${item.direction}-${item.timestamp}`} />
          ))}
        </div>
      ) : (
        <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-5">
          <div className="font-semibold text-[var(--radar-ink)]">No candidates right now.</div>
          <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">
            No symbol passed the volatility-normalized movement, volume, acceleration, and liquidity filters.
          </p>
        </div>
      )}
    </div>
  );
}

export function FuturesAnomalyPanel({ data }: FuturesAnomalyPanelProps) {
  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="radar-chip">Real-Time Futures Anomaly Scoring</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
            Volatility-normalized breakout and breakdown radar
          </h2>
          <p className="mt-2 max-w-5xl text-sm leading-7 text-[var(--radar-muted)]">
            Ranks unusual movers by normalized price shock, volume expansion, acceleration, futures stress proxies, liquidity,
            and BTC/ETH isolation. This is an anomaly detector, not a buy/sell signal.
          </p>
        </div>
        <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
          <div>Cadence: {data.interval_seconds}s source snapshots</div>
          <div>Lookback: {data.lookback_hours}h</div>
          <div>Latest: {formatTimestamp(data.latest_report_at)}</div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <AnomalyColumn items={data.top_breakouts} title="Top Breakouts" />
        <AnomalyColumn items={data.top_breakdowns} title="Top Breakdowns" />
      </div>

      <p className="mt-4 text-xs leading-6 text-[var(--radar-muted)]">
        Source: {data.source}. {data.note}
      </p>
    </section>
  );
}
