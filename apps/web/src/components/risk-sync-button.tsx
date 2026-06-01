"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { syncRiskNow } from "@/lib/api";

export function RiskSyncButton() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [message, setMessage] = useState("");

  async function handleSync() {
    setMessage("");
    try {
      await syncRiskNow();
      setMessage("Account snapshot refreshed.");
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Sync failed.");
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        className="inline-flex items-center justify-center rounded-full bg-[var(--radar-sea)] px-5 py-3 text-sm font-semibold text-[#04110f] transition hover:-translate-y-0.5 hover:bg-[var(--radar-sun)] disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isPending}
        onClick={handleSync}
        type="button"
      >
        {isPending ? "Syncing..." : "Sync Account"}
      </button>
      {message ? (
        <p aria-live="polite" className="max-w-[20rem] text-right text-xs text-[var(--radar-muted)]">
          {message}
        </p>
      ) : null}
    </div>
  );
}
