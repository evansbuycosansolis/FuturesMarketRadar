"use client";

import { useState, useTransition } from "react";

import { updateRiskPolicy } from "@/lib/api";
import { RiskPolicy } from "@/lib/types";

type EditablePolicy = Omit<RiskPolicy, "id" | "name" | "created_at" | "updated_at">;
type NumericPolicyField =
  | "max_risk_per_trade_pct"
  | "max_daily_loss_pct"
  | "max_weekly_loss_pct"
  | "max_portfolio_heat_pct"
  | "max_symbol_exposure_pct"
  | "max_open_positions"
  | "max_allowed_leverage"
  | "min_liquidation_buffer_pct"
  | "min_stop_distance_pct"
  | "buyer_absence_block_score"
  | "dead_market_block_score";
type BooleanPolicyField =
  | "require_stop_loss"
  | "block_new_trades_in_dead_market"
  | "block_longs_when_buyers_left";

type RiskPolicyPanelProps = {
  policy: RiskPolicy;
};

const numberFields: NumericPolicyField[] = [
  "max_risk_per_trade_pct",
  "max_daily_loss_pct",
  "max_weekly_loss_pct",
  "max_portfolio_heat_pct",
  "max_symbol_exposure_pct",
  "max_open_positions",
  "max_allowed_leverage",
  "min_liquidation_buffer_pct",
  "min_stop_distance_pct",
  "buyer_absence_block_score",
  "dead_market_block_score",
];

const booleanFields: BooleanPolicyField[] = [
  "require_stop_loss",
  "block_new_trades_in_dead_market",
  "block_longs_when_buyers_left",
];

const labels: Record<keyof EditablePolicy, string> = {
  max_risk_per_trade_pct: "Risk / Trade %",
  max_daily_loss_pct: "Daily Loss %",
  max_weekly_loss_pct: "Weekly Loss %",
  max_portfolio_heat_pct: "Portfolio Heat %",
  max_symbol_exposure_pct: "Symbol Exposure %",
  max_open_positions: "Open Positions",
  max_allowed_leverage: "Max Leverage",
  min_liquidation_buffer_pct: "Min Liq Buffer %",
  min_stop_distance_pct: "Min Stop Distance %",
  buyer_absence_block_score: "Buyer-Left Block",
  dead_market_block_score: "Dead-Market Block",
  require_stop_loss: "Require Stop Loss",
  block_new_trades_in_dead_market: "Block Dead Markets",
  block_longs_when_buyers_left: "Block Longs When Buyers Left",
};

function toEditablePolicy(policy: RiskPolicy): EditablePolicy {
  return {
    max_risk_per_trade_pct: policy.max_risk_per_trade_pct,
    max_daily_loss_pct: policy.max_daily_loss_pct,
    max_weekly_loss_pct: policy.max_weekly_loss_pct,
    max_portfolio_heat_pct: policy.max_portfolio_heat_pct,
    max_symbol_exposure_pct: policy.max_symbol_exposure_pct,
    max_open_positions: policy.max_open_positions,
    max_allowed_leverage: policy.max_allowed_leverage,
    min_liquidation_buffer_pct: policy.min_liquidation_buffer_pct,
    min_stop_distance_pct: policy.min_stop_distance_pct,
    buyer_absence_block_score: policy.buyer_absence_block_score,
    dead_market_block_score: policy.dead_market_block_score,
    require_stop_loss: policy.require_stop_loss,
    block_new_trades_in_dead_market: policy.block_new_trades_in_dead_market,
    block_longs_when_buyers_left: policy.block_longs_when_buyers_left,
  };
}

export function RiskPolicyPanel({ policy }: RiskPolicyPanelProps) {
  const [isPending, startTransition] = useTransition();
  const [form, setForm] = useState<EditablePolicy>(() => toEditablePolicy(policy));
  const [message, setMessage] = useState("");

  function handleNumberChange(field: NumericPolicyField, value: string) {
    setForm((current) => ({
      ...current,
      [field]: value === "" ? 0 : Number(value),
    }));
  }

  function handleBooleanChange(field: BooleanPolicyField, checked: boolean) {
    setForm((current) => ({
      ...current,
      [field]: checked,
    }));
  }

  function handleSave() {
    setMessage("");
    startTransition(async () => {
      try {
        const updated = await updateRiskPolicy(form);
        setForm(toEditablePolicy(updated));
        setMessage("Risk policy saved.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Save failed.");
      }
    });
  }

  return (
    <section className="radar-card p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">Risk Policy</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Hard limits you actually trade through</h2>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--radar-muted)]">
            These rules are enforced by the pre-trade checker first, and the execution path only opens if the order survives every blocking rule.
          </p>
        </div>
        <button
          className="inline-flex items-center justify-center rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-4 py-2 text-sm font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sea)] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isPending}
          onClick={handleSave}
          type="button"
        >
          {isPending ? "Saving..." : "Save Policy"}
        </button>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {numberFields.map((field) => (
          <label key={field} className="space-y-2">
            <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">{labels[field]}</span>
            <input
              className="w-full rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
              min={0}
              onChange={(event) => handleNumberChange(field, event.target.value)}
              step={field === "max_open_positions" ? 1 : 0.01}
              type="number"
              value={form[field] as number}
            />
          </label>
        ))}
      </div>

      <div className="mt-6 grid gap-3">
        {booleanFields.map((field) => (
          <label key={field} className="flex items-center justify-between rounded-[20px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3">
            <span className="text-sm font-medium text-[var(--radar-ink)]">{labels[field]}</span>
            <input
              checked={Boolean(form[field])}
              className="h-4 w-4 accent-[var(--radar-sea)]"
              onChange={(event) => handleBooleanChange(field, event.target.checked)}
              type="checkbox"
            />
          </label>
        ))}
      </div>

      {message ? <p className="mt-4 text-sm text-[var(--radar-muted)]">{message}</p> : null}
    </section>
  );
}
