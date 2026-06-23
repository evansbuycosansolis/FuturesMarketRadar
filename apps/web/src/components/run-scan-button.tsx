"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { runScanNow } from "@/lib/api";

export function RunScanButton() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [message, setMessage] = useState<string>("");

  async function handleClick() {
    setMessage("");
    try {
      const result = await runScanNow();
      setMessage(result.report ? "Fresh report generated." : result.message || "Market board refreshed.");
      startTransition(() => {
        router.refresh();
      });
    } catch {
      setMessage("Run failed. Check the API logs and try again.");
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        className="inline-flex items-center justify-center rounded-full border border-[color:rgba(46,183,154,0.35)] bg-[var(--radar-sea)] px-5 py-3 text-sm font-bold text-black shadow-[0_0_24px_rgba(46,183,154,0.18)] transition hover:-translate-y-0.5 hover:bg-[var(--radar-ink)] hover:text-[var(--radar-bg)] disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isPending}
        onClick={handleClick}
        type="button"
      >
        {isPending ? "Running Scan..." : "Run Now"}
      </button>
      {message ? (
        <p aria-live="polite" className="text-right text-xs text-[var(--radar-muted)]">
          {message}
        </p>
      ) : null}
    </div>
  );
}
