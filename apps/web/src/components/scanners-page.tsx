import { AppFrame } from "@/components/app-frame";
import { FuturesAnomalyPanel } from "@/components/futures-anomaly-panel";
import { OneHourSpikePanel } from "@/components/one-hour-spike-panel";
import { ScannersAutoRefresh } from "@/components/scanners-auto-refresh";
import { SleepingGiantsPanel } from "@/components/sleeping-giants-panel";
import { getFuturesAnomalies, getOneHourSpikes, getSleepingGiants } from "@/lib/api";

export async function ScannersPage() {
  const fallbackSleepingGiants = (timeframe: "1H" | "4H") => ({
    latest_report_at: null,
    timeframe,
    lookback_days: 21,
    baseline_candles: 200,
    scanned_symbols: 0,
    candidates: [],
    note: "Sleeping Giant candle provider is temporarily unavailable. The rest of the scanner workbench is still usable.",
  });
  const [sleepingGiants1h, sleepingGiants4h, recentAwakenings1h] = await Promise.all([
    getSleepingGiants("1H").catch(() => fallbackSleepingGiants("1H")),
    getSleepingGiants("4H").catch(() => fallbackSleepingGiants("4H")),
    getSleepingGiants("1H", "recent").catch(() => fallbackSleepingGiants("1H")),
  ]);
  const futuresAnomalies = await getFuturesAnomalies().catch(() => ({
    latest_report_at: null,
    interval_seconds: 300,
    lookback_hours: 24,
    source: "Anomaly endpoint unavailable.",
    top_breakouts: [],
    top_breakdowns: [],
    note: "The anomaly scoring endpoint is temporarily unavailable. Restart the API if this section stays empty.",
  }));
  const oneHourSpikes = await getOneHourSpikes().catch(() => ({
    latest_report_at: null,
    interval_seconds: 300,
    baseline_candles: 48,
    scanned_symbols: 0,
    candidates: [],
    source: "1H spike endpoint unavailable.",
    note: "The 1H spike monitor endpoint is temporarily unavailable. Restart the API if this section stays empty.",
  }));

  return (
    <AppFrame
      current="scanners"
      title="Scanner workbench."
      subtitle="Watch early compression breakouts as decision support, not trade commands."
    >
      <ScannersAutoRefresh />

      <FuturesAnomalyPanel data={futuresAnomalies} />

      <OneHourSpikePanel data={oneHourSpikes} />

      <SleepingGiantsPanel data={sleepingGiants1h} />

      <SleepingGiantsPanel data={sleepingGiants4h} />

      <SleepingGiantsPanel data={recentAwakenings1h} variant="recent" />
    </AppFrame>
  );
}
