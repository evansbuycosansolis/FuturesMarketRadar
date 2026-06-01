import { formatTimestamp } from "@/lib/formatters";
import { Report } from "@/lib/types";

type ReportsOverviewProps = {
  reports: Report[];
};

function overviewCard(label: string, value: string, detail: string) {
  return (
    <div className="rounded-[26px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-5 shadow-[0_20px_60px_-42px_rgba(0,0,0,0.72)]">
      <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">{label}</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-[var(--radar-ink)]">{value}</div>
      <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">{detail}</p>
    </div>
  );
}

export function ReportsOverview({ reports }: ReportsOverviewProps) {
  const latest = reports[0];
  const recentLeaders = reports
    .map((report) => ({
      id: report.id,
      createdAt: report.created_at,
      symbol: report.top_active[0]?.symbol ?? report.top_bullish[0]?.symbol ?? report.top_bearish[0]?.symbol ?? "No lead",
      status:
        report.top_quiet_rallies[0]?.symbol ??
        report.top_buyers_left[0]?.symbol ??
        report.top_dead_markets[0]?.symbol ??
        report.watchlist[0]?.symbol ??
        "Watching",
    }))
    .slice(0, 6);

  return (
    <section className="radar-card overflow-hidden p-6 sm:p-8">
      <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-r from-[rgba(244,173,61,0.16)] via-[rgba(15,126,104,0.08)] to-[rgba(227,91,82,0.14)]" />
      <div className="relative space-y-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <div className="radar-chip">Archive Overview</div>
            <h2 className="text-2xl font-semibold tracking-tight text-[var(--radar-ink)] sm:text-3xl">
              Read every stored scan as a visual tape log.
            </h2>
            <p className="max-w-3xl text-sm leading-7 text-[var(--radar-muted)] sm:text-base">
              The reports tab now shows who led, what regime appeared, and which names stayed on watch without making you
              parse dense text blocks first.
            </p>
          </div>
          <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-5 py-4 text-sm text-[var(--radar-muted)]">
            <div>Latest archive entry</div>
            <div className="mt-1 font-mono text-[var(--radar-ink)]">{formatTimestamp(latest?.created_at ?? null)}</div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-4">
          {overviewCard(
            "Stored Reports",
            String(reports.length),
            "Every completed scan is kept in SQLite so you can study rotation instead of only the latest state.",
          )}
          {overviewCard(
            "Latest Active Lead",
            latest?.top_active[0]?.symbol ?? "Waiting",
            latest?.top_active[0]
              ? `Current activity leader with ${latest.top_active[0].activity_score.toFixed(0)}/100 activity score.`
              : "This populates after the next completed scan.",
          )}
          {overviewCard(
            "Quiet -> Rally Lead",
            latest?.top_quiet_rallies[0]?.symbol ?? "Waiting",
            latest?.top_quiet_rallies[0]
              ? `Most recent compression breakout candidate at ${latest.top_quiet_rallies[0].quiet_rally_score.toFixed(0)}/100.`
              : "No recent stored report has filled the quiet-then-rally bucket yet.",
          )}
          {overviewCard(
            "Latest Watchlist",
            String(latest?.watchlist.length ?? 0),
            "How many names still needed confirmation instead of immediate follow-through on the latest stored report.",
          )}
        </div>

        <div className="rounded-[28px] border border-[color:var(--radar-line)] bg-[linear-gradient(135deg,rgba(20,38,33,0.94),rgba(16,54,46,0.7))] p-5 sm:p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">Leadership Rotation</div>
              <div className="mt-2 text-lg font-semibold tracking-tight text-[var(--radar-ink)]">
                Most recent top leaders at a glance
              </div>
            </div>
            <div className="text-sm text-[var(--radar-muted)]">Newest report on the left</div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            {recentLeaders.map((leader, index) => (
              <div
                className="rounded-[22px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-4 shadow-[0_16px_40px_-34px_rgba(0,0,0,0.72)]"
                key={leader.id}
              >
                <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">
                  Report {String(index + 1).padStart(2, "0")}
                </div>
                <div className="mt-3 text-base font-semibold tracking-tight text-[var(--radar-ink)]">{leader.symbol}</div>
                <div className="mt-1 text-xs text-[var(--radar-muted)]">{formatTimestamp(leader.createdAt)}</div>
                <div className="mt-4 rounded-full bg-[var(--radar-panel-soft)] px-3 py-1 text-xs font-medium text-[var(--radar-ink)]">
                  {leader.status}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
