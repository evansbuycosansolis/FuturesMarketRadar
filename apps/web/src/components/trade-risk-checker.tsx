"use client";

import { useState, useTransition } from "react";

import { armManagedExit, checkTradeRisk, placeTradeOrder, planTrade } from "@/lib/api";
import { formatCurrency, formatPercent, formatSignedNumber } from "@/lib/formatters";
import { ArmManagedExitResponse, OrderExecutionResponse, TradeCheckRequest, TradeCheckResponse, TradePlanResponse } from "@/lib/types";

type TradeRiskCheckerProps = {
  defaultSymbol?: string;
};

type FormState = {
  symbol: string;
  side: "BUY" | "SELL";
  size: string;
  entry_price: string;
  stop_price: string;
  take_profit_price: string;
  order_type: "LIMIT" | "MARKET_QTY" | "IOC" | "FOK" | "POSTONLY";
  position_side: "BOTH" | "LONG" | "SHORT";
  planned_leverage: string;
  reduce_only: boolean;
  arm_exit_automation: boolean;
  client_order_id: string;
};

function emptyToNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined;
  }
  return Number(value);
}

function buildPayload(form: FormState): TradeCheckRequest {
  return {
    symbol: form.symbol.trim().toUpperCase(),
    side: form.side,
    size: Number(form.size),
    entry_price: Number(form.entry_price),
    stop_price: emptyToNumber(form.stop_price),
    order_type: form.order_type,
    position_side: form.position_side,
    planned_leverage: emptyToNumber(form.planned_leverage),
    reduce_only: form.reduce_only,
  };
}

function toneClass(passed: boolean): string {
  return passed
    ? "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] text-emerald-200"
    : "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)] text-rose-200";
}

export function TradeRiskChecker({ defaultSymbol = "" }: TradeRiskCheckerProps) {
  const [isPending, startTransition] = useTransition();
  const [isPlanning, startPlanning] = useTransition();
  const [isExecuting, startExecution] = useTransition();
  const [isArmingExisting, startArmingExisting] = useTransition();
  const [form, setForm] = useState<FormState>({
    symbol: defaultSymbol,
    side: "BUY",
    size: "",
    entry_price: "",
    stop_price: "",
    take_profit_price: "",
    order_type: "LIMIT",
    position_side: "BOTH",
    planned_leverage: "3",
    reduce_only: false,
    arm_exit_automation: true,
    client_order_id: "",
  });
  const [result, setResult] = useState<TradeCheckResponse | null>(null);
  const [plan, setPlan] = useState<TradePlanResponse | null>(null);
  const [message, setMessage] = useState("");
  const [execution, setExecution] = useState<OrderExecutionResponse | null>(null);
  const [armedExisting, setArmedExisting] = useState<ArmManagedExitResponse | null>(null);

  function updateField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function handleCheck() {
    setMessage("");
    setExecution(null);
    startTransition(async () => {
      try {
        const response = await checkTradeRisk(buildPayload(form));
        setResult(response);
      } catch (error) {
        setResult(null);
        setMessage(error instanceof Error ? error.message : "Risk check failed.");
      }
    });
  }

  function handlePlan() {
    setMessage("");
    setExecution(null);
    startPlanning(async () => {
      try {
        const response = await planTrade({
          symbol: form.symbol.trim().toUpperCase(),
          side: form.side,
          entry_price: emptyToNumber(form.entry_price),
          size: emptyToNumber(form.size),
          planned_leverage: emptyToNumber(form.planned_leverage),
        });
        setPlan(response);
        setForm((current) => ({
          ...current,
          symbol: response.symbol,
          entry_price: response.entry_price.toFixed(8).replace(/0+$/, "").replace(/\.$/, ""),
          stop_price: response.stop_price.toFixed(8).replace(/0+$/, "").replace(/\.$/, ""),
          take_profit_price: response.take_profit_price.toFixed(8).replace(/0+$/, "").replace(/\.$/, ""),
          size:
            current.size.trim() === "" && response.suggested_size
              ? response.suggested_size.toFixed(6).replace(/0+$/, "").replace(/\.$/, "")
              : current.size,
        }));
        setMessage("Stop loss and take profit were auto-filled from the current risk plan.");
      } catch (error) {
        setPlan(null);
        setMessage(error instanceof Error ? error.message : "Auto-plan failed.");
      }
    });
  }

  function handleExecute() {
    setMessage("");
    startExecution(async () => {
      try {
        const response = await placeTradeOrder({
          ...buildPayload(form),
          client_order_id: form.client_order_id.trim() || undefined,
          take_profit_price: emptyToNumber(form.take_profit_price),
          arm_exit_automation: form.arm_exit_automation,
        });
        setExecution(response);
        setArmedExisting(null);
        setResult(response.check);
        setMessage(response.message);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Order placement failed.");
      }
    });
  }

  function handleArmExistingPosition() {
    setMessage("");
    startArmingExisting(async () => {
      try {
        const response = await armManagedExit({
          symbol: form.symbol.trim().toUpperCase(),
          side: form.side,
          stop_price: Number(form.stop_price),
          take_profit_price: Number(form.take_profit_price),
          position_side: "BOTH",
          entry_price: emptyToNumber(form.entry_price),
          expected_size: emptyToNumber(form.size),
        });
        setArmedExisting(response);
        setExecution(null);
        setMessage(response.message);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Arming existing position failed.");
      }
    });
  }

  return (
    <section className="radar-card p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">Pre-Trade Gate</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Check the trade before the exchange ever sees it</h2>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--radar-muted)]">
            Size, stop, leverage, heat, symbol concentration, and current market state all get evaluated here first.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex items-center justify-center rounded-full border border-[color:rgba(46,183,154,0.3)] bg-[rgba(18,58,49,0.42)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sun)] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isPlanning}
            onClick={handlePlan}
            type="button"
          >
            {isPlanning ? "Planning..." : "Auto-set SL / TP"}
          </button>
          <button
            className="inline-flex items-center justify-center rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sea)] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isPending}
            onClick={handleCheck}
            type="button"
          >
            {isPending ? "Checking..." : "Check Trade"}
          </button>
          <button
            className="inline-flex items-center justify-center rounded-full border border-[color:rgba(108,152,255,0.24)] bg-[rgba(20,30,54,0.4)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sea)] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={
              isArmingExisting ||
              form.position_side !== "BOTH" ||
              !form.symbol.trim() ||
              !form.stop_price.trim() ||
              !form.take_profit_price.trim()
            }
            onClick={handleArmExistingPosition}
            type="button"
          >
            {isArmingExisting ? "Arming..." : "Arm Existing Position"}
          </button>
          <button
            className="inline-flex items-center justify-center rounded-full bg-[var(--radar-ink)] px-4 py-2 text-sm font-semibold text-[#05110f] transition hover:-translate-y-0.5 hover:bg-[var(--radar-sun)] disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!result?.allowed || !result.execution_available || isExecuting}
            onClick={handleExecute}
            type="button"
          >
            {isExecuting ? "Placing..." : "Place Order"}
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Symbol</span>
          <input
            className="w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => updateField("symbol", event.target.value)}
            placeholder="BTC_USDT_PERP"
            value={form.symbol}
          />
        </label>
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Client Order ID</span>
          <input
            className="w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => updateField("client_order_id", event.target.value)}
            placeholder="optional-manual-id"
            value={form.client_order_id}
          />
        </label>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Side</span>
          <select
            className="w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => updateField("side", event.target.value as FormState["side"])}
            value={form.side}
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Order Type</span>
          <select
            className="w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => updateField("order_type", event.target.value as FormState["order_type"])}
            value={form.order_type}
          >
            <option value="LIMIT">LIMIT</option>
            <option value="MARKET_QTY">MARKET_QTY</option>
            <option value="IOC">IOC</option>
            <option value="FOK">FOK</option>
            <option value="POSTONLY">POSTONLY</option>
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Position Side</span>
          <select
            className="w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => updateField("position_side", event.target.value as FormState["position_side"])}
            value={form.position_side}
          >
            <option value="BOTH">BOTH</option>
            <option value="LONG">LONG</option>
            <option value="SHORT">SHORT</option>
          </select>
        </label>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-5">
        {[
          ["size", "Size"],
          ["entry_price", "Entry"],
          ["stop_price", "Stop"],
          ["take_profit_price", "Take Profit"],
          ["planned_leverage", "Leverage"],
        ].map(([field, label]) => (
          <label key={field} className="space-y-2">
            <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</span>
            <input
              className="w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
              min={0}
              onChange={(event) => updateField(field as keyof FormState, event.target.value)}
              step="0.0001"
              type="number"
              value={form[field as keyof FormState] as string}
            />
          </label>
        ))}
      </div>

      <label className="mt-4 flex items-center justify-between rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3">
        <span className="text-sm font-medium text-[var(--radar-ink)]">Reduce Only</span>
        <input
          checked={form.reduce_only}
          className="h-4 w-4 accent-[var(--radar-sea)]"
          onChange={(event) => updateField("reduce_only", event.target.checked)}
          type="checkbox"
        />
      </label>

      <label className="mt-3 flex items-center justify-between rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3">
        <div className="space-y-1">
          <span className="text-sm font-medium text-[var(--radar-ink)]">Arm Live Exit Automation</span>
          <p className="text-xs leading-6 text-[var(--radar-muted)]">
            Uses reduce-only market exits after entry. Supported only in one-way `BOTH` mode.
          </p>
        </div>
        <input
          checked={form.arm_exit_automation}
          className="h-4 w-4 accent-[var(--radar-sea)]"
          disabled={form.position_side !== "BOTH"}
          onChange={(event) => updateField("arm_exit_automation", event.target.checked)}
          type="checkbox"
        />
      </label>

      {form.position_side !== "BOTH" ? (
        <div className="mt-3 rounded-[18px] border border-[color:rgba(244,173,61,0.2)] bg-[rgba(80,54,15,0.34)] px-4 py-3 text-sm leading-7 text-amber-100">
          Live exit automation is intentionally disabled here because Pionex currently documents `reduceOnly` for one-way mode, not hedge mode.
        </div>
      ) : null}

      {message ? <p className="mt-4 text-sm leading-7 text-[var(--radar-muted)]">{message}</p> : null}

      {plan ? (
        <div className="mt-4 rounded-[24px] border border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.34)] p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Auto Trade Plan</div>
              <h3 className="mt-2 text-xl font-semibold tracking-tight text-[var(--radar-ink)]">
                {plan.symbol} {plan.side} at {formatCurrency(plan.entry_price)}
              </h3>
            </div>
            <div className="grid gap-1 text-sm text-[var(--radar-ink)] sm:text-right">
              <div>{plan.risk_reward_ratio.toFixed(2)}R target</div>
              <div>ATR: {formatPercent(plan.atr_percent)}</div>
              <div>Stop distance: {formatPercent(plan.stop_distance_pct)}</div>
            </div>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-4">
            {[
              ["Entry", formatCurrency(plan.entry_price)],
              ["Stop", formatCurrency(plan.stop_price)],
              ["Take Profit", formatCurrency(plan.take_profit_price)],
              ["Suggested Size", plan.suggested_size ? plan.suggested_size.toFixed(6) : "n/a"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-[20px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.42)] p-4">
                <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
                <div className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">{value}</div>
              </div>
            ))}
          </div>

          <div className="mt-4 space-y-2 text-sm leading-7 text-[var(--radar-ink)]">
            {plan.notes.map((note) => (
              <div key={note}>• {note}</div>
            ))}
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="mt-6 space-y-5">
          <div className={`rounded-[24px] border p-5 ${result.allowed ? "border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)]" : "border-[color:rgba(255,126,115,0.24)] bg-[rgba(74,23,19,0.42)]"}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Decision</div>
                <h3 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">
                  {result.allowed ? "Allowed by policy" : "Blocked by policy"}
                </h3>
              </div>
              <div className="grid gap-2 text-sm text-[var(--radar-ink)] sm:text-right">
                <div>Risk: {formatCurrency(result.estimated_risk_amount)}</div>
                <div>Risk %: {formatPercent(result.estimated_risk_pct)}</div>
                <div>Projected heat: {formatPercent(result.estimated_portfolio_heat_pct)}</div>
              </div>
            </div>
            {result.blocked_reasons.length > 0 ? (
              <div className="mt-4 space-y-2 text-sm leading-7 text-[var(--radar-ink)]">
                {result.blocked_reasons.map((reason) => (
                  <div key={reason}>• {reason}</div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            {[
              ["Notional", formatCurrency(result.estimated_position_notional)],
              ["Margin", formatCurrency(result.estimated_margin_required)],
              ["Symbol Exposure", formatPercent(result.estimated_symbol_exposure_pct)],
              ["Stop Buffer", formatPercent(result.stop_distance_pct)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-[22px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-4">
                <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
                <div className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">{value}</div>
              </div>
            ))}
          </div>

          {result.market_context ? (
            <div className="rounded-[24px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] p-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Market Context</div>
                  <h3 className="mt-2 text-xl font-semibold tracking-tight text-[var(--radar-ink)]">{result.market_context.symbol}</h3>
                </div>
                <div className="text-sm text-[var(--radar-muted)]">{result.market_context.trend_label}</div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {[
                  ["Activity", result.market_context.activity_score],
                  ["Bullish", result.market_context.bullish_score],
                  ["Bearish", result.market_context.bearish_score],
                  ["Buyers Left", result.market_context.buyer_absence_score],
                  ["Dead Market", result.market_context.dead_market_score],
                  ["Quiet -> Rally", result.market_context.quiet_rally_score],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.48)] p-3">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--radar-muted)]">{label}</div>
                    <div className="mt-2 text-xl font-semibold text-[var(--radar-ink)]">{formatSignedNumber(value as number, 1)}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {result.warnings.length > 0 ? (
            <div className="rounded-[24px] border border-[color:rgba(244,173,61,0.2)] bg-[rgba(80,54,15,0.34)] p-5 text-sm leading-7 text-amber-100">
              {result.warnings.map((warning) => (
                <div key={warning}>• {warning}</div>
              ))}
            </div>
          ) : null}

          <div className="grid gap-3">
            {result.checks.map((check) => (
              <div key={check.name} className={`rounded-[18px] border px-4 py-3 text-sm ${toneClass(check.passed)}`}>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div className="font-semibold">{check.name}</div>
                  {check.metric !== null && check.threshold !== null ? (
                    <div className="font-mono text-xs">
                      {check.metric.toFixed(2)} / {check.threshold.toFixed(2)}
                    </div>
                  ) : null}
                </div>
                <div className="mt-1 leading-6">{check.detail}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {execution ? (
        <div className="mt-4 rounded-[20px] border border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] px-4 py-3 text-sm text-emerald-100">
          Order ID: <span className="font-mono">{execution.order_id}</span>
          {execution.managed_exit_plan ? (
            <div className="mt-2">
              Managed exit armed at stop <span className="font-mono">{execution.managed_exit_plan.stop_price}</span> and take profit{" "}
              <span className="font-mono">{execution.managed_exit_plan.take_profit_price}</span>.
            </div>
          ) : null}
        </div>
      ) : null}

      {armedExisting ? (
        <div className="mt-4 rounded-[20px] border border-[color:rgba(108,152,255,0.24)] bg-[rgba(20,30,54,0.4)] px-4 py-3 text-sm text-sky-100">
          Existing position armed with managed exit plan <span className="font-mono">#{armedExisting.plan.id}</span>.
        </div>
      ) : null}
    </section>
  );
}
