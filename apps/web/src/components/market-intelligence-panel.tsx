import { formatSignedNumber, formatTimestamp } from "@/lib/formatters";
import type { MarketIntelligenceSummary } from "@/lib/types";

type MarketIntelligencePanelProps = {
  summary: MarketIntelligenceSummary | null;
};

function toneClass(score: number): string {
  if (score >= 0.2) {
    return "text-emerald-300";
  }
  if (score <= -0.2) {
    return "text-rose-300";
  }
  return "text-amber-300";
}

function barStyle(score: number): { width: string; marginLeft: string } {
  const magnitude = Math.min(100, Math.abs(score) * 100);
  if (score >= 0) {
    return { width: `${magnitude / 2}%`, marginLeft: "50%" };
  }
  return { width: `${magnitude / 2}%`, marginLeft: `${50 - magnitude / 2}%` };
}

export function MarketIntelligencePanel({ summary }: MarketIntelligencePanelProps) {
  if (!summary || !summary.latest_run) {
    return (
      <section className="radar-card p-6 sm:p-8">
        <div className="radar-chip">Market Intelligence</div>
        <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Sentiment agent waiting for its first scan</h2>
        <p className="mt-3 text-sm leading-7 text-[var(--radar-muted)]">
          The agent is configured as decision support only. Run the backend intelligence scan once, then it will continue on the scheduled interval.
        </p>
      </section>
    );
  }

  return (
    <section className="radar-card p-6 sm:p-8">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="radar-chip">Market Intelligence</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Internet sentiment, scored every {summary.interval_minutes / 60}h</h2>
          <p className="mt-2 text-sm leading-7 text-[var(--radar-muted)]">{summary.note}</p>
        </div>
        <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
          <div>Latest: {formatTimestamp(summary.latest_run.completed_at)}</div>
          <div>Sources: {summary.latest_run.sources_checked}</div>
          <div>Matched mentions: {summary.latest_run.matched_articles}</div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-4">
        {summary.assets.map((asset) => {
          const style = barStyle(asset.sentiment_score);
          const topSources = Object.entries(asset.source_counts).slice(0, 3);
          return (
            <div key={asset.asset} className="rounded-[8px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-[var(--radar-ink)]">{asset.asset}</div>
                  <div className={`mt-1 text-2xl font-semibold ${toneClass(asset.sentiment_score)}`}>{formatSignedNumber(asset.sentiment_score, 2)}</div>
                </div>
                <div className={`text-right text-xs font-semibold ${toneClass(asset.sentiment_score)}`}>
                  {asset.label}
                  <div className="mt-1 text-[var(--radar-muted)]">{asset.article_count} mentions</div>
                </div>
              </div>

              <div className="relative mt-4 h-2 rounded-full bg-[rgba(238,248,244,0.12)]">
                <div className="absolute left-1/2 top-[-3px] h-4 w-px bg-[rgba(238,248,244,0.28)]" />
                <div
                  className={`h-2 rounded-full ${asset.sentiment_score >= 0 ? "bg-emerald-400" : "bg-rose-400"}`}
                  style={style}
                />
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-[var(--radar-muted)]">9h MA</div>
                  <div className={toneClass(asset.ma_3_score)}>{formatSignedNumber(asset.ma_3_score, 2)}</div>
                </div>
                <div>
                  <div className="text-[var(--radar-muted)]">24h MA</div>
                  <div className={toneClass(asset.ma_8_score)}>{formatSignedNumber(asset.ma_8_score, 2)}</div>
                </div>
                <div>
                  <div className="text-[var(--radar-muted)]">7d MA</div>
                  <div className={toneClass(asset.ma_56_score)}>{formatSignedNumber(asset.ma_56_score, 2)}</div>
                </div>
              </div>

              <div className="mt-4 text-xs leading-5 text-[var(--radar-muted)]">
                <div>Positive {asset.positive_count} · Neutral {asset.neutral_count} · Negative {asset.negative_count}</div>
                <div>Confidence {(asset.confidence * 100).toFixed(0)}%</div>
                {asset.themes.length > 0 ? <div>Themes: {asset.themes.slice(0, 3).join(", ")}</div> : null}
                {topSources.length > 0 ? <div>Sources: {topSources.map(([name, count]) => `${name} ${count}`).join(", ")}</div> : null}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
