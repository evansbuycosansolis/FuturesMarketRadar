import { TradingDesk } from "@/components/trading-desk";
export const dynamic = "force-dynamic";
export default async function DeskPage({ searchParams }: { searchParams: Promise<{ symbol?: string; new?: string }> }) {
  const params = await searchParams;
  return <TradingDesk key={`${params.symbol ?? ""}:${params.new ?? ""}`} initialSymbol={params.symbol ?? "ETH_USDT_PERP"} newConversation={params.new === "1"} />;
}
