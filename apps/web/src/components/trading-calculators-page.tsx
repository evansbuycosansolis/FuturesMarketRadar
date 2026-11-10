"use client";

import { useEffect, useMemo, useState } from "react";

import { AppFrame } from "@/components/app-frame";
import { analyzeSimulatorSetup } from "@/lib/api";
import { formatCurrency, formatPrice } from "@/lib/formatters";

type Side = "long" | "short";
type OrderType = "maker" | "taker";
type EntryType = "market" | "limit";
type TpSlMode = "manual" | "fib";
type ProjectionMode = "fib" | "ticket" | "custom";
type FibTimeframe = "5m" | "15m" | "1h" | "4h";
type CalculatorTab = "pnl" | "liquidation" | "position" | "riskReward" | "targets" | "dca" | "fees" | "compound" | "scenario";
type SimulatedPosition = {
  side: Side;
  symbol: string;
  entryType: EntryType;
  entry: number;
  margin: number;
  leverage: number;
  orderType: OrderType;
  stopLoss: number;
  takeProfit: number;
  openedAt: string;
};
type FibLevels = {
  swingHigh: number;
  swingLow: number;
  retrace382: number;
  retrace618: number;
  retrace786: number;
  extension1272: number;
  extension1618: number;
  updatedAt: string;
};
type FibRiskProfile = "conservative" | "standard" | "aggressive";

const tabs: { id: CalculatorTab; label: string }[] = [
  { id: "pnl", label: "Profit/Loss" },
  { id: "liquidation", label: "Liquidation" },
  { id: "position", label: "Position Size" },
  { id: "riskReward", label: "Risk/Reward" },
  { id: "targets", label: "TP / SL" },
  { id: "dca", label: "DCA Average" },
  { id: "fees", label: "Fees" },
  { id: "compound", label: "Compounding" },
  { id: "scenario", label: "Scenario" },
];

function n(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function pct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(value, max));
}

function sideMultiplier(side: Side): number {
  return side === "long" ? 1 : -1;
}

function positionValue(margin: number, leverage: number): number {
  return Math.max(margin, 0) * Math.max(leverage, 0);
}

function quantityFromNotional(notional: number, entry: number): number {
  return entry > 0 ? notional / entry : 0;
}

function grossPnl(side: Side, entry: number, exit: number, quantity: number): number {
  return (exit - entry) * quantity * sideMultiplier(side);
}

function feeRate(orderType: OrderType, makerFeePct: number, takerFeePct: number): number {
  return (orderType === "maker" ? makerFeePct : takerFeePct) / 100;
}

function estimateFees({
  entry,
  exit,
  margin,
  leverage,
  orderType,
  makerFeePct,
  takerFeePct,
  fundingRatePct,
  fundingSettlements,
}: {
  entry: number;
  exit: number;
  margin: number;
  leverage: number;
  orderType: OrderType;
  makerFeePct: number;
  takerFeePct: number;
  fundingRatePct: number;
  fundingSettlements: number;
}) {
  const notional = positionValue(margin, leverage);
  const quantity = quantityFromNotional(notional, entry);
  const exitValue = quantity * exit;
  const rate = feeRate(orderType, makerFeePct, takerFeePct);
  const openingFee = notional * rate;
  const closingFee = exitValue * rate;
  const fundingFee = notional * (fundingRatePct / 100) * fundingSettlements;
  return { openingFee, closingFee, fundingFee, totalFees: openingFee + closingFee + fundingFee, notional, quantity, exitValue };
}

function Field({ label, value, onChange, suffix, min = "0", max, step = "any" }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  suffix?: string;
  min?: string;
  max?: string;
  step?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">{label}</span>
      <span className="mt-2 flex items-center rounded-[16px] border border-[color:var(--radar-line)] bg-black/20 px-3 transition focus-within:border-[color:var(--radar-sea)] hover:border-[color:var(--radar-line-strong)]">
        <input
          className="min-w-0 flex-1 bg-transparent py-3 text-sm font-semibold text-[var(--radar-ink)] outline-none"
          max={max}
          min={min}
          onChange={(event) => onChange(event.target.value)}
          step={step}
          type="number"
          value={value}
        />
        {suffix ? <span className="text-xs font-semibold text-[var(--radar-muted)]">{suffix}</span> : null}
      </span>
    </label>
  );
}

function TextField({ label, value, onChange }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">{label}</span>
      <span className="mt-2 flex items-center rounded-[16px] border border-[color:var(--radar-line)] bg-black/20 px-3 transition focus-within:border-[color:var(--radar-sea)] hover:border-[color:var(--radar-line-strong)]">
        <input
          className="min-w-0 flex-1 bg-transparent py-3 text-sm font-semibold text-[var(--radar-ink)] outline-none"
          onChange={(event) => onChange(event.target.value)}
          type="text"
          value={value}
        />
      </span>
    </label>
  );
}

function Result({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "good" | "bad" | "warn" }) {
  const toneClass = {
    neutral: "text-[var(--radar-ink)]",
    good: "text-emerald-300",
    bad: "text-rose-300",
    warn: "text-amber-300",
  }[tone];

  return (
    <div className="rounded-[16px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.46)] p-4 transition hover:border-[color:var(--radar-line-strong)]">
      <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">{label}</div>
      <div className={`mt-2 break-words text-xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function SegmentButton({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
        active ? "bg-[var(--radar-sea)] text-black" : "bg-[var(--radar-panel-soft)] text-[var(--radar-muted)] hover:text-[var(--radar-ink)]"
      }`}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function TradingViewPracticeChart({ symbol }: { symbol: string }) {
  const embedUrl = useMemo(() => {
    const query = new URLSearchParams({
      symbol,
      interval: "15",
      hidetoptoolbar: "0",
      hidelegend: "0",
      saveimage: "0",
      theme: "dark",
      style: "1",
      timezone: "America/Toronto",
      locale: "en",
      studies: "STD;Donchian_Channels",
      withdateranges: "1",
      allow_symbol_change: "0",
      calendar: "0",
    });

    return `https://www.tradingview.com/widgetembed/?${query.toString()}`;
  }, [symbol]);

  return (
    <div className="relative h-[680px] overflow-hidden rounded-[22px] border border-[color:var(--radar-line)] bg-black">
      <div className="absolute inset-0 grid place-items-center px-6 text-center text-sm text-[var(--radar-muted)]">
        Loading TradingView chart. If it stays blank, check browser third-party frame blocking.
      </div>
      <iframe
        allowFullScreen
        className="relative z-10 h-full w-full border-0"
        key={embedUrl}
        src={embedUrl}
        title={`TradingView practice chart ${symbol}`}
      />
    </div>
  );
}

function selectMarketEntry(setSimEntryType: (value: EntryType) => void, setSimEntry: (value: string) => void, livePrice: string) {
  setSimEntryType("market");
  if (n(livePrice) > 0) {
    setSimEntry(livePrice);
  }
}

function binanceFuturesSymbolFromTradingView(symbol: string): string | null {
  const normalized = symbol.trim().toUpperCase();
  if (!normalized.startsWith("BINANCE:")) {
    return null;
  }

  const rawSymbol = normalized.replace("BINANCE:", "").replace(/\.P$/, "");
  const cleanSymbol = rawSymbol.replace(/[^A-Z0-9]/g, "");
  return cleanSymbol.endsWith("USDT") ? cleanSymbol : null;
}

function normalizeTradingViewSymbolInput(value: string): string {
  const trimmed = value.trim();
  const normalized = trimmed.toUpperCase();
  const withoutExchange = normalized.includes(":") ? normalized.split(":").at(-1) ?? normalized : normalized;
  const cleanSymbol = withoutExchange.replace(/\.P$/, "").replace(/[^A-Z0-9]/g, "");

  if (cleanSymbol.endsWith("USDT") && cleanSymbol.length > 4) {
    return `BINANCE:${cleanSymbol}.P`;
  }

  return trimmed;
}

function firstValidLevel(levels: number[], predicate: (level: number) => boolean): number | null {
  return levels.find((level) => Number.isFinite(level) && level > 0 && predicate(level)) ?? null;
}

function fibTicketLevels(levels: FibLevels, side: Side, entry: number, profile: FibRiskProfile) {
  const longStopsByProfile = {
    conservative: [levels.retrace618, levels.retrace786, levels.swingLow],
    standard: [levels.retrace786, levels.retrace618, levels.swingLow],
    aggressive: [levels.swingLow, levels.retrace786, levels.retrace618],
  };
  const shortStopsByProfile = {
    conservative: [levels.retrace382, levels.retrace618, levels.swingHigh],
    standard: [levels.retrace618, levels.retrace382, levels.swingHigh],
    aggressive: [levels.swingHigh, levels.retrace618, levels.retrace382],
  };
  const targetsByProfile = {
    conservative: [levels.extension1272, levels.extension1618],
    standard: [levels.extension1272, levels.extension1618],
    aggressive: [levels.extension1618, levels.extension1272],
  };

  if (side === "long") {
    return {
      stop: firstValidLevel(longStopsByProfile[profile], (level) => level < entry),
      takeProfit: firstValidLevel(targetsByProfile[profile], (level) => level > entry),
    };
  }

  return {
    stop: firstValidLevel(shortStopsByProfile[profile], (level) => level > entry),
    takeProfit: firstValidLevel(targetsByProfile[profile], (level) => level < entry),
  };
}

function formatTradePrice(price: number): string {
  if (!Number.isFinite(price) || price <= 0) {
    return "0";
  }

  return price < 1 ? price.toFixed(8).replace(/0+$/, "").replace(/\.$/, "") : price.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
}

export function TradingCalculatorsPage() {
  const [tab, setTab] = useState<CalculatorTab>("pnl");
  const [side, setSide] = useState<Side>("long");
  const [calculatorOrderType, setCalculatorOrderType] = useState<OrderType>("taker");
  const [entry, setEntry] = useState("0.1174");
  const [exit, setExit] = useState("0.2211");
  const [margin, setMargin] = useState("20");
  const [leverage, setLeverage] = useState("10");
  const [makerFee, setMakerFee] = useState("0.02");
  const [takerFee, setTakerFee] = useState("0.05");
  const [fundingRate, setFundingRate] = useState("0.01");
  const [fundingSettlements, setFundingSettlements] = useState("0");
  const [maintenanceMargin, setMaintenanceMargin] = useState("0.5");
  const [accountBalance, setAccountBalance] = useState("500");
  const [riskPct, setRiskPct] = useState("2");
  const [stopLossPct, setStopLossPct] = useState("4");
  const [stopPrice, setStopPrice] = useState("0.095");
  const [takeProfitPrice, setTakeProfitPrice] = useState("0.115");
  const [targetLoss, setTargetLoss] = useState("10");
  const [targetProfit, setTargetProfit] = useState("100");
  const [desiredProfitPct, setDesiredProfitPct] = useState("20");
  const [compoundCapital, setCompoundCapital] = useState("100");
  const [dailyGain, setDailyGain] = useState("5");
  const [compoundDays, setCompoundDays] = useState("30");
  const [scenarioPrice, setScenarioPrice] = useState("0.15");
  const [simSymbol, setSimSymbol] = useState("BINANCE:BTCUSDT.P");
  const [simSide, setSimSide] = useState<Side>("long");
  const [simEntryType, setSimEntryType] = useState<EntryType>("market");
  const [simTpSlMode, setSimTpSlMode] = useState<TpSlMode>("manual");
  const [simEntry, setSimEntry] = useState("62000");
  const [simLivePrice, setSimLivePrice] = useState("62500");
  const [simCurrent, setSimCurrent] = useState("62500");
  const [simExitTouched, setSimExitTouched] = useState(false);
  const [simMargin, setSimMargin] = useState("50");
  const [simLeverage, setSimLeverage] = useState("10");
  const [simStop, setSimStop] = useState("60800");
  const [simTakeProfit, setSimTakeProfit] = useState("65000");
  const [projectionMode, setProjectionMode] = useState<ProjectionMode>("ticket");
  const [projectionStop, setProjectionStop] = useState("60800");
  const [projectionTakeProfit, setProjectionTakeProfit] = useState("65000");
  const [simWhatIfPct, setSimWhatIfPct] = useState("0");
  const [practiceCash, setPracticeCash] = useState(3000);
  const [simPosition, setSimPosition] = useState<SimulatedPosition | null>(null);
  const [livePriceStatus, setLivePriceStatus] = useState("Waiting for Binance futures price feed");
  const [livePriceUpdatedAt, setLivePriceUpdatedAt] = useState("");
  const [fibTimeframe, setFibTimeframe] = useState<FibTimeframe>("15m");
  const [fibStatus, setFibStatus] = useState("Waiting for Fibonacci candle scan");
  const [fibLevels, setFibLevels] = useState<FibLevels | null>(null);
  const [tradeNotification, setTradeNotification] = useState("");
  const [coachAnalysis, setCoachAnalysis] = useState("");
  const [coachWarnings, setCoachWarnings] = useState<string[]>([]);
  const [coachStatus, setCoachStatus] = useState("Ready to analyze the simulated setup.");
  const [coachLoading, setCoachLoading] = useState(false);
  const [dcaRows, setDcaRows] = useState([
    { price: "0.10", amount: "50" },
    { price: "0.09", amount: "50" },
    { price: "0.08", amount: "100" },
  ]);

  const binanceLiveSymbol = useMemo(() => binanceFuturesSymbolFromTradingView(simSymbol), [simSymbol]);
  const simulatorOrderType: OrderType = simEntryType === "limit" ? "maker" : "taker";

  useEffect(() => {
    let cancelled = false;

    async function refreshLivePrice() {
      if (!binanceLiveSymbol) {
        setLivePriceStatus("Manual mark price: live feed supports Binance USDT futures symbols only");
        return;
      }

      try {
        const response = await fetch(`https://fapi.binance.com/fapi/v2/ticker/price?symbol=${encodeURIComponent(binanceLiveSymbol)}`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json() as { price?: string };
        const price = Number(payload.price);

        if (!Number.isFinite(price) || price <= 0) {
          throw new Error("Missing price");
        }

        if (cancelled) {
          return;
        }

        const formattedPrice = formatTradePrice(price);
        setSimLivePrice(formattedPrice);
        if (!simExitTouched) {
          setSimCurrent(formattedPrice);
        }
        if (simEntryType === "market") {
          setSimEntry(formattedPrice);
        }
        setLivePriceUpdatedAt(new Date().toLocaleTimeString("en-CA", { timeZone: "America/Toronto" }));
        setLivePriceStatus(`Live Binance futures price: ${binanceLiveSymbol}`);
      } catch {
        if (!cancelled) {
          setLivePriceStatus(`Live price unavailable for ${binanceLiveSymbol}; use manual mark price`);
        }
      }
    }

    refreshLivePrice();
    const intervalId = window.setInterval(refreshLivePrice, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [binanceLiveSymbol, simEntryType, simExitTouched]);

  useEffect(() => {
    let cancelled = false;

    async function refreshFibLevels() {
      if (!binanceLiveSymbol) {
        setFibLevels(null);
        setFibStatus("Fibonacci scan supports Binance USDT futures symbols only");
        return;
      }

      try {
        const response = await fetch(`https://fapi.binance.com/fapi/v1/klines?symbol=${encodeURIComponent(binanceLiveSymbol)}&interval=${fibTimeframe}&limit=120`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const candles = await response.json() as unknown[][];
        const completedCandles = candles.slice(0, -1);
        const highs = completedCandles.map((candle) => Number(candle[2])).filter(Number.isFinite);
        const lows = completedCandles.map((candle) => Number(candle[3])).filter(Number.isFinite);

        if (highs.length < 20 || lows.length < 20) {
          throw new Error("Not enough candles");
        }

        const swingHigh = Math.max(...highs);
        const swingLow = Math.min(...lows);
        const range = swingHigh - swingLow;

        if (!Number.isFinite(range) || range <= 0) {
          throw new Error("Invalid range");
        }

        const nextLevels = {
          swingHigh,
          swingLow,
          retrace382: swingHigh - range * 0.382,
          retrace618: swingHigh - range * 0.618,
          retrace786: swingHigh - range * 0.786,
          extension1272: simSide === "long" ? swingHigh + range * 0.272 : swingLow - range * 0.272,
          extension1618: simSide === "long" ? swingHigh + range * 0.618 : swingLow - range * 0.618,
          updatedAt: new Date().toLocaleTimeString("en-CA", { timeZone: "America/Toronto" }),
        };

        if (!cancelled) {
          setFibLevels(nextLevels);
          setFibStatus(`Fibonacci levels from ${binanceLiveSymbol} ${fibTimeframe} candles`);
        }
      } catch {
        if (!cancelled) {
          setFibLevels(null);
          setFibStatus(`Fibonacci scan unavailable for ${binanceLiveSymbol}`);
        }
      }
    }

    refreshFibLevels();
    const intervalId = window.setInterval(refreshFibLevels, 30000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [binanceLiveSymbol, fibTimeframe, simSide]);

  useEffect(() => {
    if (!tradeNotification) {
      return;
    }

    const timeoutId = window.setTimeout(() => setTradeNotification(""), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [tradeNotification]);

  function selectSimulatorSide(nextSide: Side) {
    if (nextSide === simSide) {
      return;
    }

    setSimSide(nextSide);
    setSimWhatIfPct("0");

    if (simTpSlMode === "fib" && fibLevels) {
      const levels = fibTicketLevels(fibLevels, nextSide, n(simEntry), "standard");
      if (levels.stop) {
        setSimStop(formatTradePrice(levels.stop));
      }
      if (levels.takeProfit) {
        setSimTakeProfit(formatTradePrice(levels.takeProfit));
      }
      return;
    }

    const entryValue = n(simEntry);
    const stopValue = n(simStop);
    const takeProfitValue = n(simTakeProfit);
    const looksLikeLongSetup = stopValue < entryValue && takeProfitValue > entryValue;
    const looksLikeShortSetup = stopValue > entryValue && takeProfitValue < entryValue;

    if ((nextSide === "long" && looksLikeShortSetup) || (nextSide === "short" && looksLikeLongSetup)) {
      setSimStop(formatTradePrice(takeProfitValue));
      setSimTakeProfit(formatTradePrice(stopValue));
    }
  }

  async function runCoachAnalysis() {
    setCoachLoading(true);
    setCoachStatus("Analyzing current simulator setup...");
    setCoachWarnings([]);
    try {
      const result = await analyzeSimulatorSetup({
        symbol: simSymbol,
        side: simSide,
        entry_type: simEntryType,
        entry_price: n(simEntry),
        mark_price: n(simCurrent),
        margin: n(simMargin),
        leverage: n(simLeverage),
        stop_loss: n(simStop) > 0 ? n(simStop) : null,
        take_profit: n(simTakeProfit) > 0 ? n(simTakeProfit) : null,
        order_type: simulatorOrderType,
        timeframe: fibTimeframe,
      });
      setCoachAnalysis(result.analysis);
      setCoachWarnings(result.warnings);
      setCoachStatus(result.used_ai ? `AI coach analysis from ${result.model}.` : "Local coach analysis. Add FMR_OPENAI_API_KEY for ChatGPT analysis.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown simulator coach error.";
      setCoachAnalysis("");
      setCoachStatus(message);
    } finally {
      setCoachLoading(false);
    }
  }

  const values = useMemo(() => {
    const entryValue = n(entry);
    const exitValue = n(exit);
    const marginValue = n(margin);
    const leverageValue = n(leverage);
    const notional = positionValue(marginValue, leverageValue);
    const quantity = quantityFromNotional(notional, entryValue);
    const fees = estimateFees({
      entry: entryValue,
      exit: exitValue,
      margin: marginValue,
      leverage: leverageValue,
      orderType: calculatorOrderType,
      makerFeePct: n(makerFee),
      takerFeePct: n(takerFee),
      fundingRatePct: n(fundingRate),
      fundingSettlements: n(fundingSettlements),
    });
    const gross = grossPnl(side, entryValue, exitValue, quantity);
    const net = gross - fees.totalFees;
    const roi = marginValue > 0 ? (net / marginValue) * 100 : 0;
    const mmr = n(maintenanceMargin) / 100;
    const liquidation =
      entryValue > 0 && leverageValue > 0
        ? side === "long"
          ? entryValue * (1 - 1 / leverageValue + mmr)
          : entryValue * (1 + 1 / leverageValue - mmr)
        : 0;
    const liquidationDistance = entryValue > 0 ? Math.abs((entryValue - liquidation) / entryValue) * 100 : 0;
    const riskAmount = n(accountBalance) * (n(riskPct) / 100);
    const positionByRisk = n(stopLossPct) > 0 ? riskAmount / (n(stopLossPct) / 100) : 0;
    const recommendedLeverage = marginValue > 0 ? positionByRisk / marginValue : 0;
    const stopRiskPct = entryValue > 0 ? Math.abs((entryValue - n(stopPrice)) / entryValue) * 100 : 0;
    const rewardPct = entryValue > 0 ? Math.abs((n(takeProfitPrice) - entryValue) / entryValue) * 100 : 0;
    const rr = stopRiskPct > 0 ? rewardPct / stopRiskPct : 0;
    const stopByLossMovePct = notional > 0 ? n(targetLoss) / notional : 0;
    const suggestedStop = side === "long" ? entryValue * (1 - stopByLossMovePct) : entryValue * (1 + stopByLossMovePct);
    const profitMovePct = notional > 0 ? n(targetProfit) / notional : 0;
    const tpByProfit = side === "long" ? entryValue * (1 + profitMovePct) : entryValue * (1 - profitMovePct);
    const tpByPercent = side === "long" ? entryValue * (1 + n(desiredProfitPct) / 100 / Math.max(leverageValue, 1)) : entryValue * (1 - n(desiredProfitPct) / 100 / Math.max(leverageValue, 1));
    const breakevenMove = quantity > 0 ? fees.totalFees / quantity : 0;
    const breakeven = side === "long" ? entryValue + breakevenMove : entryValue - breakevenMove;
    const scenarioGross = grossPnl(side, entryValue, n(scenarioPrice), quantity);
    const scenarioFees = estimateFees({
      entry: entryValue,
      exit: n(scenarioPrice),
      margin: marginValue,
      leverage: leverageValue,
      orderType: calculatorOrderType,
      makerFeePct: n(makerFee),
      takerFeePct: n(takerFee),
      fundingRatePct: n(fundingRate),
      fundingSettlements: n(fundingSettlements),
    });
    const scenarioNet = scenarioGross - scenarioFees.totalFees;

    const dca = dcaRows.reduce(
      (acc, row) => {
        const price = n(row.price);
        const amount = n(row.amount);
        const qty = price > 0 ? amount / price : 0;
        return { investment: acc.investment + amount, quantity: acc.quantity + qty };
      },
      { investment: 0, quantity: 0 },
    );
    const averageEntry = dca.quantity > 0 ? dca.investment / dca.quantity : 0;
    const compounded = n(compoundCapital) * (1 + n(dailyGain) / 100) ** n(compoundDays);

    return {
      notional,
      quantity,
      gross,
      net,
      roi,
      finalBalance: marginValue + net,
      liquidation,
      liquidationDistance,
      riskAmount,
      positionByRisk,
      recommendedLeverage,
      stopRiskPct,
      rewardPct,
      rr,
      suggestedStop,
      tpByProfit,
      tpByPercent,
      breakeven,
      fees,
      averageEntry,
      dcaInvestment: dca.investment,
      dcaQuantity: dca.quantity,
      compounded,
      scenarioNet,
      scenarioGross,
      scenarioRoi: marginValue > 0 ? (scenarioNet / marginValue) * 100 : 0,
    };
  }, [accountBalance, calculatorOrderType, compoundCapital, compoundDays, dailyGain, dcaRows, desiredProfitPct, entry, exit, fundingRate, fundingSettlements, leverage, maintenanceMargin, makerFee, margin, riskPct, scenarioPrice, side, stopLossPct, stopPrice, takerFee, takeProfitPrice, targetLoss, targetProfit]);

  const simValues = useMemo(() => {
    const active = simPosition ?? {
      side: simSide,
      symbol: simSymbol,
      entryType: simEntryType,
      entry: n(simEntry),
      margin: n(simMargin),
      leverage: n(simLeverage),
      orderType: simulatorOrderType,
      stopLoss: n(simStop),
      takeProfit: n(simTakeProfit),
      openedAt: "",
    };
    const current = n(simCurrent);
    const notional = positionValue(active.margin, active.leverage);
    const quantity = quantityFromNotional(notional, active.entry);
    const fees = estimateFees({
      entry: active.entry,
      exit: current,
      margin: active.margin,
      leverage: active.leverage,
      orderType: active.orderType,
      makerFeePct: n(makerFee),
      takerFeePct: n(takerFee),
      fundingRatePct: n(fundingRate),
      fundingSettlements: n(fundingSettlements),
    });
    const gross = grossPnl(active.side, active.entry, current, quantity);
    const net = gross - fees.totalFees;
    const roi = active.margin > 0 ? (net / active.margin) * 100 : 0;
    const mmr = n(maintenanceMargin) / 100;
    const liquidation =
      active.entry > 0 && active.leverage > 0
        ? active.side === "long"
          ? active.entry * (1 - 1 / active.leverage + mmr)
          : active.entry * (1 + 1 / active.leverage - mmr)
        : 0;
    const stopHit = active.stopLoss > 0 ? active.side === "long" ? current <= active.stopLoss : current >= active.stopLoss : false;
    const takeProfitHit = active.takeProfit > 0 ? active.side === "long" ? current >= active.takeProfit : current <= active.takeProfit : false;
    const liquidationHit = liquidation > 0 ? active.side === "long" ? current <= liquidation : current >= liquidation : false;
    const status = !simPosition
      ? "Ready to practice"
      : liquidationHit
        ? "Liquidation zone"
        : stopHit
          ? "Stop loss hit"
          : takeProfitHit
            ? "Take profit hit"
            : "Position open";

    return { active, current, notional, quantity, gross, net, roi, fees, liquidation, stopHit, takeProfitHit, liquidationHit, status };
  }, [fundingRate, fundingSettlements, maintenanceMargin, makerFee, simCurrent, simEntry, simEntryType, simLeverage, simMargin, simPosition, simSide, simStop, simSymbol, simTakeProfit, simulatorOrderType, takerFee]);

  const whatIfValues = useMemo(() => {
    const active = {
      side: simSide,
      symbol: simSymbol,
      entryType: simEntryType,
      entry: n(simEntry),
      margin: n(simMargin),
      leverage: n(simLeverage),
      orderType: simulatorOrderType,
      openedAt: "",
    };
    const fibProjectionLevels = fibLevels ? fibTicketLevels(fibLevels, active.side, active.entry, "standard") : null;
    const stop =
      projectionMode === "fib"
        ? fibProjectionLevels?.stop ?? 0
        : projectionMode === "custom"
          ? n(projectionStop)
          : n(simStop);
    const targetExit =
      projectionMode === "fib"
        ? fibProjectionLevels?.takeProfit ?? 0
        : projectionMode === "custom"
          ? n(projectionTakeProfit)
          : n(simTakeProfit);
    const targetSource =
      projectionMode === "fib"
        ? "Fibonacci target"
        : projectionMode === "custom"
          ? "custom take profit"
          : "ticket take profit";
    const pathPct = clamp(n(simWhatIfPct), -100, 100);
    const hasCompleteRange = stop > 0 && targetExit > 0 && active.entry > 0 && stop !== active.entry && targetExit !== active.entry;
    const isDirectionalRange =
      active.side === "long"
        ? stop < active.entry && targetExit > active.entry
        : stop > active.entry && targetExit < active.entry;
    const validRange = hasCompleteRange && isDirectionalRange;
    const rangeWarning = !hasCompleteRange
      ? `Add a valid stop loss and ${targetSource} to activate the distance simulator.`
      : active.side === "long"
        ? `For a long setup, stop loss must be below entry and ${targetSource} must be above entry.`
        : `For a short setup, stop loss must be above entry and ${targetSource} must be below entry.`;
    const targetLabel = projectionMode === "fib" ? "Fib TP" : projectionMode === "custom" ? "Custom TP" : "Ticket TP";
    const leftLabel = active.side === "long" ? "SL" : targetLabel;
    const rightLabel = active.side === "long" ? targetLabel : "SL";
    const leftPrice = active.side === "long" ? stop : targetExit;
    const rightPrice = active.side === "long" ? targetExit : stop;
    const price =
      validRange && pathPct < 0
        ? active.entry + (Math.abs(pathPct) / 100) * (leftPrice - active.entry)
        : validRange
          ? active.entry + (pathPct / 100) * (rightPrice - active.entry)
          : 0;
    const notional = positionValue(active.margin, active.leverage);
    const quantity = quantityFromNotional(notional, active.entry);
    const fees = estimateFees({
      entry: active.entry,
      exit: price,
      margin: active.margin,
      leverage: active.leverage,
      orderType: active.orderType,
      makerFeePct: n(makerFee),
      takerFeePct: n(takerFee),
      fundingRatePct: n(fundingRate),
      fundingSettlements: n(fundingSettlements),
    });
    const gross = grossPnl(active.side, active.entry, price, quantity);
    const net = gross - fees.totalFees;
    const roi = active.margin > 0 ? (net / active.margin) * 100 : 0;
    const movePct = active.entry > 0 ? ((price - active.entry) / active.entry) * 100 : 0;
    const mmr = n(maintenanceMargin) / 100;
    const liquidation =
      active.entry > 0 && active.leverage > 0
        ? active.side === "long"
          ? active.entry * (1 - 1 / active.leverage + mmr)
          : active.entry * (1 + 1 / active.leverage - mmr)
        : 0;
    const liquidationWarning =
      validRange && liquidation > 0
        ? active.side === "long" && stop <= liquidation
          ? "Warning: your stop loss is at or beyond the estimated liquidation area."
          : active.side === "short" && stop >= liquidation
            ? "Warning: your stop loss is at or beyond the estimated liquidation area."
            : ""
        : "";
    const pathLabel = pathPct < 0
      ? `${Math.abs(pathPct).toFixed(0)}% toward ${leftLabel}`
      : pathPct > 0
        ? `${pathPct.toFixed(0)}% toward ${rightLabel}`
        : "At entry";

    return { active, validRange, rangeWarning, stop, targetExit, targetLabel, leftLabel, rightLabel, leftPrice, rightPrice, pathPct, pathLabel, price, net, gross, roi, movePct, fees, liquidation, liquidationWarning };
  }, [fibLevels, fundingRate, fundingSettlements, maintenanceMargin, makerFee, projectionMode, projectionStop, projectionTakeProfit, simEntry, simEntryType, simLeverage, simMargin, simSide, simStop, simSymbol, simTakeProfit, simWhatIfPct, simulatorOrderType, takerFee]);

  const hasOpenSimulatedTrade = simPosition !== null;
  const displayedPositionNet = hasOpenSimulatedTrade ? simValues.net : 0;
  const displayedPositionRoi = hasOpenSimulatedTrade ? simValues.roi : 0;
  const displayedPositionFees = hasOpenSimulatedTrade ? simValues.fees.totalFees : 0;
  const openMargin = hasOpenSimulatedTrade ? simValues.active.margin : 0;
  const practiceEquity = practiceCash + openMargin + displayedPositionNet;
  const canOpenSimulatedTrade = !hasOpenSimulatedTrade && n(simMargin) > 0 && n(simMargin) <= practiceCash && n(simEntry) > 0 && n(simLeverage) > 0;

  return (
    <AppFrame
      current="simulator"
      title="Trading simulator for futures practice."
      subtitle="Practice long and short scenarios beside a live TradingView chart, then use the calculator toolkit to check PnL, liquidation, fees, risk, DCA, and compounding."
    >
      {tradeNotification ? (
        <div className="fixed right-6 top-6 z-50 max-w-sm rounded-[18px] border border-emerald-400/40 bg-emerald-950/90 p-4 text-sm text-emerald-50 shadow-2xl shadow-black/40">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-200">Simulator update</div>
          <div className="mt-2 font-semibold">{tradeNotification}</div>
          <div className="mt-1 text-xs text-emerald-100/80">Simulator only. No live order was placed.</div>
        </div>
      ) : null}

      <section className="radar-card overflow-hidden p-5 sm:p-6">
        <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="radar-chip">Paper trade simulator</div>
            <h2 className="mt-3 text-2xl font-semibold text-[var(--radar-ink)]">Practice trades against a real chart</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--radar-muted)]">
              Enter any TradingView symbol here and the chart, trade ticket, and simulated position will follow it. The ticket is
              simulated locally and does not place orders.
            </p>
          </div>
          <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-black/20 px-4 py-3 text-sm text-[var(--radar-muted)]">
            Training mode only
          </div>
        </div>

        <div className="space-y-5">
          <div className="grid gap-4 rounded-[22px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.5)] p-4 transition hover:border-[color:var(--radar-line-strong)] lg:grid-cols-[0.9fr_1.3fr] lg:items-end">
            <TextField
              label="Simulator symbol"
              value={simSymbol}
              onChange={(value) => {
                setSimSymbol(normalizeTradingViewSymbolInput(value));
                setSimExitTouched(false);
              }}
            />
            <div className="rounded-[16px] border border-[color:var(--radar-line)] bg-black/15 p-3 text-xs leading-5 text-[var(--radar-muted)]">
              Change the symbol here so the chart, live price, Fib levels, and simulator stay together. You can type shorthand like
              <span className="font-semibold text-[var(--radar-ink)]"> THETAUSDT</span>,
              <span className="font-semibold text-[var(--radar-ink)]"> HUSDT</span>, or
              <span className="font-semibold text-[var(--radar-ink)]"> BICOUSDT</span>.
              The chart search is locked because TradingView iframe changes cannot be read back by this app.
              <div className="mt-2 font-semibold text-[var(--radar-ink)]">
                {livePriceStatus}
                {livePriceUpdatedAt ? <span className="text-[var(--radar-muted)]"> · updated {livePriceUpdatedAt} Montreal time</span> : null}
              </div>
            </div>
          </div>

          <div className="grid gap-3 rounded-[22px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.5)] p-4 sm:grid-cols-4">
            <Result label="Practice cash" value={formatCurrency(practiceCash)} tone={practiceCash >= 0 ? "good" : "bad"} />
            <Result label="Reserved margin" value={formatCurrency(openMargin)} tone="warn" />
            <Result label="Live equity" value={formatCurrency(practiceEquity)} tone={practiceEquity >= 3000 ? "good" : practiceEquity > 0 ? "neutral" : "bad"} />
            <div className="rounded-[16px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.46)] p-4 transition hover:border-[color:var(--radar-line-strong)]">
              <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Practice account</div>
              <div className="mt-2 text-xl font-semibold text-[var(--radar-ink)]">$3,000 start</div>
              <button
                className="mt-3 rounded-full border border-[color:var(--radar-line)] px-3 py-2 text-xs font-semibold text-[var(--radar-muted)] transition hover:border-[color:var(--radar-line-strong)] hover:text-[var(--radar-ink)] disabled:cursor-not-allowed disabled:opacity-50"
                disabled={hasOpenSimulatedTrade}
                onClick={() => {
                  setPracticeCash(3000);
                  setTradeNotification("Practice account reset to $3,000.");
                }}
                type="button"
              >
                Reset funds
              </button>
            </div>
          </div>

          <TradingViewPracticeChart symbol={simSymbol} />

          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-[22px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.5)] p-4">
              <div className="radar-chip">Trade ticket</div>
              <div className="flex flex-wrap gap-2">
                <SegmentButton active={simEntryType === "market"} onClick={() => selectMarketEntry(setSimEntryType, setSimEntry, simLivePrice)}>Market</SegmentButton>
                <SegmentButton active={simEntryType === "limit"} onClick={() => setSimEntryType("limit")}>Limit</SegmentButton>
                <SegmentButton active={simSide === "long"} onClick={() => selectSimulatorSide("long")}>Long</SegmentButton>
                <SegmentButton active={simSide === "short"} onClick={() => selectSimulatorSide("short")}>Short</SegmentButton>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <Field label="Entry" value={simEntry} onChange={setSimEntry} />
                <Field
                  label="Exit price"
                  value={simCurrent}
                  onChange={(value) => {
                    setSimExitTouched(true);
                    setSimCurrent(value);
                  }}
                />
                <Field label="Margin" value={simMargin} onChange={setSimMargin} suffix="USDT" />
                <Field label="Leverage" value={simLeverage} onChange={setSimLeverage} suffix="x" />
              </div>

              <div className="mt-4 rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="radar-chip">TP / SL Settings</div>
                    <p className="mt-2 text-xs leading-5 text-[var(--radar-muted)]">
                      Type your own stop and target, or let Fibonacci fill these fields as an optional suggestion.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <SegmentButton active={simTpSlMode === "manual"} onClick={() => setSimTpSlMode("manual")}>Manual TP/SL</SegmentButton>
                    <SegmentButton
                      active={simTpSlMode === "fib"}
                      onClick={() => {
                        setSimTpSlMode("fib");
                        if (fibLevels) {
                          const levels = fibTicketLevels(fibLevels, simSide, n(simEntry), "standard");
                          if (levels.stop) {
                            setSimStop(formatTradePrice(levels.stop));
                          }
                          if (levels.takeProfit) {
                            setSimTakeProfit(formatTradePrice(levels.takeProfit));
                          }
                        }
                      }}
                    >
                      Apply Standard Fib
                    </SegmentButton>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <Field
                    label="Stop loss"
                    value={simStop}
                    onChange={(value) => {
                      setSimTpSlMode("manual");
                      setSimStop(value);
                    }}
                  />
                  <Field
                    label="Take profit"
                    value={simTakeProfit}
                    onChange={(value) => {
                      setSimTpSlMode("manual");
                      setSimTakeProfit(value);
                    }}
                  />
                </div>

                <div className="mt-4 rounded-[16px] border border-[color:var(--radar-line)] bg-black/15 p-3 text-xs leading-5 text-[var(--radar-muted)]">
                  {simTpSlMode === "fib"
                    ? "Fib Auto is active. The distance simulator below uses exactly the Stop Loss and Take Profit fields shown here."
                    : "Manual TP/SL is active. The distance simulator below uses your stop loss plus the exit price you typed above."}
                </div>
              </div>

              <div className="mt-4 rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="radar-chip">Fibonacci TP / SL layer</div>
                    <p className="mt-2 text-xs leading-5 text-[var(--radar-muted)]">{fibStatus}</p>
                    {fibLevels?.updatedAt ? (
                      <p className="mt-1 text-xs text-[var(--radar-muted)]">Updated {fibLevels.updatedAt} Montreal time</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(["5m", "15m", "1h", "4h"] as FibTimeframe[]).map((timeframe) => (
                      <button
                        className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                          fibTimeframe === timeframe ? "bg-[var(--radar-sea)] text-black" : "bg-[var(--radar-panel-soft)] text-[var(--radar-muted)] hover:text-[var(--radar-ink)]"
                        }`}
                        key={timeframe}
                        onClick={() => setFibTimeframe(timeframe)}
                        type="button"
                      >
                        {timeframe}
                      </button>
                    ))}
                  </div>
                </div>

                {fibLevels ? (
                  <>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <Result label="Swing low" value={formatPrice(fibLevels.swingLow)} />
                      <Result label="Swing high" value={formatPrice(fibLevels.swingHigh)} />
                      <Result label="Range" value={formatPrice(fibLevels.swingHigh - fibLevels.swingLow)} />
                      <Result label="Fib 0.618" value={formatPrice(fibLevels.retrace618)} tone="warn" />
                      <Result label="TP 1.272" value={formatPrice(fibLevels.extension1272)} tone="good" />
                      <Result label="TP 1.618" value={formatPrice(fibLevels.extension1618)} tone="good" />
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <button
                        className="rounded-[16px] border border-[color:var(--radar-line)] px-3 py-3 text-xs font-semibold text-[var(--radar-muted)] transition hover:border-[color:var(--radar-line-strong)] hover:text-[var(--radar-ink)]"
                        onClick={() => {
                          setSimTpSlMode("fib");
                          const levels = fibTicketLevels(fibLevels, simSide, n(simEntry), "conservative");
                          if (levels.stop) {
                            setSimStop(formatTradePrice(levels.stop));
                          }
                          if (levels.takeProfit) {
                            setSimTakeProfit(formatTradePrice(levels.takeProfit));
                          }
                        }}
                        type="button"
                      >
                        Conservative
                      </button>
                      <button
                        className="rounded-[16px] bg-[var(--radar-sea)] px-3 py-3 text-xs font-semibold text-black transition hover:brightness-110"
                        onClick={() => {
                          setSimTpSlMode("fib");
                          const levels = fibTicketLevels(fibLevels, simSide, n(simEntry), "standard");
                          if (levels.stop) {
                            setSimStop(formatTradePrice(levels.stop));
                          }
                          if (levels.takeProfit) {
                            setSimTakeProfit(formatTradePrice(levels.takeProfit));
                          }
                        }}
                        type="button"
                      >
                        Apply Standard
                      </button>
                      <button
                        className="rounded-[16px] border border-[color:var(--radar-line)] px-3 py-3 text-xs font-semibold text-[var(--radar-muted)] transition hover:border-[color:var(--radar-line-strong)] hover:text-[var(--radar-ink)]"
                        onClick={() => {
                          setSimTpSlMode("fib");
                          const levels = fibTicketLevels(fibLevels, simSide, n(simEntry), "aggressive");
                          if (levels.stop) {
                            setSimStop(formatTradePrice(levels.stop));
                          }
                          if (levels.takeProfit) {
                            setSimTakeProfit(formatTradePrice(levels.takeProfit));
                          }
                        }}
                        type="button"
                      >
                        Aggressive
                      </button>
                    </div>
                  </>
                ) : null}
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <button
                  className="rounded-[16px] bg-emerald-400 px-4 py-3 text-sm font-semibold text-black transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!canOpenSimulatedTrade}
                  onClick={() => {
                    const fillPrice = n(simEntry);
                    const marginAmount = n(simMargin);
                    if (!canOpenSimulatedTrade) {
                      setTradeNotification(hasOpenSimulatedTrade ? "Close the current simulated trade before opening another one." : "Not enough practice cash or invalid trade inputs.");
                      return;
                    }
                    setPracticeCash((cash) => cash - marginAmount);
                    setSimPosition({
                      side: simSide,
                      symbol: simSymbol,
                      entryType: simEntryType,
                      entry: fillPrice,
                      margin: marginAmount,
                      leverage: n(simLeverage),
                      orderType: simulatorOrderType,
                      stopLoss: n(simStop),
                      takeProfit: n(simTakeProfit),
                      openedAt: new Date().toLocaleString("en-CA", { timeZone: "America/Toronto" }),
                    });
                    setTradeNotification(`${simEntryType.toUpperCase()} ${simSide.toUpperCase()} ${simSymbol} opened at ${formatPrice(fillPrice)} with ${formatCurrency(marginAmount)} reserved.`);
                  }}
                  type="button"
                >
                  Open Simulated Trade
                </button>
                <button
                  className="rounded-[16px] border border-[color:var(--radar-line)] px-4 py-3 text-sm font-semibold text-[var(--radar-muted)] transition hover:border-[color:var(--radar-line-strong)] hover:text-[var(--radar-ink)] disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={hasOpenSimulatedTrade}
                  onClick={() => setSimPosition(null)}
                  type="button"
                >
                  Reset Ticket
                </button>
              </div>

              <div className="mt-4 rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
                <div>
                  <div>
                    <div className="radar-chip">SL / TP Distance Simulator</div>
                    <p className="mt-2 text-xs leading-5 text-[var(--radar-muted)]">
                      Projection-only calculator. It reads entry, margin, leverage, and optional SL/TP fields only. It does not open, reset, or manage trades.
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <SegmentButton active={projectionMode === "fib"} onClick={() => setProjectionMode("fib")}>Use Fib levels</SegmentButton>
                  <SegmentButton active={projectionMode === "ticket"} onClick={() => setProjectionMode("ticket")}>Use ticket fields</SegmentButton>
                  <SegmentButton active={projectionMode === "custom"} onClick={() => setProjectionMode("custom")}>Use own SL/TP</SegmentButton>
                </div>

                {projectionMode === "custom" ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <Field label="Projection stop loss" value={projectionStop} onChange={setProjectionStop} />
                    <Field label="Projection take profit" value={projectionTakeProfit} onChange={setProjectionTakeProfit} />
                  </div>
                ) : null}

                <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_220px] lg:items-end">
                  <div>
                    <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">
                      <span>100% to {whatIfValues.leftLabel}</span>
                      <span>Entry</span>
                      <span>100% to {whatIfValues.rightLabel}</span>
                    </div>
                    <input
                      className="mt-3 h-2 w-full cursor-pointer accent-[var(--radar-sea)] disabled:cursor-not-allowed disabled:opacity-40"
                      disabled={!whatIfValues.validRange}
                      max="100"
                      min="-100"
                      onChange={(event) => {
                        setSimWhatIfPct(String(clamp(Number(event.target.value), -100, 100)));
                      }}
                      step="1"
                      type="range"
                      value={whatIfValues.pathPct}
                    />
                    <div className="mt-2 flex items-center justify-between text-xs text-[var(--radar-muted)]">
                      <span>
                        {whatIfValues.leftLabel} {formatPrice(whatIfValues.leftPrice)}
                        {whatIfValues.active.side === "long" && whatIfValues.liquidation > 0 ? (
                          <span className="block text-amber-300">Liq est {formatPrice(whatIfValues.liquidation)}</span>
                        ) : null}
                      </span>
                      <span className="font-semibold text-[var(--radar-ink)]">
                        {whatIfValues.validRange ? whatIfValues.pathLabel : "Waiting for valid SL/TP"}
                      </span>
                      <span className="text-right">
                        {whatIfValues.rightLabel} {formatPrice(whatIfValues.rightPrice)}
                        {whatIfValues.active.side === "short" && whatIfValues.liquidation > 0 ? (
                          <span className="block text-amber-300">Liq est {formatPrice(whatIfValues.liquidation)}</span>
                        ) : null}
                      </span>
                    </div>
                  </div>
                  <Field
                    label="Distance %"
                    max="100"
                    min="-100"
                    step="1"
                    suffix="%"
                    value={simWhatIfPct}
                    onChange={(value) => setSimWhatIfPct(String(clamp(n(value), -100, 100)))}
                  />
                </div>

                {whatIfValues.validRange ? (
                  <>
                    {whatIfValues.liquidationWarning ? (
                      <div className="mt-4 rounded-[16px] border border-amber-300/25 bg-amber-400/10 p-3 text-sm text-amber-100">
                        {whatIfValues.liquidationWarning}
                      </div>
                    ) : null}
                    <div className="mt-4 grid gap-3 sm:grid-cols-4">
                      <Result label="Projected exit" value={formatPrice(whatIfValues.price)} />
                      <Result label="Net PnL" value={formatCurrency(whatIfValues.net)} tone={whatIfValues.net >= 0 ? "good" : "bad"} />
                      <Result label="ROI" value={pct(whatIfValues.roi)} tone={whatIfValues.roi >= 0 ? "good" : "bad"} />
                      <Result label="Move from entry" value={pct(whatIfValues.movePct)} tone={whatIfValues.movePct * sideMultiplier(whatIfValues.active.side) >= 0 ? "good" : "bad"} />
                    </div>
                  </>
                ) : (
                  <div className="mt-4 rounded-[16px] border border-amber-300/25 bg-amber-400/10 p-3 text-sm text-amber-100">
                    {whatIfValues.rangeWarning}
                  </div>
                )}
              </div>
            </div>

            <div className={`rounded-[22px] border p-4 ${
              !hasOpenSimulatedTrade
                ? "border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.5)]"
                : simValues.net >= 0
                  ? "border-emerald-400/40 bg-emerald-950/25"
                  : "border-rose-400/40 bg-rose-950/25"
            }`}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">{simValues.active.symbol}</div>
                  <div className="mt-1 text-xl font-semibold text-[var(--radar-ink)]">{simValues.status}</div>
                </div>
                <div className={`text-right text-2xl font-semibold ${
                  !hasOpenSimulatedTrade ? "text-[var(--radar-muted)]" : displayedPositionNet >= 0 ? "text-emerald-300" : "text-rose-300"
                }`}>
                  {hasOpenSimulatedTrade ? formatCurrency(displayedPositionNet) : "No active trade"}
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <Result label="ROI" value={pct(displayedPositionRoi)} tone={displayedPositionRoi >= 0 ? "good" : "bad"} />
                <Result label="Liquidation estimate" value={formatPrice(simValues.liquidation)} tone="warn" />
                <Result label="Position value" value={formatCurrency(simValues.notional)} />
                <Result label="Fees" value={formatCurrency(displayedPositionFees)} tone="warn" />
              </div>
              <div className="mt-4 rounded-[16px] border border-[color:var(--radar-line)] bg-black/15 p-3 text-xs leading-5 text-[var(--radar-muted)]">
                {simPosition
                  ? `Opened ${simPosition.entryType.toUpperCase()} ${simPosition.side.toUpperCase()} at ${formatPrice(simPosition.entry)} on ${simPosition.openedAt}.`
                  : "Set your entry, stop, take profit, margin, and leverage, then open a simulated trade."}
              </div>
              {hasOpenSimulatedTrade ? (
                <button
                  className="mt-4 w-full rounded-[16px] bg-[var(--radar-sea)] px-4 py-3 text-sm font-semibold text-black transition hover:brightness-110"
                  onClick={() => {
                    const settledAmount = simValues.active.margin + simValues.net;
                    setPracticeCash((cash) => cash + settledAmount);
                    setTradeNotification(
                      `${simValues.active.symbol} closed at ${formatPrice(simValues.current)}. Realized ${formatCurrency(simValues.net)}. Practice cash updated.`
                    );
                    setSimPosition(null);
                  }}
                  type="button"
                >
                  Close and Settle Simulated Trade
                </button>
              ) : null}

              <div className="mt-5 border-t border-[color:var(--radar-line)] pt-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="radar-chip">AI Trading Coach</div>
                    <h3 className="mt-3 text-lg font-semibold text-[var(--radar-ink)]">Entry, exit, and strategy analysis</h3>
                    <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">
                      Uses the simulator ticket, live candle context, risk fields, and Fibonacci layer. It explains possible plans only.
                    </p>
                  </div>
                  <button
                    className="rounded-[16px] bg-[var(--radar-sea)] px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={coachLoading}
                    onClick={runCoachAnalysis}
                    type="button"
                  >
                    {coachLoading ? "Analyzing..." : "Analyze Setup"}
                  </button>
                </div>

                <div className="mt-4 rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">{coachStatus}</div>
                  {coachWarnings.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {coachWarnings.map((warning) => (
                        <span className="rounded-full border border-amber-300/25 bg-amber-400/10 px-3 py-1 text-xs font-semibold text-amber-100" key={warning}>
                          {warning}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <pre className="mt-4 max-h-[360px] min-h-48 overflow-auto whitespace-pre-wrap rounded-[16px] border border-[color:var(--radar-line)] bg-black/20 p-4 text-sm leading-7 text-[var(--radar-ink)]">
                    {coachAnalysis || "Click Analyze Setup to generate a trading-coach readout with market context, possible long/short plans, invalidation, risk warnings, and no-trade conditions."}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="radar-card p-5 sm:p-6">
        <div className="mb-4">
          <div className="radar-chip">Calculator toolkit</div>
          <h2 className="mt-3 text-2xl font-semibold text-[var(--radar-ink)]">Futures planning calculators</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {tabs.map((item) => (
            <button
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                tab === item.id ? "bg-[var(--radar-sea)] text-black" : "bg-[var(--radar-panel-soft)] text-[var(--radar-muted)] hover:text-[var(--radar-ink)]"
              }`}
              key={item.id}
              onClick={() => setTab(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="radar-card p-5 sm:p-6">
          <div className="radar-chip">Inputs</div>
          <div className="mt-5 flex flex-wrap gap-2">
            <SegmentButton active={side === "long"} onClick={() => setSide("long")}>Long</SegmentButton>
            <SegmentButton active={side === "short"} onClick={() => setSide("short")}>Short</SegmentButton>
            <SegmentButton active={calculatorOrderType === "maker"} onClick={() => setCalculatorOrderType("maker")}>Maker</SegmentButton>
            <SegmentButton active={calculatorOrderType === "taker"} onClick={() => setCalculatorOrderType("taker")}>Taker</SegmentButton>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Field label="Entry price" value={entry} onChange={setEntry} />
            <Field label="Exit price" value={exit} onChange={setExit} />
            <Field label="Margin" value={margin} onChange={setMargin} suffix="USDT" />
            <Field label="Leverage" value={leverage} onChange={setLeverage} suffix="x" />
            <Field label="Maker fee" value={makerFee} onChange={setMakerFee} suffix="%" />
            <Field label="Taker fee" value={takerFee} onChange={setTakerFee} suffix="%" />
            <Field label="Funding rate" value={fundingRate} onChange={setFundingRate} suffix="%" min="-100" />
            <Field label="Funding settlements" value={fundingSettlements} onChange={setFundingSettlements} />
          </div>

          <div className="mt-5 rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4 text-sm leading-6 text-[var(--radar-muted)]">
            Pionex defaults used here: futures maker fee <span className="font-semibold text-[var(--radar-ink)]">0.02%</span>,
            taker fee <span className="font-semibold text-[var(--radar-ink)]">0.05%</span>. Fees are charged on notional
            position value, not just margin. Funding may be paid or received depending on the live funding rate.
          </div>
        </div>

        <div className="radar-card p-5 sm:p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="radar-chip">Outputs</div>
              <h2 className="mt-3 text-2xl font-semibold text-[var(--radar-ink)]">{tabs.find((item) => item.id === tab)?.label}</h2>
            </div>
          </div>

          {tab === "pnl" ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <Result label="Gross PnL" value={formatCurrency(values.gross)} tone={values.gross >= 0 ? "good" : "bad"} />
              <Result label="Net PnL" value={formatCurrency(values.net)} tone={values.net >= 0 ? "good" : "bad"} />
              <Result label="ROI" value={pct(values.roi)} tone={values.roi >= 0 ? "good" : "bad"} />
              <Result label="Final balance" value={formatCurrency(values.finalBalance)} />
              <Result label="Position value" value={formatCurrency(values.notional)} />
              <Result label="Quantity" value={values.quantity.toFixed(6)} />
            </div>
          ) : null}

          {tab === "liquidation" ? (
            <div className="mt-5 space-y-4">
              <Field label="Maintenance margin" value={maintenanceMargin} onChange={setMaintenanceMargin} suffix="%" />
              <div className="grid gap-3 sm:grid-cols-2">
                <Result label="Estimated liquidation" value={formatPrice(values.liquidation)} tone="bad" />
                <Result label="Distance to liquidation" value={pct(values.liquidationDistance)} tone="warn" />
              </div>
            </div>
          ) : null}

          {tab === "position" ? (
            <div className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Account balance" value={accountBalance} onChange={setAccountBalance} suffix="USDT" />
                <Field label="Risk" value={riskPct} onChange={setRiskPct} suffix="%" />
                <Field label="Stop distance" value={stopLossPct} onChange={setStopLossPct} suffix="%" />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Result label="Maximum loss" value={formatCurrency(values.riskAmount)} tone="bad" />
                <Result label="Recommended position value" value={formatCurrency(values.positionByRisk)} />
                <Result label="Recommended leverage vs current margin" value={`${values.recommendedLeverage.toFixed(2)}x`} />
              </div>
            </div>
          ) : null}

          {tab === "riskReward" ? (
            <div className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Entry" value={entry} onChange={setEntry} />
                <Field label="Stop loss" value={stopPrice} onChange={setStopPrice} />
                <Field label="Take profit" value={takeProfitPrice} onChange={setTakeProfitPrice} />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Result label="Risk" value={pct(values.stopRiskPct)} tone="bad" />
                <Result label="Reward" value={pct(values.rewardPct)} tone="good" />
                <Result label="Risk:Reward" value={`1:${values.rr.toFixed(2)}`} tone={values.rr >= 2 ? "good" : "warn"} />
              </div>
            </div>
          ) : null}

          {tab === "targets" ? (
            <div className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Max acceptable loss" value={targetLoss} onChange={setTargetLoss} suffix="USDT" />
                <Field label="Desired profit" value={targetProfit} onChange={setTargetProfit} suffix="USDT" />
                <Field label="Desired ROI" value={desiredProfitPct} onChange={setDesiredProfitPct} suffix="%" />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Result label="Suggested stop loss" value={formatPrice(values.suggestedStop)} tone="bad" />
                <Result label="TP for desired profit" value={formatPrice(values.tpByProfit)} tone="good" />
                <Result label="TP for desired ROI" value={formatPrice(values.tpByPercent)} tone="good" />
              </div>
            </div>
          ) : null}

          {tab === "dca" ? (
            <div className="mt-5 space-y-4">
              <div className="space-y-3">
                {dcaRows.map((row, index) => (
                  <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]" key={index}>
                    <Field label={`Buy ${index + 1} price`} value={row.price} onChange={(value) => setDcaRows((rows) => rows.map((item, rowIndex) => rowIndex === index ? { ...item, price: value } : item))} />
                    <Field label="Investment" value={row.amount} onChange={(value) => setDcaRows((rows) => rows.map((item, rowIndex) => rowIndex === index ? { ...item, amount: value } : item))} suffix="USDT" />
                    <button className="rounded-[16px] border border-[color:var(--radar-line)] px-4 text-sm font-semibold text-[var(--radar-muted)] transition hover:text-[var(--radar-ink)]" onClick={() => setDcaRows((rows) => rows.filter((_, rowIndex) => rowIndex !== index))} type="button">Remove</button>
                  </div>
                ))}
              </div>
              <button className="rounded-full bg-[var(--radar-sea)] px-4 py-2 text-sm font-semibold text-black" onClick={() => setDcaRows((rows) => [...rows, { price: "", amount: "" }])} type="button">Add DCA row</button>
              <div className="grid gap-3 sm:grid-cols-3">
                <Result label="Average entry" value={formatPrice(values.averageEntry)} />
                <Result label="Total investment" value={formatCurrency(values.dcaInvestment)} />
                <Result label="Total quantity" value={values.dcaQuantity.toFixed(6)} />
              </div>
            </div>
          ) : null}

          {tab === "fees" ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <Result label="Opening fee" value={formatCurrency(values.fees.openingFee)} />
              <Result label="Closing fee" value={formatCurrency(values.fees.closingFee)} />
              <Result label="Funding fee estimate" value={formatCurrency(values.fees.fundingFee)} tone={values.fees.fundingFee > 0 ? "bad" : "good"} />
              <Result label="Total fees" value={formatCurrency(values.fees.totalFees)} tone="warn" />
              <Result label="Breakeven price" value={formatPrice(values.breakeven)} />
              <Result label="Net profit after fees" value={formatCurrency(values.net)} tone={values.net >= 0 ? "good" : "bad"} />
            </div>
          ) : null}

          {tab === "compound" ? (
            <div className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Initial capital" value={compoundCapital} onChange={setCompoundCapital} suffix="USDT" />
                <Field label="Daily gain" value={dailyGain} onChange={setDailyGain} suffix="%" />
                <Field label="Days" value={compoundDays} onChange={setCompoundDays} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Result label="Final capital" value={formatCurrency(values.compounded)} tone="good" />
                <Result label="Total growth" value={pct(n(compoundCapital) > 0 ? ((values.compounded - n(compoundCapital)) / n(compoundCapital)) * 100 : 0)} tone="good" />
              </div>
              <div className="grid grid-cols-6 items-end gap-2 rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
                {Array.from({ length: 6 }).map((_, index) => {
                  const days = Math.round((n(compoundDays) / 5) * index);
                  const capital = n(compoundCapital) * (1 + n(dailyGain) / 100) ** days;
                  const height = clamp((capital / Math.max(values.compounded, 1)) * 120, 8, 120);
                  return (
                    <div className="flex flex-col items-center gap-2" key={index}>
                      <div className="w-full rounded-t bg-[var(--radar-sea)]" style={{ height }} />
                      <div className="text-[10px] text-[var(--radar-muted)]">D{days}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {tab === "scenario" ? (
            <div className="mt-5 space-y-4">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">Scenario exit price</span>
                <input
                  className="mt-4 w-full accent-[var(--radar-sea)]"
                  max={String(Math.max(n(entry) * 1.8, n(entry) + 1))}
                  min={String(Math.max(n(entry) * 0.2, 0))}
                  onChange={(event) => setScenarioPrice(event.target.value)}
                  step="any"
                  type="range"
                  value={scenarioPrice}
                />
              </label>
              <Field label="Scenario price" value={scenarioPrice} onChange={setScenarioPrice} />
              <div className="grid gap-3 sm:grid-cols-3">
                <Result label="Scenario gross PnL" value={formatCurrency(values.scenarioGross)} tone={values.scenarioGross >= 0 ? "good" : "bad"} />
                <Result label="Scenario net PnL" value={formatCurrency(values.scenarioNet)} tone={values.scenarioNet >= 0 ? "good" : "bad"} />
                <Result label="Scenario ROI" value={pct(values.scenarioRoi)} tone={values.scenarioRoi >= 0 ? "good" : "bad"} />
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </AppFrame>
  );
}
