"use client";

import { FormEvent, useMemo, useState } from "react";

import { researchAsset } from "@/lib/api";
import type { AssetResearchResponse } from "@/lib/types";

function sessionPressure(result: AssetResearchResponse): string {
  const strongest = result.session_support.sessions.find((session) => session.session === result.session_support.dominant_session);
  if (!strongest || strongest.samples < 2) {
    return "Waiting for session data";
  }
  if (strongest.net_delta > 0) {
    return `Buying pressure +${strongest.net_delta.toFixed(2)} pts`;
  }
  if (strongest.net_delta < 0) {
    return `Selling pressure ${strongest.net_delta.toFixed(2)} pts`;
  }
  return "Balanced flow";
}

function sessionTone(session: string): string {
  if (session === "Asian") {
    return "border-cyan-300/25 bg-cyan-400/10 text-cyan-100";
  }
  if (session === "London") {
    return "border-emerald-300/25 bg-emerald-400/10 text-emerald-100";
  }
  if (session === "New York") {
    return "border-violet-300/25 bg-violet-400/10 text-violet-100";
  }
  return "border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] text-[var(--radar-muted)]";
}

function defaultBrief(): string {
  return [
    "Type a crypto, token, or stock symbol above, then run research.",
    "",
    "The output will summarize:",
    "- What the asset is",
    "- Who created or issued it when public summaries can identify that",
    "- Where it lives, such as network, chain, or market context",
    "- When it launched or first appears in public summaries",
    "- Which 8-hour session currently supports it using this app's stored 5-minute 24H Change momentum",
    "- Recent themes, risks, and what to watch next",
    "",
    "Decision support only. It does not place trades.",
  ].join("\n");
}

export function AssetResearchPanel() {
  const [query, setQuery] = useState("BTC");
  const [result, setResult] = useState<AssetResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const brief = useMemo(() => result?.summary_text ?? defaultBrief(), [result]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Enter a symbol or asset name first.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await researchAsset(trimmed);
      setResult(data);
    } catch (researchError) {
      setError(researchError instanceof Error ? researchError.message : "Research request failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-5 flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="radar-chip">Asset Research Agent</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
            Research any crypto, token, or stock
          </h2>
          <p className="mt-2 max-w-4xl text-sm leading-7 text-[var(--radar-muted)]">
            The agent reads public summaries and headlines, then combines that context with your own 5-minute session momentum.
            It is a research assistant only, not an execution engine.
          </p>
        </div>
        {result ? (
          <div className={`min-w-[260px] rounded-[18px] border px-4 py-3 text-sm ${sessionTone(result.session_support.dominant_session)}`}>
            <div className="font-semibold">Strongest pressure: {result.session_support.dominant_session}</div>
            <div className="mt-1 opacity-90">{sessionPressure(result)}</div>
            <div className="mt-1 opacity-80">{result.session_support.matched_symbol ?? "No tracked futures match"}</div>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[460px_minmax(0,1fr)]">
        <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4 transition hover:border-[color:var(--radar-line-strong)] hover:bg-[var(--radar-panel-soft)]">
          <form className="space-y-4" onSubmit={onSubmit}>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--radar-muted)]">Asset input</span>
              <input
                className="mt-2 w-full rounded-[16px] border border-[color:var(--radar-line)] bg-[rgba(1,8,7,0.72)] px-4 py-3 text-sm font-semibold text-[var(--radar-ink)] outline-none transition placeholder:text-[var(--radar-muted)] hover:border-[color:var(--radar-line-strong)] focus:border-[color:var(--radar-sea)]"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="BTC, Solana, XRP, AAPL..."
                value={query}
              />
            </label>
            <button
              className="w-full rounded-[16px] bg-[var(--radar-sea)] px-4 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:bg-emerald-300 disabled:cursor-wait disabled:opacity-60"
              disabled={isLoading}
              type="submit"
            >
              {isLoading ? "Researching..." : "Run Research"}
            </button>
          </form>

          {error ? (
            <div className="mt-4 rounded-[16px] border border-rose-400/25 bg-rose-500/10 p-3 text-sm leading-6 text-rose-100">
              {error}
            </div>
          ) : null}

          {result ? (
            <div className="mt-4 space-y-3 text-sm">
              <div className="rounded-[16px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-3">
                <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Confidence</div>
                <div className="mt-1 text-lg font-semibold text-[var(--radar-ink)]">{Math.round(result.confidence * 100)}%</div>
              </div>
              <div className="rounded-[16px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-3">
                <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Sources</div>
                <div className="mt-2 space-y-2">
                  {result.sources.slice(0, 5).map((source) => (
                    <a
                      className="block break-words text-[var(--radar-ink)] underline decoration-[var(--radar-line-strong)] underline-offset-4 transition hover:text-[var(--radar-sea)]"
                      href={source.url}
                      key={`${source.source}-${source.url}`}
                      rel="noreferrer"
                      target="_blank"
                      title={source.title}
                    >
                      {source.source}: {source.title}
                    </a>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4 transition hover:border-[color:var(--radar-line-strong)]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-[var(--radar-ink)]">Research summary</div>
              <div className="mt-1 text-xs text-[var(--radar-muted)]">Public web context plus your stored session momentum.</div>
            </div>
            {result ? (
              <div className="rounded-full border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-3 py-1 text-xs text-[var(--radar-muted)]">
                {result.asset_type}
              </div>
            ) : null}
          </div>
          <textarea
            className="min-h-[520px] w-full resize-y rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(1,8,7,0.74)] p-4 font-mono text-sm leading-7 text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            readOnly
            value={brief}
          />
        </div>
      </div>
    </section>
  );
}
