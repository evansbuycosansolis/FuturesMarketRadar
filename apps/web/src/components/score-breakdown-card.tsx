import { ScoreEntry } from "@/lib/types";
import { pionexFuturesUrl } from "@/lib/links";

type ScoreBreakdownCardProps = {
  coin: ScoreEntry | null;
};

export function ScoreBreakdownCard({ coin }: ScoreBreakdownCardProps) {
  return (
    <section className="radar-card p-6 sm:p-8">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight text-[var(--radar-ink)]">Score Breakdown</h2>
        <p className="text-sm leading-6 text-[var(--radar-muted)]">
          Deterministic components behind the current lead contract.
        </p>
      </div>

      {!coin ? (
        <div className="mt-8 text-sm text-[var(--radar-muted)]">Run the scanner once to populate score details.</div>
      ) : (
        <>
          <a
            className="mt-6 inline-flex max-w-full items-center gap-2 rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 font-semibold text-[var(--radar-ink)] underline-offset-4 transition hover:border-[color:var(--radar-line-strong)] hover:text-[var(--radar-sea)] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--radar-sea)]"
            href={pionexFuturesUrl(coin.symbol)}
            rel="noreferrer"
            target="_blank"
            title={`Open ${coin.symbol} on Pionex`}
          >
            <span className="truncate">{coin.symbol}</span>
            <span className="text-xs opacity-70">open</span>
          </a>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            {Object.entries(coin.breakdown).map(([bucket, entries]) => {
              const bucketMax = Math.max(...Object.values(entries), 1);

              return (
                <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel)] p-5" key={bucket}>
                  <div className="text-sm font-semibold capitalize text-[var(--radar-ink)]">{bucket}</div>
                  <div className="mt-4 space-y-3">
                    {Object.entries(entries).map(([label, value]) => (
                      <div className="space-y-1" key={label}>
                        <div className="flex items-center justify-between gap-3 text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">
                          <span>{label.replaceAll("_", " ")}</span>
                          <span className="font-mono text-[var(--radar-ink)]">{value.toFixed(1)}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-[var(--radar-track)]">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-[var(--radar-sea)] to-[var(--radar-sun)]"
                            style={{ width: `${Math.min((value / bucketMax) * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
