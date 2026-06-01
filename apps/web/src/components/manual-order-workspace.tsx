"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { sendManualSignal } from "@/lib/api";

const symbols = [
  { label: "BTC", api: "BTC_USDT_PERP", tv: "BINANCE:BTCUSDT.P" },
  { label: "ETH", api: "ETH_USDT_PERP", tv: "BINANCE:ETHUSDT.P" },
  { label: "XRP", api: "XRP_USDT_PERP", tv: "BINANCE:XRPUSDT.P" },
  { label: "SOL", api: "SOL_USDT_PERP", tv: "BINANCE:SOLUSDT.P" },
  { label: "DOGE", api: "DOGE_USDT_PERP", tv: "BINANCE:DOGEUSDT.P" },
  { label: "BNB", api: "BNB_USDT_PERP", tv: "BINANCE:BNBUSDT.P" },
];

function toNumber(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

type TicketFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  suffix?: string;
};

function TicketField({ label, value, onChange, placeholder, suffix = "USDT" }: TicketFieldProps) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{label}</span>
      <span className="flex items-center rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.52)] px-3 py-2 transition hover:border-[color:var(--radar-line-strong)] focus-within:border-[color:var(--radar-sea)]">
        <input
          className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
          inputMode="decimal"
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          value={value}
        />
        <span className="ml-2 text-xs font-semibold text-white">{suffix}</span>
      </span>
    </label>
  );
}

export function ManualOrderWorkspace() {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [symbol, setSymbol] = useState(symbols[2]);
  const [orderType, setOrderType] = useState<"LIMIT" | "MARKET_QTY">("MARKET_QTY");
  const [quantity, setQuantity] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [leverage, setLeverage] = useState("10");
  const [reduceOnly, setReduceOnly] = useState(false);
  const [tpSlEnabled, setTpSlEnabled] = useState(true);
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  const maxBuyLabel = useMemo(() => {
    const qty = toNumber(quantity);
    return qty ? `${qty.toLocaleString()} ${symbol.label}` : `-- ${symbol.label}`;
  }, [quantity, symbol.label]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    container.innerHTML = "";
    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget h-full w-full";
    container.appendChild(widget);

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: symbol.tv,
      interval: "15",
      timezone: "America/Toronto",
      theme: "dark",
      style: "1",
      locale: "en",
      enable_publishing: false,
      allow_symbol_change: true,
      calendar: false,
      support_host: "https://www.tradingview.com",
    });
    container.appendChild(script);
  }, [symbol]);

  function submit(side: "BUY" | "SELL") {
    setMessage("");
    const size = toNumber(quantity);
    const entry = toNumber(entryPrice);
    if (!size || !entry) {
      setMessage("Quantity and entry/current price are required before submitting.");
      return;
    }

    startTransition(async () => {
      try {
        const response = await sendManualSignal({
          symbol: symbol.api,
          side,
          order_type: orderType,
          size,
          entry_price: entry,
          stop_price: tpSlEnabled ? toNumber(stopLoss) : undefined,
          take_profit_price: tpSlEnabled ? toNumber(takeProfit) : undefined,
          planned_leverage: toNumber(leverage),
          position_side: "BOTH",
          reduce_only: reduceOnly,
          strategy: "manual-ticket",
        });
        setMessage(`${response.message} Status: ${response.signal.status}.`);
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Manual signal failed.");
      }
    });
  }

  return (
    <section className="radar-card grid overflow-hidden lg:h-[720px] lg:grid-cols-[420px_minmax(0,1fr)]">
      <aside className="border-b border-[color:var(--radar-line)] p-4 lg:h-[720px] lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <div className="mb-4 flex gap-5 text-sm font-semibold">
          {[
            ["LIMIT", "Limit"],
            ["MARKET_QTY", "Market"],
          ].map(([value, label]) => (
            <button
              className={`rounded-full px-3 py-2 transition ${orderType === value ? "bg-[var(--radar-panel)] text-white shadow-sm" : "text-slate-400 hover:bg-[var(--radar-panel-soft)] hover:text-white"}`}
              key={value}
              onClick={() => setOrderType(value as "LIMIT" | "MARKET_QTY")}
              type="button"
            >
              {label}
            </button>
          ))}
          <button className="rounded-full px-3 py-2 text-slate-400 transition hover:bg-[var(--radar-panel-soft)] hover:text-white" type="button">Conditional</button>
        </div>

        <label className="mb-3 flex items-center rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.52)] px-3 py-2 transition hover:border-[color:var(--radar-line-strong)] focus-within:border-[color:var(--radar-sea)]">
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
            inputMode="decimal"
            onChange={(event) => setQuantity(event.target.value)}
            placeholder="Quantity"
            value={quantity}
          />
          <select
            className="rounded-full bg-[var(--radar-panel)] px-2 py-1 text-sm font-semibold text-white outline-none"
            onChange={(event) => setSymbol(symbols.find((item) => item.api === event.target.value) ?? symbols[0])}
            value={symbol.api}
          >
            {symbols.map((item) => (
              <option key={item.api} value={item.api}>{item.label}</option>
            ))}
          </select>
        </label>

        <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
          <span>Buy <span className="text-emerald-400">{quantity || 0} {symbol.label}</span></span>
          <span>Sell <span className="text-rose-400">{quantity || 0} {symbol.label}</span></span>
        </div>

        <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
          <span>Available</span>
          <span className="font-semibold text-white">Paper balance / risk gate</span>
        </div>

        <div className="mb-4 h-px bg-[color:var(--radar-line)]" />

        <label className="mb-3 flex items-center gap-2 rounded-[18px] border border-transparent px-2 py-1 text-sm text-slate-300 transition hover:border-[color:var(--radar-line)] hover:bg-[var(--radar-panel-soft)]">
          <input checked={reduceOnly} onChange={(event) => setReduceOnly(event.target.checked)} type="checkbox" />
          Reduce only
        </label>
        <label className="mb-3 flex items-center gap-2 rounded-[18px] border border-transparent px-2 py-1 text-sm text-slate-300 transition hover:border-[color:var(--radar-line)] hover:bg-[var(--radar-panel-soft)]">
          <input checked={tpSlEnabled} onChange={(event) => setTpSlEnabled(event.target.checked)} type="checkbox" />
          TP/SL
        </label>

        <div className="grid gap-3">
          <TicketField label="Entry / Current Price" onChange={setEntryPrice} placeholder="Required" value={entryPrice} />
          <TicketField label="TP Price" onChange={setTakeProfit} placeholder="Take profit" value={takeProfit} />
          <TicketField label="SL Price" onChange={setStopLoss} placeholder="Stop loss" value={stopLoss} />
          <TicketField label="Leverage" onChange={setLeverage} placeholder="10" suffix="x" value={leverage} />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            className="rounded-[18px] bg-[#08b875] px-4 py-3 text-sm font-bold text-white shadow-[0_18px_42px_-24px_rgba(8,184,117,0.9)] transition hover:-translate-y-0.5 hover:bg-[#10c985] hover:shadow-[0_22px_50px_-22px_rgba(8,184,117,0.95)] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isPending}
            onClick={() => submit("BUY")}
            type="button"
          >
            Buy / Long
          </button>
          <button
            className="rounded-[18px] bg-[#ef4444] px-4 py-3 text-sm font-bold text-white shadow-[0_18px_42px_-24px_rgba(239,68,68,0.9)] transition hover:-translate-y-0.5 hover:bg-[#ff5a5a] hover:shadow-[0_22px_50px_-22px_rgba(239,68,68,0.95)] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isPending}
            onClick={() => submit("SELL")}
            type="button"
          >
            Sell / Short
          </button>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
          <div>Max Buy <span className="font-semibold text-white">{maxBuyLabel}</span></div>
          <div className="text-right">Max Sell <span className="font-semibold text-white">{maxBuyLabel}</span></div>
          <div>Cost <span className="font-semibold text-white">risk checked</span></div>
          <div className="text-right">Est. Liq. <span className="font-semibold text-white">-- USDT</span></div>
        </div>

        <div className="mt-4 rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-3 text-xs text-slate-300 transition hover:border-[color:var(--radar-line-strong)] hover:bg-[var(--radar-panel)]">
          <div className="font-semibold text-white">Manual signal path</div>
          <div className="mt-1">Buttons submit to backend, then through webhook normalization, risk gate, and current paper/supervised/live mode.</div>
        </div>
        {message ? <div className="mt-3 text-xs leading-5 text-cyan-300">{message}</div> : null}
      </aside>

      <div className="min-h-[560px] min-w-0 overflow-hidden bg-[rgba(2,6,5,0.72)] lg:h-[720px]">
        <div className="flex h-12 items-center justify-between border-b border-[color:var(--radar-line)] px-4 text-xs text-slate-400">
          <div className="min-w-0 truncate">{symbol.label}/USDT Perp · 15 · TradingView</div>
          <div className="flex shrink-0 gap-4">
            {["1m", "5m", "15m", "1H", "4H", "1D", "1W"].map((item) => (
              <span className={`rounded-full px-2 py-1 transition ${item === "15m" ? "bg-[var(--radar-panel)] font-semibold text-white" : "hover:bg-[var(--radar-panel-soft)] hover:text-white"}`} key={item}>{item}</span>
            ))}
          </div>
        </div>
        <div className="relative h-[520px] overflow-hidden rounded-b-[30px] lg:h-[668px]">
          <div ref={containerRef} className="absolute inset-0 h-full w-full overflow-hidden" />
        </div>
      </div>
    </section>
  );
}
