import { ScoreEntry } from "@/lib/types";
import { formatCompactNumber, formatPercent, formatPrice, scoreTone } from "@/lib/formatters";

type SignalTableProps = {
  title: string;
  description: string;
  items: ScoreEntry[];
};

function statusClass(label: string): string {
  if (label.includes("Dead")) {
    return "bg-slate-500/12 text-slate-200 ring-1 ring-slate-400/20";
  }
  if (label.includes("Quiet Then Rally") || label.includes("Coiled")) {
    return "bg-cyan-500/12 text-cyan-200 ring-1 ring-cyan-400/20";
  }
  if (label.includes("Buyers Left") || label.includes("Weak Bid")) {
    return "bg-orange-500/12 text-orange-200 ring-1 ring-orange-400/20";
  }
  if (label.includes("Bullish")) {
    return "bg-emerald-500/12 text-emerald-200 ring-1 ring-emerald-400/20";
  }
  if (label.includes("Bearish")) {
    return "bg-rose-500/12 text-rose-200 ring-1 ring-rose-400/20";
  }
  if (label.includes("Active")) {
    return "bg-amber-500/12 text-amber-200 ring-1 ring-amber-400/20";
  }
  return "bg-slate-500/12 text-slate-200 ring-1 ring-slate-400/20";
}

export function SignalTable({ title, description, items }: SignalTableProps) {
  return (
    <section className="radar-card overflow-hidden">
      <div className="border-b border-[color:var(--radar-line)] px-6 py-5 sm:px-8">
        <div className="flex flex-col gap-2">
          <h2 className="text-xl font-semibold tracking-tight text-[var(--radar-ink)]">{title}</h2>
          <p className="text-sm leading-6 text-[var(--radar-muted)]">{description}</p>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="px-6 py-10 text-sm text-[var(--radar-muted)] sm:px-8">
          No contracts qualified for this section on the latest scan.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <caption className="sr-only">{description}</caption>
            <thead className="bg-[var(--radar-panel-soft)] text-left text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">
              <tr>
                <th className="px-6 py-4 sm:px-8" scope="col">Symbol</th>
                <th className="px-6 py-4" scope="col">Price</th>
                <th className="px-6 py-4" scope="col">24h</th>
                <th className="px-6 py-4" scope="col">5m</th>
                <th className="px-6 py-4" scope="col">15m</th>
                <th className="px-6 py-4" scope="col">Volume Spike</th>
                <th className="px-6 py-4" scope="col">Buyer Vol</th>
                <th className="px-6 py-4" scope="col">OI</th>
                <th className="px-6 py-4" scope="col">Scores</th>
                <th className="px-6 py-4 sm:px-8" scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr className="border-t border-[color:var(--radar-line)] align-top" key={item.symbol}>
                  <td className="px-6 py-4 sm:px-8">
                    <div className="space-y-1">
                      <div className="font-semibold text-[var(--radar-ink)]">{item.symbol}</div>
                      <div className="font-mono text-xs text-[var(--radar-muted)]">
                        ATR {item.atr_percent.toFixed(2)}% · Green {Math.round(item.green_candle_ratio * 100)}%
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 font-mono text-[var(--radar-ink)]">{formatPrice(item.price)}</td>
                  <td className="px-6 py-4 font-mono">{formatPercent(item.price_change_24h)}</td>
                  <td className="px-6 py-4 font-mono">{formatPercent(item.price_change_5m)}</td>
                  <td className="px-6 py-4 font-mono">{formatPercent(item.price_change_15m)}</td>
                  <td className="px-6 py-4 font-mono">{item.volume_spike_ratio.toFixed(2)}x</td>
                  <td className="px-6 py-4 font-mono">{Math.round(item.buyer_volume_share * 100)}%</td>
                  <td className="px-6 py-4">
                    <div className="space-y-1 font-mono text-xs text-[var(--radar-muted)]">
                      <div>{formatCompactNumber(item.open_interest)}</div>
                      <div>{formatPercent(item.open_interest_change_pct)}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="grid grid-cols-6 gap-2 text-xs">
                      <div>
                        <div className="text-[var(--radar-muted)]">Act</div>
                        <div className={`font-semibold ${scoreTone(item.activity_score)}`}>{item.activity_score.toFixed(0)}</div>
                      </div>
                      <div>
                        <div className="text-[var(--radar-muted)]">Bull</div>
                        <div className={`font-semibold ${scoreTone(item.bullish_score)}`}>{item.bullish_score.toFixed(0)}</div>
                      </div>
                      <div>
                        <div className="text-[var(--radar-muted)]">Bear</div>
                        <div className={`font-semibold ${scoreTone(item.bearish_score)}`}>{item.bearish_score.toFixed(0)}</div>
                      </div>
                      <div>
                        <div className="text-[var(--radar-muted)]">Bid</div>
                        <div className={`font-semibold ${scoreTone(item.buyer_absence_score)}`}>{item.buyer_absence_score.toFixed(0)}</div>
                      </div>
                      <div>
                        <div className="text-[var(--radar-muted)]">Dead</div>
                        <div className={`font-semibold ${scoreTone(item.dead_market_score)}`}>{item.dead_market_score.toFixed(0)}</div>
                      </div>
                      <div>
                        <div className="text-[var(--radar-muted)]">Q-R</div>
                        <div className={`font-semibold ${scoreTone(item.quiet_rally_score)}`}>{item.quiet_rally_score.toFixed(0)}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 sm:px-8">
                    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${statusClass(item.trend_label)}`}>
                      {item.trend_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
