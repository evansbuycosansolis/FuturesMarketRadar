"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { engageKillSwitch, releaseKillSwitch, runAutomationWatchdogNow, syncRiskNow } from "@/lib/api";

type HubControlButtonsProps = {
  compact?: boolean;
  killSwitchEnabled: boolean;
};

export function HubControlButtons({ compact = false, killSwitchEnabled }: HubControlButtonsProps) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function runAction(action: () => Promise<{ message?: string } | unknown>, fallback: string) {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await action();
        const typed = response as { message?: string };
        setMessage(typed.message ?? fallback);
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Action failed.");
      }
    });
  }

  const buttonClass = compact ? "px-3 py-1 text-xs" : "px-4 py-1 text-xs";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        className={`bg-emerald-600 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${buttonClass}`}
        disabled={isPending || !killSwitchEnabled}
        onClick={() => runAction(() => releaseKillSwitch("Released from Evans's Future Trading Copilot."), "Trading controls released.")}
        type="button"
      >
        Start All
      </button>
      <button
        className={`bg-rose-600 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${buttonClass}`}
        disabled={isPending || killSwitchEnabled}
        onClick={() => runAction(() => engageKillSwitch("Stopped from Evans's Future Trading Copilot."), "Trading controls stopped.")}
        type="button"
      >
        Stop All
      </button>
      <button
        className={`border border-[#516076] text-slate-200 disabled:cursor-not-allowed disabled:opacity-50 ${buttonClass}`}
        disabled={isPending}
        onClick={() => runAction(syncRiskNow, "Account sync requested.")}
        type="button"
      >
        Sync
      </button>
      <button
        className={`border border-[#516076] text-slate-200 disabled:cursor-not-allowed disabled:opacity-50 ${buttonClass}`}
        disabled={isPending}
        onClick={() => runAction(runAutomationWatchdogNow, "Watchdog cycle completed.")}
        type="button"
      >
        Watchdog
      </button>
      {message ? <span className="text-[11px] text-cyan-300">{message}</span> : null}
    </div>
  );
}
