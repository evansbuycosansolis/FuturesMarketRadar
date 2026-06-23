import { AppFrame } from "@/components/app-frame";
import { ExchangeStatusPanel } from "@/components/exchange-status-panel";
import { MarketIntelligencePanel } from "@/components/market-intelligence-panel";
import { MarketTradingClock } from "@/components/market-trading-clock";
import { RunScanButton } from "@/components/run-scan-button";
import { ScoreBreakdownCard } from "@/components/score-breakdown-card";
import { SignalTable } from "@/components/signal-table";
import { formatCompactNumber, formatPercent, formatTimestamp } from "@/lib/formatters";
import { getMarketOverview, getMarketQuality, probeBackend } from "@/lib/api";
import { pionexFuturesUrl } from "@/lib/links";

function metricValueClass(value: string): string {
  const hasLongToken = value.split(/\s+/).some((part) => part.length >= 12);

  if (hasLongToken) {
    return "text-[clamp(1.7rem,1.9vw,2.45rem)] leading-[1.02] break-all";
  }
  if (value.length >= 18) {
    return "text-[clamp(1.85rem,2vw,2.55rem)] leading-[1.06] break-words";
  }
  return "text-3xl sm:text-[2.15rem] leading-[1.05]";
}

function metricCard(label: string, value: string, detail: string, href?: string) {
  const valueClass = `mt-3 min-w-0 font-semibold tracking-tight ${metricValueClass(value)}`;

  return (
    <div className="radar-card min-w-0 p-5 sm:p-6">
      <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
      {href ? (
        <a
          className={`${valueClass} inline-flex max-w-full items-center gap-2 text-[var(--radar-ink)] underline-offset-4 transition hover:text-[var(--radar-sea)] hover:underline focus:outline-none focus-visible:rounded-md focus-visible:ring-2 focus-visible:ring-[var(--radar-sea)]`}
          href={href}
          rel="noreferrer"
          target="_blank"
          title={`Open ${value} on Pionex`}
        >
          <span className="truncate">{value}</span>
          <span className="text-xs opacity-70">open</span>
        </a>
      ) : (
        <div className={`${valueClass} text-[var(--radar-ink)]`}>{value}</div>
      )}
      <div className="mt-2 break-words text-sm text-[var(--radar-muted)]">{detail}</div>
    </div>
  );
}

function minutesSince(timestamp: string | null): number | null {
  if (!timestamp) {
    return null;
  }

  const parsed = new Date(timestamp).getTime();
  if (Number.isNaN(parsed)) {
    return null;
  }

  return (Date.now() - parsed) / 60000;
}

function freshnessDetail(ageMinutes: number | null, source: string): string {
  if (ageMinutes === null) {
    return `${source} has not produced a timestamp yet.`;
  }

  if (ageMinutes < 1) {
    return `${source} updated less than a minute ago.`;
  }

  return `${source} updated ${ageMinutes.toFixed(1)} minutes ago.`;
}

export async function DashboardPage() {
  const backend = await probeBackend();

  if (!backend.ok) {
    return (
      <AppFrame
        current="dashboard"
        title="Scan futures flow every five minutes without handing trade decisions to a black box."
        subtitle="The frontend is up, but it cannot reach the FastAPI backend yet."
        actions={<RunScanButton />}
      >
        <section className="radar-card p-6 sm:p-8">
          <div className="space-y-4">
            <div className="radar-chip">Backend Unreachable</div>
            <h2 className="text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
              The dashboard could not connect to the API.
            </h2>
            <p className="text-sm leading-7 text-[var(--radar-muted)]">
              It tried <span className="font-mono text-[var(--radar-ink)]">{backend.baseUrl}</span> and got:
              {" "}
              <span className="font-mono text-[var(--radar-ink)]">{backend.error}</span>
            </p>
            <div className="rounded-[24px] border border-[color:rgba(46,183,154,0.18)] bg-[var(--radar-mint-soft)] p-5 text-sm leading-7 text-[var(--radar-ink)]">
              Start the FastAPI server on the same port configured in <span className="font-mono">apps/web/.env.local</span>.
              If port <span className="font-mono">8000</span> is already taken on your machine, run the API on
              {" "}
              <span className="font-mono">8010</span> and update both
              {" "}
              <span className="font-mono">API_BASE_URL</span> and <span className="font-mono">NEXT_PUBLIC_API_BASE_URL</span>.
            </div>
          </div>
        </section>
      </AppFrame>
    );
  }

  const { health, latestReport } = backend;
  const [marketOverview, marketQuality] = await Promise.all([
    getMarketOverview().catch(() => null),
    getMarketQuality().catch(() => null),
  ]);
  const scanAgeMinutes = minutesSince(health.last_run_completed_at);
  const reportTimestamp = latestReport?.created_at ?? health.latest_report_at;
  const reportAgeMinutes = minutesSince(reportTimestamp);
  const reportIsCurrent = reportAgeMinutes !== null && reportAgeMinutes <= 15;
  const marketIsCurrent =
    marketOverview !== null &&
    marketOverview.latest_age_minutes !== null &&
    !marketOverview.is_stale &&
    marketOverview.latest_age_minutes <= 15;
  const currentGainer = marketOverview?.gainers[0] ?? (reportIsCurrent ? latestReport?.top_bullish[0] : null) ?? null;
  const currentLoser = marketOverview?.losers[0] ?? (reportIsCurrent ? latestReport?.top_bearish[0] : null) ?? null;
  const leadCoin = reportIsCurrent
    ? latestReport?.top_quiet_rallies[0] ??
      latestReport?.top_buyers_left[0] ??
      latestReport?.top_active[0] ??
      latestReport?.top_bullish[0] ??
      latestReport?.top_bearish[0] ??
      null
    : null;

  return (
    <AppFrame
      current="dashboard"
      title="Manage your futures trading from one risk-first command center."
      subtitle="Monitor Pionex now, prepare Binance next, scan live futures flow, and keep execution behind deterministic checks, explicit switches, and a visible kill switch."
      actions={<RunScanButton />}
    >
      <MarketTradingClock>
        <ExchangeStatusPanel compact status={backend.exchangeStatus} />
      </MarketTradingClock>

      <MarketIntelligencePanel summary={backend.marketIntelligence} />

      <section className="grid gap-4 xl:grid-cols-6">
        {metricCard(
          "Tracked Universe",
          formatCompactNumber(health.tracked_symbol_count),
          "Stored futures symbols discovered from Pionex.",
        )}
        {metricCard(
          "Latest Scan",
          formatTimestamp(health.last_run_completed_at),
          health.scheduler_running
            ? freshnessDetail(scanAgeMinutes, "Scanner")
            : "Scheduler is offline.",
        )}
        {metricCard(
          "Top Gainer",
          currentGainer?.symbol ?? "Waiting",
          currentGainer
            ? `${formatPercent(currentGainer.price_change_24h)} over 24h from ${marketOverview?.data_source ?? "latest source"}`
            : "Run the scanner to populate the radar.",
          currentGainer ? pionexFuturesUrl(currentGainer.symbol) : undefined,
        )}
        {metricCard(
          "Top Loser",
          currentLoser?.symbol ?? "Waiting",
          currentLoser
            ? `${formatPercent(currentLoser.price_change_24h)} over 24h from ${marketOverview?.data_source ?? "latest source"}`
            : "Loser rankings appear after the first market snapshot.",
          currentLoser ? pionexFuturesUrl(currentLoser.symbol) : undefined,
        )}
        {metricCard(
          reportIsCurrent ? "Quiet -> Rally" : "Market Quality",
          reportIsCurrent ? latestReport?.top_quiet_rallies[0]?.symbol ?? "Waiting" : marketQuality ? `${Math.round(marketQuality.score)}/100` : "Checking",
          reportIsCurrent && latestReport?.top_quiet_rallies[0]
            ? `${formatPercent(latestReport.top_quiet_rallies[0].price_change_15m)} over 15m after compression`
            : marketQuality
              ? `${marketQuality.status} decision-support inputs from the current snapshot.`
              : "Quality checks are loading.",
          reportIsCurrent && latestReport?.top_quiet_rallies[0]
            ? pionexFuturesUrl(latestReport.top_quiet_rallies[0].symbol)
            : undefined,
        )}
        {metricCard(
          reportIsCurrent ? "Buyers Left" : "Snapshot Coverage",
          reportIsCurrent ? latestReport?.top_buyers_left[0]?.symbol ?? "Waiting" : marketOverview ? String(marketOverview.futures.length) : "Checking",
          reportIsCurrent && latestReport?.top_buyers_left[0]
            ? `${Math.round(latestReport.top_buyers_left[0].buyer_volume_share * 100)}% buyer-side volume`
            : marketOverview
              ? `Current Pionex-board futures ranked from ${marketOverview.data_source}.`
              : "Market coverage is loading.",
          reportIsCurrent && latestReport?.top_buyers_left[0]
            ? pionexFuturesUrl(latestReport.top_buyers_left[0].symbol)
            : undefined,
        )}
      </section>

      {!reportIsCurrent ? (
        <section className="radar-card border-[color:rgba(46,183,154,0.3)] bg-[color:rgba(46,183,154,0.08)] p-6 sm:p-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="radar-chip border-[color:rgba(46,183,154,0.42)] text-[var(--radar-sea)]">
                Current Data Status
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
                Current market data is fresh.
              </h2>
              <p className="max-w-4xl text-sm leading-7 text-[var(--radar-muted)]">
                The live market board snapshot is{" "}
                {marketIsCurrent ? freshnessDetail(marketOverview.latest_age_minutes, "market data") : "not confirmed fresh"}.
                Score-report-only signals are paused until the backend produces a fresh scored report, so this dashboard is
                using the current Pionex-board snapshot as its primary source.
              </p>
            </div>
            <div className="rounded-[20px] border border-[color:rgba(46,183,154,0.32)] bg-[color:rgba(46,183,154,0.1)] px-4 py-3 text-sm text-[var(--radar-ink)]">
              <div>Quality: {marketQuality ? `${marketQuality.status} (${Math.round(marketQuality.score)}/100)` : "Unavailable"}</div>
              <div>Latest snapshot: {formatTimestamp(marketOverview?.latest_report_at ?? null)}</div>
            </div>
          </div>
        </section>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[1.35fr_0.95fr]">
        <div className="radar-card p-6 sm:p-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="radar-chip">Latest 5-Minute Report</div>
              <h2 className="text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
                {reportIsCurrent ? latestReport?.title ?? "No report yet" : "Current market snapshot"}
              </h2>
            </div>
            <div className="rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
              <div>Last completed: {formatTimestamp(health.last_run_completed_at)}</div>
              <div>Scanner running: {health.scanner_running ? "Yes" : "No"}</div>
            </div>
          </div>

          <div className="mt-6 space-y-5">
            <p className="text-sm leading-7 text-[var(--radar-muted)]">
              {reportIsCurrent && latestReport?.summary
                ? latestReport.summary
                : marketOverview
                  ? `Fresh Pionex market-board snapshot is available from ${formatTimestamp(marketOverview.latest_report_at)} with ${marketOverview.futures.length} futures ranked by 24H change. The separate generated score report is stale, so score-based conclusions are paused here.`
                  : latestReport?.summary ??
                "The backend is ready, but it still needs its first scan. Use the Run Now control to seed the SQLite database and generate the opening report."}
            </p>
            <div className="rounded-[24px] border border-[color:rgba(46,183,154,0.18)] bg-[var(--radar-mint-soft)] p-5">
              <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">AI Explanation</div>
              <p className="mt-3 text-sm leading-7 text-[var(--radar-ink)]">
                {reportIsCurrent && latestReport?.ai_commentary
                  ? latestReport.ai_commentary
                  : marketQuality
                    ? `Decision-support quality is ${marketQuality.status} at ${Math.round(marketQuality.score)}/100. ${marketQuality.source}.`
                    : latestReport?.ai_commentary ??
                  "Once scans are running, this panel summarizes the strongest active, bullish, and bearish contracts with a plain-English risk note."}
              </p>
            </div>
          </div>
        </div>

        {reportIsCurrent ? (
          <ScoreBreakdownCard coin={leadCoin} />
        ) : (
          <div className="radar-card p-6 sm:p-8">
            <div className="radar-chip">Current Snapshot</div>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
              {marketIsCurrent ? "Market board is current" : "Market board needs confirmation"}
            </h2>
            <div className="mt-6 space-y-4 text-sm leading-7 text-[var(--radar-muted)]">
              <p>{marketOverview?.data_source ?? "Market source unavailable."}</p>
              <p>
                {marketQuality
                  ? marketQuality.checks.map((check) => `${check.name}: ${check.status}`).join(" · ")
                  : "Quality checks unavailable."}
              </p>
            </div>
          </div>
        )}
      </section>

      {marketOverview ? (
        <SignalTable
          title="Current Pionex Futures Snapshot"
          description="Fresh market-board rows ranked by current 24H change. This is the most current dashboard source right now."
          items={marketOverview.futures.slice(0, 20)}
        />
      ) : null}

      {reportIsCurrent ? (
        <>
      <SignalTable
        title="Top Active Futures"
        description="Contracts with the strongest combination of sudden volume, short-term movement, volatility, and open-interest change."
        items={latestReport?.top_active ?? []}
      />
      <SignalTable
        title="Suddenly Bullish Futures"
        description="Names with aligned 5m and 15m momentum, price above short EMAs, and rising participation."
        items={latestReport?.top_bullish ?? []}
      />
      <SignalTable
        title="Suddenly Bearish Futures"
        description="Names with synchronized downside momentum, weak structure versus EMAs, and elevated sell-side participation."
        items={latestReport?.top_bearish ?? []}
      />
      <SignalTable
        title="Quiet Then Rally"
        description="Contracts that spent the prior window dead and compressed, then woke up with ignition volume, repeated spike legs, and bullish follow-through instead of a one-candle fakeout."
        items={latestReport?.top_quiet_rallies ?? []}
      />
      <SignalTable
        title="Top Futures Where Buyers Left"
        description="Contracts where green-candle participation is thin, closes keep landing near the lows, and weak-bid behavior is showing up even without order-book data."
        items={latestReport?.top_buyers_left ?? []}
      />
      <SignalTable
        title="Dead-Market / Thin Participation"
        description="Contracts with compressed range, flat open interest, weak movement, and low relative activity so you can separate quiet tape from true sell pressure."
        items={latestReport?.top_dead_markets ?? []}
      />
      <SignalTable
        title="Watchlist"
        description="Moderate-strength names worth monitoring for confirmation on the next scan instead of chasing immediately."
        items={latestReport?.watchlist ?? []}
      />
        </>
      ) : null}
    </AppFrame>
  );
}
