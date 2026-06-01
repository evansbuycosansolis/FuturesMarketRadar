"use client";

import { useEffect, useRef, useState } from "react";

const chartSymbols = [
  { label: "BTC Perp", value: "BINANCE:BTCUSDT.P" },
  { label: "ETH Perp", value: "BINANCE:ETHUSDT.P" },
  { label: "SOL Perp", value: "BINANCE:SOLUSDT.P" },
  { label: "Pionex BTC", value: "PIONEX:BTCUSDT" },
];

export function TradingViewChartPanel() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [symbol, setSymbol] = useState(chartSymbols[0].value);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "blocked">("loading");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    setLoadState("loading");
    container.innerHTML = "";
    const widgetContainer = document.createElement("div");
    widgetContainer.className = "tradingview-widget-container__widget h-full min-h-[520px]";
    container.appendChild(widgetContainer);

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol,
      interval: "15",
      timezone: "America/Toronto",
      theme: "dark",
      style: "1",
      locale: "en",
      allow_symbol_change: true,
      calendar: false,
      support_host: "https://www.tradingview.com",
    });
    script.addEventListener("load", () => {
      window.setTimeout(() => setLoadState("ready"), 1500);
    });
    script.addEventListener("error", () => setLoadState("blocked"));
    container.appendChild(script);

    const timeout = window.setTimeout(() => {
      if (!container.querySelector("iframe")) {
        setLoadState("blocked");
      }
    }, 6000);

    return () => window.clearTimeout(timeout);
  }, [symbol]);

  const tradingViewUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`;

  return (
    <section className="radar-card overflow-hidden p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">TradingView Chart</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Live chart workspace</h2>
        </div>
        <select
          className="rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
          onChange={(event) => setSymbol(event.target.value)}
          value={symbol}
        >
          {chartSymbols.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <div className="relative mt-6 h-[72vh] min-h-[620px] overflow-hidden rounded-[24px] border border-[color:var(--radar-line)] bg-black">
        <div ref={containerRef} className="h-full w-full" />
        {loadState !== "ready" ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/72 p-6">
            <div className="max-w-md text-center">
              <div className="text-xs uppercase tracking-[0.18em] text-[var(--radar-muted)]">
                {loadState === "loading" ? "Loading TradingView" : "TradingView embed unavailable"}
              </div>
              <p className="mt-3 text-sm leading-7 text-[var(--radar-muted)]">
                {loadState === "loading"
                  ? "The external chart widget is connecting. If it stays here, a browser blocker, firewall, or third-party script setting may be stopping it."
                  : "The chart widget script did not load inside the app. You can still open the same symbol directly on TradingView."}
              </p>
              <a
                className="pointer-events-auto mt-4 inline-flex rounded-full border border-[color:rgba(46,183,154,0.28)] bg-[rgba(18,58,49,0.64)] px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:border-[color:rgba(46,183,154,0.5)]"
                href={tradingViewUrl}
                rel="noreferrer"
                target="_blank"
              >
                Open Chart
              </a>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
