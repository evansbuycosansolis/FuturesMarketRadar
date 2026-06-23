import type { ExchangeStatusResponse } from "@/lib/types";

function modeTone(mode: string): string {
  switch (mode) {
    case "live_enabled":
      return "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] text-rose-100";
    case "read_only":
      return "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] text-emerald-100";
    case "needs_keys":
      return "border-[color:rgba(244,173,61,0.24)] bg-[rgba(80,54,15,0.34)] text-amber-100";
    default:
      return "border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] text-[var(--radar-muted)]";
  }
}

function modeLabel(mode: string): string {
  return mode.replaceAll("_", " ");
}

type ExchangeStatusPanelProps = {
  status: ExchangeStatusResponse;
  compact?: boolean;
};

export function ExchangeStatusPanel({ status, compact = false }: ExchangeStatusPanelProps) {
  if (compact) {
    return (
      <div className="rounded-[22px] border border-[color:var(--radar-line)] bg-black/15 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="radar-chip">Exchange Control</div>
            <div className="mt-2 text-sm font-semibold text-[var(--radar-ink)]">Personal trading connections</div>
          </div>
          <span className={`inline-flex rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${modeTone(status.global_trading_enabled ? "live_enabled" : "guardrail")}`}>
            {status.global_trading_enabled ? "Live switch on" : "Live switch off"}
          </span>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {status.exchanges.map((exchange) => (
            <article
              className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4 transition hover:border-[color:var(--radar-line-strong)]"
              key={exchange.exchange}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold tracking-tight text-[var(--radar-ink)]">{exchange.label}</h3>
                  <p className="mt-1 break-all font-mono text-[10px] text-[var(--radar-muted)]">{exchange.base_url}</p>
                </div>
                <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${modeTone(exchange.mode)}`}>
                  {modeLabel(exchange.mode)}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                {[
                  ["Enabled", exchange.enabled ? "Yes" : "No"],
                  ["Keys", exchange.configured ? "Ready" : "Missing"],
                  ["Execution", exchange.execution_available ? "Ready" : "Locked"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-[12px] border border-[color:var(--radar-line)] bg-black/15 p-2">
                    <div className="text-[9px] uppercase tracking-[0.12em] text-[var(--radar-muted)]">{label}</div>
                    <div className="mt-1 font-semibold text-[var(--radar-ink)]">{value}</div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    );
  }

  return (
    <section className="radar-card p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">Exchange Control</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
            Personal trading connections
          </h2>
        </div>
        <span className={`inline-flex rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${modeTone(status.global_trading_enabled ? "live_enabled" : "guardrail")}`}>
          {status.global_trading_enabled ? "Global live switch on" : "Global live switch off"}
        </span>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {status.exchanges.map((exchange) => (
          <article key={exchange.exchange} className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-lg font-semibold tracking-tight text-[var(--radar-ink)]">{exchange.label}</h3>
                <p className="mt-2 break-all font-mono text-xs text-[var(--radar-muted)]">{exchange.base_url}</p>
              </div>
              <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${modeTone(exchange.mode)}`}>
                {modeLabel(exchange.mode)}
              </span>
            </div>

            <div className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
              {[
                ["Enabled", exchange.enabled ? "Yes" : "No"],
                ["Keys", exchange.configured ? "Ready" : "Missing"],
                ["Execution", exchange.execution_available ? "Ready" : "Locked"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(7,17,15,0.36)] p-3">
                  <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
                  <div className="mt-2 font-semibold text-[var(--radar-ink)]">{value}</div>
                </div>
              ))}
            </div>

            <p className="mt-4 text-sm leading-6 text-[var(--radar-muted)]">{exchange.message}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
