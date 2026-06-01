import { formatPercent, scoreTone } from "@/lib/formatters";
import { ScoreEntry } from "@/lib/types";

type ReportSignalCardProps = {
  label: string;
  badgeClassName: string;
  barClassName: string;
  coin: ScoreEntry | undefined;
  metric: string;
  value: string;
  score: number;
};

export function ReportSignalCard({
  label,
  badgeClassName,
  barClassName,
  coin,
  metric,
  value,
  score,
}: ReportSignalCardProps) {
  return (
    <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-4 shadow-[0_18px_48px_-38px_rgba(0,0,0,0.72)]">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--radar-muted)]">{label}</div>
          <div className="text-lg font-semibold tracking-tight text-[var(--radar-ink)]">
            {coin?.symbol ?? "No leader"}
          </div>
        </div>
        <div className={`rounded-full px-2.5 py-1 text-xs font-semibold ${badgeClassName}`}>
          <span className={scoreTone(score)}>{score.toFixed(0)}</span>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <div className="h-2 overflow-hidden rounded-full bg-[var(--radar-track)]">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${barClassName}`}
            style={{ width: `${Math.min(Math.max(score, 0), 100)}%` }}
          />
        </div>
        <div className="flex items-center justify-between gap-3 text-sm">
          <span className="text-[var(--radar-muted)]">{metric}</span>
          <span className="font-mono text-[var(--radar-ink)]">{value}</span>
        </div>
        {coin ? (
          <div className="font-mono text-xs text-[var(--radar-muted)]">
            5m {formatPercent(coin.price_change_5m)} · 15m {formatPercent(coin.price_change_15m)}
          </div>
        ) : (
          <div className="text-xs text-[var(--radar-muted)]">This bucket did not produce a lead name.</div>
        )}
      </div>
    </div>
  );
}
