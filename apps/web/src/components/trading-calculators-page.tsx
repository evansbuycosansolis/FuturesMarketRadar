"use client";

import { useMemo, useState } from "react";

import { AppFrame } from "@/components/app-frame";
import { formatCurrency, formatPrice } from "@/lib/formatters";

type Side = "long" | "short";
type OrderType = "maker" | "taker";
type CalculatorTab = "pnl" | "liquidation" | "position" | "riskReward" | "targets" | "dca" | "fees" | "compound" | "scenario";

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

function Field({ label, value, onChange, suffix, min = "0", step = "any" }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  suffix?: string;
  min?: string;
  step?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--radar-muted)]">{label}</span>
      <span className="mt-2 flex items-center rounded-[16px] border border-[color:var(--radar-line)] bg-black/20 px-3 transition focus-within:border-[color:var(--radar-sea)] hover:border-[color:var(--radar-line-strong)]">
        <input
          className="min-w-0 flex-1 bg-transparent py-3 text-sm font-semibold text-[var(--radar-ink)] outline-none"
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

export function TradingCalculatorsPage() {
  const [tab, setTab] = useState<CalculatorTab>("pnl");
  const [side, setSide] = useState<Side>("long");
  const [orderType, setOrderType] = useState<OrderType>("taker");
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
  const [dcaRows, setDcaRows] = useState([
    { price: "0.10", amount: "50" },
    { price: "0.09", amount: "50" },
    { price: "0.08", amount: "100" },
  ]);

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
      orderType,
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
      orderType,
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
  }, [accountBalance, compoundCapital, compoundDays, dailyGain, dcaRows, desiredProfitPct, entry, exit, fundingRate, fundingSettlements, leverage, maintenanceMargin, makerFee, margin, orderType, riskPct, scenarioPrice, side, stopLossPct, stopPrice, takerFee, takeProfitPrice, targetLoss, targetProfit]);

  return (
    <AppFrame
      current="calculators"
      title="Trading calculators for futures decisions."
      subtitle="Estimate PnL, liquidation, position sizing, fees, breakeven, DCA average, compounding, and trade scenarios before touching execution."
    >
      <section className="radar-card p-5 sm:p-6">
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
            <SegmentButton active={orderType === "maker"} onClick={() => setOrderType("maker")}>Maker</SegmentButton>
            <SegmentButton active={orderType === "taker"} onClick={() => setOrderType("taker")}>Taker</SegmentButton>
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
