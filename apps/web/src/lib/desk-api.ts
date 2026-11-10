export type DeskStatus = { configured: boolean; provider: string; model: string; mode: string; roles: Record<string, string>; csrf_token: string; exchange_writes: boolean };
export type Evidence = { tool: string; observed_at: string; result: unknown };
export type DeskAnswer = { content: string; model: string; traces: Evidence[]; usage: { input_tokens: number; output_tokens: number } };
export type DeskMessage = { id?: number; role: "user" | "assistant"; seat: string; content: string; created_at?: string; details?: Partial<DeskAnswer> };
export type Conversation = { id: string; title: string; created_at: string };
export type MarketSnapshot = { market: string; coin: string; source: { observed_at: string; [key: string]: unknown }; prices: Record<string, string>; funding: Record<string, string>; activity: Record<string, string>; book: { spread_bps: string; depth: Record<string, { bid_usd: string; ask_usd: string; bid_complete: boolean; ask_complete: boolean }> } };
export type RadarEvidence = { symbol: string; exchange: string; status: string; retrieved_at: string; market: { price: number; observed_at: string; freshness: string } | null; scanner: { activity_score: number; bullish_score: number; bearish_score: number; observed_at: string; freshness: string } | null; research: { article_count: number; sentiment_score: number; observed_at: string; freshness: string } | null; limitations: string[] };

function baseUrl() { return typeof window === "undefined" ? process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010" : process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010"; }
export async function deskApi<T>(path: string, options: { body?: unknown; token?: string; signal?: AbortSignal } = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`${baseUrl()}/api/desk/${path}`, { method: options.body === undefined ? "GET" : "POST", cache: "no-store", signal: options.signal, headers: { "Content-Type": "application/json", ...(options.token ? { "X-Desk-Token": options.token } : {}) }, ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }) }); }
  catch (error) { if (error instanceof DOMException && error.name === "AbortError") throw error; throw new Error("Cannot reach Radar. Start the integrated launcher and check the API connection."); }
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : data.error ?? `Desk request failed (${response.status}).`);
  return data as T;
}
