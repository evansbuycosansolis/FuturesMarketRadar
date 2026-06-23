import { formatPrice, formatTimestamp } from "@/lib/formatters";
import type { SleepingGiantResponse, SleepingGiantSetup } from "@/lib/types";

type SleepingGiantsPanelProps = {
  data: SleepingGiantResponse;
  variant?: "strict" | "recent";
};

function pairName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "/USDT Perp");
}

function pionexFuturesUrl(symbol: string): string {
  const base = symbol.replace("_USDT_PERP", "");
  return `https://www.pionex.com/en/futures/${base}.PERP_USDT/Bot`;
}

function directionTone(direction: SleepingGiantSetup["direction"]): string {
  return direction === "bullish"
    ? "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"
    : "border-rose-300/25 bg-rose-400/10 text-rose-100";
}

function directionLabel(direction: SleepingGiantSetup["direction"]): string {
  return direction === "bullish" ? "Bullish expansion" : "Bearish expansion";
}

function phaseLabel(phase: SleepingGiantSetup["awakening_phase"]): string {
  switch (phase) {
    case "giant_awakening":
      return "Giant awakening";
    case "liquidity_spike":
      return "Liquidity spike";
    case "pressure_building":
      return "Pressure building";
    default:
      return "Watch";
  }
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] border border-white/10 bg-black/15 px-3 py-2 transition hover:border-[color:var(--radar-line-strong)]">
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">{label}</div>
      <div className="mt-1 text-sm font-semibold text-[var(--radar-ink)]">{value}</div>
    </div>
  );
}

function SetupCard({ setup, timeframe, baselineCandles }: { setup: SleepingGiantSetup; timeframe: string; baselineCandles: number }) {
  return (
    <article className={`rounded-[22px] border p-4 transition hover:-translate-y-0.5 ${directionTone(setup.direction)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <a
            className="inline-flex max-w-full items-center gap-2 text-lg font-semibold text-[var(--radar-ink)] underline-offset-4 transition hover:text-[var(--radar-sea)] hover:underline focus:outline-none focus-visible:rounded-md focus-visible:ring-2 focus-visible:ring-[var(--radar-sea)]"
            href={pionexFuturesUrl(setup.symbol)}
            rel="noreferrer"
            target="_blank"
            title={`Open ${pairName(setup.symbol)} on Pionex`}
          >
            <span className="truncate">{pairName(setup.symbol)}</span>
            <span aria-hidden="true" className="text-xs opacity-70">open</span>
          </a>
          <div className="mt-1 text-xs uppercase tracking-[0.14em] opacity-80">
            {phaseLabel(setup.awakening_phase)} · {directionLabel(setup.direction)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold">{setup.score.toFixed(0)}</div>
          <div className="text-[11px] uppercase tracking-[0.14em] opacity-75">Alert score</div>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Height Ratio" value={`${setup.height_ratio.toFixed(2)}x`} />
        <Metric label="Volume Ratio" value={`${setup.volume_ratio.toFixed(2)}x`} />
        <Metric label="Body Strength" value={`${(setup.body_strength * 100).toFixed(0)}%`} />
        <Metric label="2-Candle Pressure" value={`${setup.two_candle_pressure.toFixed(2)}x`} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Compression" value={`${setup.compression_score.toFixed(0)}/100`} />
        <Metric label="Expansion" value={`${setup.breakout_score.toFixed(0)}/100`} />
        <Metric label="Range Burst" value={`${setup.range_burst_score.toFixed(2)}σ`} />
        <Metric label="Volume Burst" value={`${setup.volume_burst_score.toFixed(2)}σ`} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Current Price" value={formatPrice(setup.current_price)} />
        <Metric label="Median Height" value={`${setup.median_candle_height_pct.toFixed(3)}%`} />
        <Metric label="Latest Height" value={`${setup.latest_candle_height_pct.toFixed(3)}%`} />
        <Metric label={`Avg ${timeframe} Size`} value={formatPrice(setup.average_candle_size)} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <Metric label={`Latest ${timeframe} Size`} value={formatPrice(setup.latest_candle_size)} />
        <Metric label="Volume Expansion" value={`${setup.volume_expansion_ratio.toFixed(2)}x`} />
        <Metric label="Detected" value={formatTimestamp(setup.timestamp)} />
      </div>

      <div className="mt-3 rounded-[14px] border border-white/10 bg-black/15 px-3 py-2 text-xs leading-5 text-[var(--radar-muted)]">
        Compared against the prior {baselineCandles} closed {timeframe} candles. Compression window: {setup.compression_candles} candles.
        <span className="block text-[var(--radar-muted)]">{setup.notes[0] ?? "Scanner alert only; not a buy/sell signal."}</span>
      </div>
    </article>
  );
}

export function SleepingGiantsPanel({ data, variant = "strict" }: SleepingGiantsPanelProps) {
  const isRecent = variant === "recent";

  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="radar-chip">Sleeping Giant Awakening</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
            {isRecent ? "Recent Awakening Watchlist" : `Early ${data.timeframe} abnormal expansion scanner`}
          </h2>
          <p className="mt-2 max-w-5xl text-sm leading-7 text-[var(--radar-muted)]">
            {isRecent
              ? `Brings back the broader ${data.timeframe} detector for moves that already started waking up. This can catch newly awakened giants the strict scanner may reject after the first expansion candles appear.`
              : `Looks for futures whose latest two closed ${data.timeframe} candles are both at least 2x the median height of a ${data.baseline_candles}-candle baseline, then confirms with volume, body strength, and burst statistics.`}
          </p>
        </div>
        <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
          <div>{data.timeframe} · {data.baseline_candles} candle baseline</div>
          <div>{isRecent ? "recent awakening mode" : "strict alarm-confirmation mode"}</div>
          <div>{data.lookback_days}d market context</div>
          <div>{data.scanned_symbols} symbols scanned</div>
        </div>
      </div>

      {data.candidates.length > 0 ? (
        <div className="grid gap-3 xl:grid-cols-2">
          {data.candidates.map((setup) => (
            <SetupCard
              key={`${setup.symbol}-${setup.direction}-${setup.timestamp}`}
              setup={setup}
              timeframe={data.timeframe}
              baselineCandles={data.baseline_candles}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-5">
          <div className="text-lg font-semibold text-[var(--radar-ink)]">No awakening candidates right now.</div>
          <p className="mt-2 max-w-4xl text-sm leading-7 text-[var(--radar-muted)]">
            {isRecent
              ? `That means no tracked ${data.timeframe} market structure currently reached the broader recent-awakening trigger with a clear bullish or bearish close.`
              : `That means no tracked ${data.timeframe} market structure currently reached the abnormal burst trigger with a clear bullish or bearish close.
            This can be normal when the market is not showing a fresh awakening setup.`}
          </p>
        </div>
      )}

      <p className="mt-4 text-xs leading-6 text-[var(--radar-muted)]">{data.note}</p>
    </section>
  );
}
