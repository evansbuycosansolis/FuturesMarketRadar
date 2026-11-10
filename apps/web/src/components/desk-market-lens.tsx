"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { deskApi, type MarketSnapshot, type RadarEvidence } from "@/lib/desk-api";
export function formatDeskMoney(value: string | number | undefined, compact = false) {
  if (value === undefined || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: compact ? "compact" : "standard", maximumFractionDigits: 2 }).format(Number(value));
}
export function DeskMarketLens({ symbol, onSnapshot }: { symbol: string; onSnapshot: (data: MarketSnapshot | null) => void }) {
  const initialCoin = symbol.endsWith("_USDT_PERP") ? symbol.slice(0, -10) : symbol;
  const [coin, setCoin] = useState(initialCoin);
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [radar, setRadar] = useState<RadarEvidence | null>(null);
  const [error, setError] = useState("");
  const [radarError, setRadarError] = useState("");
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);
  const onSnapshotRef = useRef(onSnapshot);
  useEffect(() => { onSnapshotRef.current = onSnapshot; }, [onSnapshot]);
  async function refresh(value: string) {
    const id = ++requestId.current;
    setLoading(true); setError(""); setSnapshot(null); onSnapshotRef.current(null);
    try { const data = await deskApi<MarketSnapshot>(`market?coin=${encodeURIComponent(value)}`); if (id !== requestId.current) return; setSnapshot(data); onSnapshotRef.current(data); }
    catch (err) { if (id === requestId.current) setError(err instanceof Error ? err.message : "Market data is unavailable."); }
    finally { if (id === requestId.current) setLoading(false); }
  }
  useEffect(() => {
    const abort = new AbortController();
    const id = ++requestId.current;
    deskApi<MarketSnapshot>(`market?coin=${encodeURIComponent(initialCoin)}`, { signal: abort.signal })
      .then(data => { if (!abort.signal.aborted && id === requestId.current) { setSnapshot(data); onSnapshotRef.current(data); } })
      .catch(err => { if (!abort.signal.aborted && id === requestId.current) setError(err.message); })
      .finally(() => { if (!abort.signal.aborted && id === requestId.current) setLoading(false); });
    deskApi<RadarEvidence>(`evidence?symbol=${encodeURIComponent(symbol)}`, { signal: abort.signal }).then(setRadar).catch(err => { if (err.name !== "AbortError") setRadarError(err.message); });
    return () => abort.abort();
  }, [initialCoin, symbol]);
  function submit(event: FormEvent) { event.preventDefault(); void refresh(coin.trim()); }
  const depth = Object.entries(snapshot?.book.depth ?? {});
  const max = Math.max(1, ...depth.flatMap(([, row]) => [Number(row.bid_usd), Number(row.ask_usd)]));
  return <aside className="desk-context">
    <section className="desk-card"><div className="desk-card-heading"><h2>Market lens</h2><span>HYPERLIQUID</span></div>
      <form className="desk-market-search" onSubmit={submit}><label className="sr-only" htmlFor="desk-coin">Hyperliquid coin</label><input id="desk-coin" value={coin} onChange={e => setCoin(e.target.value)} maxLength={64} placeholder="ETH or xyz:TSLA" /><button aria-label="Refresh Hyperliquid snapshot" disabled={loading}>{loading ? "…" : "↻"}</button></form>
      {error ? <p className="desk-error" role="alert">{error}</p> : null}<div className="desk-small-label">ORDER BOOK DEPTH <span>USD</span></div>
      {loading ? <p className="desk-muted">Fetching public market data…</p> : null}
      {depth.map(([band, row]) => <div className="desk-depth-row" key={band}><div><span>{band} bps</span><span>{row.bid_complete ? "" : "≥ "}{formatDeskMoney(row.bid_usd, true)} / {row.ask_complete ? "" : "≥ "}{formatDeskMoney(row.ask_usd, true)}</span></div><svg viewBox="0 0 200 6" aria-hidden="true"><rect x={98 - Number(row.bid_usd) / max * 97} y="0" width={Number(row.bid_usd) / max * 97} height="6" rx="2" fill="#bfd896" /><rect x="102" y="0" width={Number(row.ask_usd) / max * 97} height="6" rx="2" fill="#e9c2ad" /></svg></div>)}
      <div className="desk-depth-key"><span>▰ Bids</span><span>▰ Asks</span></div><dl className="desk-market-details"><div><dt>Mark price</dt><dd>{formatDeskMoney(snapshot?.prices.mark)}</dd></div><div><dt>Oracle price</dt><dd>{formatDeskMoney(snapshot?.prices.oracle)}</dd></div><div><dt>24h volume</dt><dd>{formatDeskMoney(snapshot?.activity.volume_24h_usd, true)}</dd></div></dl>
      <p className="desk-source">{snapshot ? `Observed ${snapshot.source.observed_at}` : "No current snapshot"}</p><p className="desk-caption">Hyperliquid /info · mainnet<br />Refresh on request. Partial depth is a floor.</p>{snapshot ? <details className="desk-evidence"><summary>Inspect source evidence</summary><pre>{JSON.stringify(snapshot, null, 2)}</pre></details> : null}
    </section>
    <section className="desk-card desk-radar-card"><div className="desk-card-heading"><h2>Radar evidence</h2><span>PIONEX</span></div><p className="desk-symbol">{symbol}</p>{radarError ? <p className="desk-error" role="alert">{radarError}</p> : null}
      {radar?.scanner ? <><dl className="desk-market-details"><div><dt>Activity</dt><dd>{radar.scanner.activity_score.toFixed(1)} / 100</dd></div><div><dt>Bullish / bearish</dt><dd>{radar.scanner.bullish_score.toFixed(0)} / {radar.scanner.bearish_score.toFixed(0)}</dd></div></dl><p className="desk-source">{radar.scanner.freshness === "fresh" ? "Recent stored scan" : "Stale or future-dated scan"} · {radar.scanner.observed_at}</p></> : <p className="desk-muted">No stored scanner evidence for this market yet.</p>}
      {radar?.research ? <p className="desk-caption">Sentiment evidence: {radar.research.article_count} articles · {radar.research.freshness}</p> : null}<p className="desk-caption">Radar scores remain separate from Hyperliquid observations and never authorize a trade.</p>{radar ? <details className="desk-evidence"><summary>Inspect Radar evidence</summary><pre>{JSON.stringify(radar, null, 2)}</pre></details> : null}
    </section>
    <section className="desk-process"><h2>A disciplined process <span>↗</span></h2><ol><li><b>01</b><div>Your idea<small>You bring the hypothesis.</small></div></li><li><b>02</b><div>Evidence & research<small>The desk checks the facts.</small></div></li><li><b>03</b><div>Risk & review<small>Assumptions stay explicit.</small></div></li></ol><p>The OpenAI desk is research-only. Existing Radar controls remain in their own workspaces.</p></section>
  </aside>;
}
