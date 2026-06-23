import { AppFrame } from "@/components/app-frame";
import { ChangeTrajectoryPanel } from "@/components/change-trajectory-panel";
import { ScannersAutoRefresh } from "@/components/scanners-auto-refresh";
import { getMarketChangeTrajectory } from "@/lib/api";

export async function RecoveryFadePage() {
  const trajectory = await getMarketChangeTrajectory();

  return (
    <AppFrame
      current="recovery-fade"
      title="Recovery & Fade Tracker."
      subtitle="Track coins recovering from weak 24H Change readings and coins fading from earlier highs using stored market snapshots."
    >
      <ScannersAutoRefresh />

      <ChangeTrajectoryPanel trajectory={trajectory} />
    </AppFrame>
  );
}
