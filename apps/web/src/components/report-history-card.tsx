import { formatPercent, formatTimestamp } from "@/lib/formatters";
import { Report, ScoreEntry } from "@/lib/types";
import { ReportSignalCard } from "@/components/report-signal-card";

type ReportHistoryCardProps = {
  report: Report;
};

type SignalSnapshot = {
  label: string;
  badgeClassName: string;
  barClassName: string;
  coin: ScoreEntry | undefined;
  metric: string;
  value: string;
  score: number;
};

function toSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function signalSnapshots(report: Report): SignalSnapshot[] {
  return [
    {
      label: "Active",
      badgeClassName: "bg-amber-500/12 text-amber-200 ring-1 ring-amber-400/20",
      barClassName: "from-amber-300 via-amber-400 to-orange-500",
      coin: report.top_active[0],
      metric: "Volume spike",
      value: report.top_active[0] ? `${report.top_active[0].volume_spike_ratio.toFixed(2)}x` : "—",
      score: report.top_active[0]?.activity_score ?? 0,
    },
    {
      label: "Bullish",
      badgeClassName: "bg-emerald-500/12 text-emerald-200 ring-1 ring-emerald-400/20",
      barClassName: "from-emerald-300 via-emerald-400 to-teal-500",
      coin: report.top_bullish[0],
      metric: "15m move",
      value: report.top_bullish[0] ? formatPercent(report.top_bullish[0].price_change_15m) : "—",
      score: report.top_bullish[0]?.bullish_score ?? 0,
    },
    {
      label: "Bearish",
      badgeClassName: "bg-rose-500/12 text-rose-200 ring-1 ring-rose-400/20",
      barClassName: "from-rose-300 via-rose-400 to-red-500",
      coin: report.top_bearish[0],
      metric: "15m move",
      value: report.top_bearish[0] ? formatPercent(report.top_bearish[0].price_change_15m) : "—",
      score: report.top_bearish[0]?.bearish_score ?? 0,
    },
    {
      label: "Quiet -> Rally",
      badgeClassName: "bg-cyan-500/12 text-cyan-200 ring-1 ring-cyan-400/20",
      barClassName: "from-cyan-300 via-sky-400 to-teal-500",
      coin: report.top_quiet_rallies[0],
      metric: "15m move",
      value: report.top_quiet_rallies[0] ? formatPercent(report.top_quiet_rallies[0].price_change_15m) : "—",
      score: report.top_quiet_rallies[0]?.quiet_rally_score ?? 0,
    },
    {
      label: "Buyers Left",
      badgeClassName: "bg-orange-500/12 text-orange-200 ring-1 ring-orange-400/20",
      barClassName: "from-orange-300 via-amber-400 to-orange-500",
      coin: report.top_buyers_left[0],
      metric: "Buyer volume",
      value: report.top_buyers_left[0] ? `${Math.round(report.top_buyers_left[0].buyer_volume_share * 100)}%` : "—",
      score: report.top_buyers_left[0]?.buyer_absence_score ?? 0,
    },
    {
      label: "Dead Market",
      badgeClassName: "bg-slate-500/12 text-slate-200 ring-1 ring-slate-400/20",
      barClassName: "from-slate-300 via-slate-400 to-stone-500",
      coin: report.top_dead_markets[0],
      metric: "ATR",
      value: report.top_dead_markets[0] ? `${report.top_dead_markets[0].atr_percent.toFixed(2)}%` : "—",
      score: report.top_dead_markets[0]?.dead_market_score ?? 0,
    },
  ];
}

export function ReportHistoryCard({ report }: ReportHistoryCardProps) {
  const leaders = [
    report.top_active[0]?.symbol,
    report.top_bullish[0]?.symbol,
    report.top_bearish[0]?.symbol,
    report.top_quiet_rallies[0]?.symbol,
  ].filter(Boolean);
  const highlights = toSentences(report.summary).slice(0, 6);
  const aiTakeaways = toSentences(report.ai_commentary).slice(0, 3);
  const snapshots = signalSnapshots(report);

  return (
    <article className="radar-card overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-r from-[rgba(244,173,61,0.12)] via-[rgba(15,126,104,0.08)] to-[rgba(227,91,82,0.12)]" />

      <div className="relative space-y-8 p-6 sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-4xl space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="radar-chip">{report.scan_reason}</span>
              <span className="rounded-full border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-3 py-1 text-xs font-medium text-[var(--radar-muted)]">
                Stored {formatTimestamp(report.created_at)}
              </span>
              <span className="rounded-full border border-[color:var(--radar-line)] bg-[var(--radar-panel)] px-3 py-1 text-xs font-medium text-[var(--radar-muted)]">
                Report #{report.id}
              </span>
            </div>
            <div className="space-y-3">
              <h2 className="text-2xl font-semibold tracking-tight text-[var(--radar-ink)] sm:text-3xl">{report.title}</h2>
              <p className="max-w-3xl text-sm leading-7 text-[var(--radar-muted)] sm:text-base">
                This stored scan has been reorganized into highlights, signal winners, and watchlist names so the tape
                is readable in one pass.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {leaders.length > 0 ? (
                leaders.map((leader, index) => (
                  <span
                    className="rounded-full border border-[color:var(--radar-line)] bg-[var(--radar-panel)] px-3 py-1.5 text-xs font-semibold tracking-[0.08em] text-[var(--radar-ink)]"
                    key={`${report.id}-${leader}-${index}`}
                  >
                    {leader}
                  </span>
                ))
              ) : (
                <span className="text-sm text-[var(--radar-muted)]">No leaders recorded in this report.</span>
              )}
            </div>
          </div>

          <div className="w-full max-w-[340px] rounded-[28px] border border-[color:var(--radar-line)] bg-[linear-gradient(145deg,rgba(18,32,28,0.96),rgba(16,54,46,0.62))] p-5 shadow-[0_22px_70px_-44px_rgba(0,0,0,0.72)]">
            <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">Read First</div>
            <div className="mt-3 text-lg font-semibold tracking-tight text-[var(--radar-ink)]">Quick tape context</div>
            <div className="mt-4 space-y-3 text-sm leading-6 text-[var(--radar-muted)]">
              <div className="flex items-center justify-between gap-3">
                <span>Primary lead</span>
                <span className="font-mono text-[var(--radar-ink)]">{report.top_active[0]?.symbol ?? "Waiting"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Quiet -&gt; rally</span>
                <span className="font-mono text-[var(--radar-ink)]">{report.top_quiet_rallies[0]?.symbol ?? "None"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Watchlist count</span>
                <span className="font-mono text-[var(--radar-ink)]">{report.watchlist.length}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>AI note</span>
                <span className="font-mono text-[var(--radar-ink)]">{aiTakeaways.length > 0 ? "Available" : "Quiet"}</span>
              </div>
            </div>
          </div>
        </div>

        <section className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">Highlights</div>
              <div className="mt-2 text-lg font-semibold tracking-tight text-[var(--radar-ink)]">What changed in this scan</div>
            </div>
            <div className="text-sm text-[var(--radar-muted)]">Converted from the stored report summary</div>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            {highlights.length > 0 ? (
              highlights.map((highlight, index) => (
                <div
                  className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-4 shadow-[0_18px_48px_-38px_rgba(0,0,0,0.72)]"
                  key={`${report.id}-highlight-${index}`}
                >
                  <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">
                    Highlight {String(index + 1).padStart(2, "0")}
                  </div>
                  <p className="mt-3 text-sm leading-7 text-[var(--radar-ink)]">{highlight}</p>
                </div>
              ))
            ) : (
              <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-4 text-sm text-[var(--radar-muted)]">
                This report did not contain summary text.
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">Signal Snapshot</div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {snapshots.map((snapshot) => (
              <ReportSignalCard
                badgeClassName={snapshot.badgeClassName}
                barClassName={snapshot.barClassName}
                coin={snapshot.coin}
                key={`${report.id}-${snapshot.label}`}
                label={snapshot.label}
                metric={snapshot.metric}
                score={snapshot.score}
                value={snapshot.value}
              />
            ))}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[28px] border border-[color:rgba(46,183,154,0.18)] bg-[linear-gradient(145deg,rgba(16,54,46,0.5),rgba(18,32,28,0.94))] p-5 sm:p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">AI Commentary</div>
                <div className="mt-2 text-lg font-semibold tracking-tight text-[var(--radar-ink)]">
                  Plain-English take on the tape
                </div>
              </div>
              <div className="rounded-full border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-3 py-1 text-xs font-medium text-[var(--radar-muted)]">
                {aiTakeaways.length > 0 ? `${aiTakeaways.length} quick takeaways` : "Narrative only"}
              </div>
            </div>
            <p className="mt-4 text-sm leading-7 text-[var(--radar-ink)]">{report.ai_commentary || "No AI commentary stored."}</p>
            {aiTakeaways.length > 0 ? (
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                {aiTakeaways.map((takeaway, index) => (
                  <div className="rounded-[22px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-4 text-sm leading-6 text-[var(--radar-muted)]" key={`${report.id}-ai-${index}`}>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">
                      AI Take {String(index + 1).padStart(2, "0")}
                    </div>
                    <p className="mt-2 text-[var(--radar-ink)]">{takeaway}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="rounded-[28px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">Watchlist</div>
                <div className="mt-2 text-lg font-semibold tracking-tight text-[var(--radar-ink)]">
                  Names to keep on deck
                </div>
              </div>
              <div className="rounded-full bg-[var(--radar-panel-soft)] px-3 py-1 text-xs font-semibold text-[var(--radar-ink)]">
                {report.watchlist.length} names
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {report.watchlist.length > 0 ? (
                report.watchlist.map((coin) => (
                  <div
                    className="rounded-full border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-3 py-2 text-xs font-medium text-[var(--radar-muted)]"
                    key={coin.symbol}
                  >
                    <span className="font-semibold text-[var(--radar-ink)]">{coin.symbol}</span>
                    <span className="ml-2 font-mono">{formatPercent(coin.price_change_15m)}</span>
                  </div>
                ))
              ) : (
                <div className="text-sm leading-7 text-[var(--radar-muted)]">
                  No watchlist names were saved for this report.
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </article>
  );
}
