import { AppFrame } from "@/components/app-frame";
import { AssetResearchPanel } from "@/components/asset-research-panel";

export function ResearchPage() {
  return (
    <AppFrame
      current="research"
      title="Asset research agent."
      subtitle="Research crypto, tokens, and stocks with public context plus your stored session momentum."
    >
      <AssetResearchPanel />
    </AppFrame>
  );
}
