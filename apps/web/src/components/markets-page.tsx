import { MarketStatusPanel } from "@/components/market-status-panel";
import { MarketsTable } from "@/components/markets-table";
import { getMarketOverview, getMarketQuality } from "@/lib/api";
import { formatCompactNumber, formatPrice, formatTimestamp } from "@/lib/formatters";
import { pionexFuturesUrl } from "@/lib/links";
import type { ScoreEntry } from "@/lib/types";

function assetName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "");
}

function tokenInitial(symbol: string): string {
  return assetName(symbol).slice(0, 1);
}

function changeClass(value: number): string {
  if (value > 0) {
    return "text-emerald-300";
  }
  if (value < 0) {
    return "text-rose-300";
  }
  return "text-[var(--radar-muted)]";
}

function formatChange(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function OverviewListCard({
  accent,
  items,
  title,
}: {
  accent: "fire" | "gain" | "loss";
  items: ScoreEntry[];
  title: string;
}) {
  const iconTone = {
    fire: "bg-orange-500 text-white",
    gain: "bg-emerald-500 text-white",
    loss: "bg-rose-500 text-white",
  }[accent];

  return (
    <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.46)] p-4 transition hover:-translate-y-0.5 hover:border-[color:var(--radar-line-strong)] hover:bg-[var(--radar-panel-soft)]">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${iconTone}`}>
            {accent === "fire" ? "▲" : accent === "gain" ? "↗" : "↘"}
          </span>
          <span className="font-semibold text-[var(--radar-ink)]">{title}</span>
        </div>
        <span className="text-xs text-[var(--radar-muted)]">More ›</span>
      </div>

      <div className="space-y-3">
        {items.map((item, index) => (
          <div className="grid grid-cols-[22px_1fr_auto_auto] items-center gap-3 text-sm" key={`${title}-${item.symbol}`}>
            <span className="text-[var(--radar-muted)]">{index + 1}</span>
            <a
              className="flex min-w-0 items-center gap-2 rounded-md underline-offset-4 transition hover:text-[var(--radar-sea)] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--radar-sea)]"
              href={pionexFuturesUrl(item.symbol)}
              rel="noreferrer"
              target="_blank"
              title={`Open ${assetName(item.symbol)} on Pionex`}
            >
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[var(--radar-panel)] text-xs font-bold text-[var(--radar-ink)]">
                {tokenInitial(item.symbol)}
              </span>
              <span className="min-w-0 truncate font-semibold text-[var(--radar-ink)]">{assetName(item.symbol)}</span>
            </a>
            <span className="font-semibold text-[var(--radar-ink)]">{formatPrice(item.price)}</span>
            <span className={`font-semibold ${changeClass(item.price_change_24h)}`}>{formatChange(item.price_change_24h)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MarketDataWarning({ overview }: { overview: Awaited<ReturnType<typeof getMarketOverview>> }) {
  if (!overview.is_stale && !overview.data_warning) {
    return null;
  }

  return (
    <section className="rounded-[24px] border border-amber-300/25 bg-amber-400/10 p-5 text-amber-50">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-100/80">Market Data Warning</div>
          <h2 className="mt-2 text-xl font-semibold">This market board may be stale.</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-amber-100/85">
            {overview.data_warning ?? "The latest market snapshot is older than the expected scan interval."} If Pionex is rate-limiting refreshes,
            use the board as context only until a fresh scan lands.
          </p>
        </div>
        <div className="rounded-[18px] border border-amber-200/20 bg-black/20 px-4 py-3 text-sm">
          <div>Source: {overview.data_source}</div>
          <div>Age: {overview.latest_age_minutes === null ? "unknown" : `${overview.latest_age_minutes.toFixed(1)} min`}</div>
        </div>
      </div>
    </section>
  );
}

export async function MarketsPage() {
  const overview = await getMarketOverview();
  const quality = await getMarketQuality().catch(() => ({
    status: "degraded" as const,
    score: 70,
    latest_report_at: overview.latest_report_at,
    source: "Quality endpoint unavailable; using market overview fallback.",
    checks: [
      {
        name: "Quality endpoint",
        status: "warn" as const,
        detail: "The backend quality endpoint is not reachable yet. Restart the API to enable full quality reporting.",
        metric: null,
        threshold: null,
      },
    ],
    caveats: [
      "Restart the API after this update so the full quality endpoint is available.",
      "Use this dashboard as decision support only, not as automated trade instruction.",
    ],
  }));

  return (
    <div className="radar-shell py-6 sm:py-8 lg:py-10">
      <MarketStatusPanel
        quality={quality}
        title="Market overview for Pionex futures."
        subtitle="Browse the futures universe, spot the strongest movers, and use market context without handing trade execution to the table."
      />
      <MarketDataWarning overview={overview} />

      <section className="radar-card overflow-hidden p-5 sm:p-6">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="radar-chip">Market Overview</div>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Pionex-style futures board</h2>
          </div>
          <div className="text-sm text-[var(--radar-muted)]">Latest scanner snapshot: {formatTimestamp(overview.latest_report_at)}</div>
        </div>
        <div className="grid gap-4 xl:grid-cols-3">
          <OverviewListCard accent="fire" items={overview.coin_cap} title="CoinCap / Volume" />
          <OverviewListCard accent="gain" items={overview.gainers} title="Gainer" />
          <OverviewListCard accent="loss" items={overview.losers} title="Loser" />
        </div>
      </section>

      <section className="radar-card overflow-hidden p-5 sm:p-6">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-5 text-sm font-semibold text-[var(--radar-muted)]">
            {["Picks", "Spot", "Futures", "Leveraged"].map((tab) => (
              <span
                className={`rounded-full px-3 py-2 transition hover:bg-[var(--radar-panel-soft)] hover:text-[var(--radar-ink)] ${tab === "Futures" ? "bg-[var(--radar-panel)] text-[var(--radar-ink)]" : ""}`}
                key={tab}
              >
                {tab}
              </span>
            ))}
          </div>
          <div className="text-sm text-[var(--radar-muted)]">
            {formatCompactNumber(overview.futures.length)} futures ranked by 24h change
          </div>
        </div>
        <MarketsTable items={overview.futures} />
      </section>
    </div>
  );
}
