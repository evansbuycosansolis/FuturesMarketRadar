import { formatTimestamp } from "@/lib/formatters";
import type { MarketQualityCheck, MarketQualityResponse } from "@/lib/types";

type MarketQualityPanelProps = {
  quality: MarketQualityResponse;
};

function statusTone(status: MarketQualityResponse["status"] | MarketQualityCheck["status"]): string {
  switch (status) {
    case "healthy":
    case "pass":
      return "border-emerald-300/25 bg-emerald-400/10 text-emerald-100";
    case "degraded":
    case "warn":
      return "border-amber-300/25 bg-amber-400/10 text-amber-100";
    default:
      return "border-rose-300/25 bg-rose-400/10 text-rose-100";
  }
}

function statusLabel(status: string): string {
  return status.replace("_", " ").toUpperCase();
}

export function MarketQualityPanel({ quality }: MarketQualityPanelProps) {
  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="radar-chip">Decision Support Quality</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Reliability and data health</h2>
          <p className="mt-2 max-w-5xl text-sm leading-7 text-[var(--radar-muted)]">
            Shows whether the market dashboard is fresh, covered, and safe to use as decision support. This does not certify any trade idea.
          </p>
        </div>
        <div className={`rounded-[18px] border px-4 py-3 text-sm ${statusTone(quality.status)}`}>
          <div className="text-xs font-semibold uppercase tracking-[0.14em]">System status</div>
          <div className="mt-1 text-2xl font-semibold">{statusLabel(quality.status)}</div>
          <div className="mt-1 opacity-80">Quality score: {quality.score.toFixed(0)}/100</div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {quality.checks.map((check) => (
          <div className={`rounded-[18px] border p-4 transition hover:-translate-y-0.5 ${statusTone(check.status)}`} key={check.name}>
            <div className="flex items-start justify-between gap-3">
              <div className="font-semibold text-[var(--radar-ink)]">{check.name}</div>
              <span className="rounded-full bg-black/20 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]">
                {check.status}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 opacity-85">{check.detail}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4">
        <div className="grid gap-3 text-sm text-[var(--radar-muted)] lg:grid-cols-[1fr_auto]">
          <div>
            <span className="font-semibold text-[var(--radar-ink)]">Sources: </span>
            {quality.source}
          </div>
          <div>Latest: {formatTimestamp(quality.latest_report_at)}</div>
        </div>
        <div className="mt-3 grid gap-2 text-xs leading-5 text-[var(--radar-muted)] lg:grid-cols-2">
          {quality.caveats.map((caveat) => (
            <div className="rounded-[12px] border border-white/10 bg-black/15 px-3 py-2" key={caveat}>
              {caveat}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
