import { pionexFuturesUrl } from "@/lib/links";
import { formatPrice, formatTimestamp } from "@/lib/formatters";
import type { OneHourSpike, OneHourSpikeResponse } from "@/lib/types";

function pairName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "/USDT Perp");
}

function toneClass(direction: OneHourSpike["direction"]): string {
  return direction === "bullish"
    ? "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"
    : "border-rose-300/25 bg-rose-400/10 text-rose-100";
}

function compactNumber(value: number): string {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

function SpikeRow({ item }: { item: OneHourSpike }) {
  return (
    <a
      className={`grid gap-3 rounded-[18px] border p-4 transition hover:-translate-y-0.5 hover:border-[color:var(--radar-line-strong)] lg:grid-cols-[1.1fr_0.7fr_0.7fr_0.7fr_0.7fr] ${toneClass(item.direction)}`}
      href={pionexFuturesUrl(item.symbol)}
      rel="noreferrer"
      target="_blank"
      title={`Open ${pairName(item.symbol)} on Pionex`}
    >
      <div>
        <div className="text-lg font-semibold text-[var(--radar-ink)]">{pairName(item.symbol)}</div>
        <div className="mt-1 text-xs uppercase tracking-[0.14em] opacity-75">
          {item.direction} spike · {formatTimestamp(item.timestamp)}
        </div>
      </div>
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-70">Score</div>
        <div className="mt-1 text-xl font-semibold">{item.score.toFixed(0)}</div>
      </div>
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-70">Price move</div>
        <div className="mt-1 text-sm font-semibold">{item.latest_price_change_pct > 0 ? "+" : ""}{item.latest_price_change_pct.toFixed(2)}%</div>
      </div>
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-70">Range / Volume</div>
        <div className="mt-1 text-sm font-semibold">{item.range_ratio.toFixed(2)}x · {item.volume_ratio.toFixed(2)}x</div>
      </div>
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-70">Price / Vol</div>
        <div className="mt-1 text-sm font-semibold">{formatPrice(item.current_price)} · {compactNumber(item.latest_volume)}</div>
      </div>
      <div className="lg:col-span-5">
        <div className="flex flex-wrap gap-2">
          {item.reason_tags.map((tag) => (
            <span className="rounded-full bg-black/20 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] opacity-80" key={tag}>
              {tag}
            </span>
          ))}
        </div>
      </div>
    </a>
  );
}

export function OneHourSpikePanel({ data }: { data: OneHourSpikeResponse }) {
  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="radar-chip">1H Price + Volume Spike Monitor</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
            Sudden 1H abnormal spike list
          </h2>
          <p className="mt-2 max-w-5xl text-sm leading-7 text-[var(--radar-muted)]">
            Simple monitor for the latest closed 1H candle: price range/change must spike and volume must spike versus the recent median baseline.
          </p>
        </div>
        <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
          <div>Refresh cadence: {Math.round(data.interval_seconds / 60)}m</div>
          <div>{data.baseline_candles} candle baseline</div>
          <div>{data.scanned_symbols} symbols scanned</div>
        </div>
      </div>

      {data.candidates.length > 0 ? (
        <div className="space-y-3">
          {data.candidates.map((item) => (
            <SpikeRow item={item} key={`${item.symbol}-${item.timestamp}`} />
          ))}
        </div>
      ) : (
        <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-5">
          <div className="text-lg font-semibold text-[var(--radar-ink)]">No major 1H spike right now.</div>
          <p className="mt-2 max-w-4xl text-sm leading-7 text-[var(--radar-muted)]">
            No tracked symbol currently has both a very abnormal latest 1H price spike and volume spike.
          </p>
        </div>
      )}

      <p className="mt-4 text-xs leading-6 text-[var(--radar-muted)]">
        Source: {data.source}. {data.note}
      </p>
    </section>
  );
}
