export function pionexFuturesUrl(symbol: string): string {
  const base = symbol.replace("_USDT_PERP", "");
  return `https://www.pionex.com/en/futures/${base}.PERP_USDT/Bot`;
}
