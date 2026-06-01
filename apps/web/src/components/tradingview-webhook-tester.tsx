"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import { sendTradingViewWebhook } from "@/lib/api";

const defaultPayload = {
  id: "manual-tv-test-001",
  strategy: "dashboard-test",
  symbol: "BTC_USDT_PERP",
  action: "BUY",
  order_type: "MARKET_QTY",
  size: 0.001,
  entry_price: 68000,
  stop_price: 67200,
  take_profit_price: 69600,
};

type TradingViewWebhookTesterProps = {
  webhookSecretConfigured: boolean;
};

export function TradingViewWebhookTester({ webhookSecretConfigured }: TradingViewWebhookTesterProps) {
  const router = useRouter();
  const [secret, setSecret] = useState("");
  const [payloadText, setPayloadText] = useState(JSON.stringify(defaultPayload, null, 2));
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  const payloadValid = useMemo(() => {
    try {
      JSON.parse(payloadText);
      return true;
    } catch {
      return false;
    }
  }, [payloadText]);

  function sendTest() {
    setMessage("");
    startTransition(async () => {
      try {
        const parsed = JSON.parse(payloadText) as Record<string, unknown>;
        const response = await sendTradingViewWebhook(parsed, secret);
        setMessage(`${response.message} Status: ${response.signal.status}.`);
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Webhook test failed.");
      }
    });
  }

  return (
    <section className="radar-card p-6 sm:p-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="radar-chip">Webhook Test</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Send a local TradingView-style alert</h2>
        </div>
        <span className="radar-chip">{webhookSecretConfigured ? "Secret Configured" : "Secret Missing"}</span>
      </div>

      <div className="mt-6 grid gap-4">
        <label className="grid gap-2">
          <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Webhook Secret</span>
          <input
            className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.48)] px-4 py-3 text-sm text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => setSecret(event.target.value)}
            placeholder="Paste FMR_TRADINGVIEW_WEBHOOK_SECRET for local test"
            type="password"
            value={secret}
          />
        </label>

        <label className="grid gap-2">
          <span className="text-xs uppercase tracking-[0.16em] text-[var(--radar-muted)]">Alert JSON</span>
          <textarea
            className="min-h-72 rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.48)] px-4 py-3 font-mono text-xs leading-6 text-[var(--radar-ink)] outline-none transition focus:border-[color:var(--radar-sea)]"
            onChange={(event) => setPayloadText(event.target.value)}
            spellCheck={false}
            value={payloadText}
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          className="inline-flex items-center justify-center rounded-full border border-[color:rgba(46,183,154,0.24)] bg-[rgba(18,58,49,0.42)] px-5 py-2.5 text-sm font-semibold text-emerald-100 transition hover:border-[color:rgba(46,183,154,0.42)] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isPending || !payloadValid}
          onClick={sendTest}
          type="button"
        >
          {isPending ? "Sending..." : "Send Test Alert"}
        </button>
        {!payloadValid ? <span className="text-sm text-rose-100">JSON is not valid.</span> : null}
      </div>

      {message ? <p className="mt-4 text-sm leading-7 text-[var(--radar-muted)]">{message}</p> : null}
    </section>
  );
}
