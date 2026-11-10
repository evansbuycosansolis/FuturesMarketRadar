"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { DeskMarketLens, formatDeskMoney } from "@/components/desk-market-lens";
import { deskApi, type Conversation, type DeskAnswer, type DeskMessage, type DeskStatus, type MarketSnapshot } from "@/lib/desk-api";

const seats: Record<string, string> = { "desk-lead": "Desk Lead", "market-analyst": "Market Analyst", "research-analyst": "Research Analyst", strategist: "Strategist", "risk-manager": "Risk Manager", "execution-trader": "Execution Trader", "trade-reviewer": "Trade Reviewer" };
const sessionKey = "agentic-radar:conversation:v1";

function MessageText({ text }: { text: string }) {
  return <div className="desk-message-text">{text.split("\n").map((line, index) => {
    const heading = /^#{1,4}\s+/.test(line);
    const content = line.replace(/^#{1,4}\s+/, "");
    const parts = content.split(/(\*\*.*?\*\*)/g).map((part, i) => part.startsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part);
    return heading ? <h3 key={index}>{parts}</h3> : line.trim() ? <p key={index}>{parts}</p> : <br key={index} />;
  })}</div>;
}

export function TradingDesk({ initialSymbol, newConversation }: { initialSymbol: string; newConversation: boolean }) {
  const [status, setStatus] = useState<DeskStatus | null>(null);
  const [role, setRole] = useState("desk-lead");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<DeskMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-5.4");
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const connection = useRef<HTMLDetailsElement>(null);
  const switchingId = useRef(0);
  useEffect(() => {
    const abort = new AbortController();
    async function load() {
      try {
        const [current, history] = await Promise.all([deskApi<DeskStatus>("status", { signal: abort.signal }), deskApi<Conversation[]>("conversations", { signal: abort.signal })]);
        if (abort.signal.aborted) return;
        setStatus(current); setModel(current.model); setConversations(history);
        const saved = newConversation ? null : sessionStorage.getItem(sessionKey);
        if (saved && history.some(item => item.id === saved)) {
          const rows = await deskApi<DeskMessage[]>(`messages?id=${saved}`, { signal: abort.signal });
          if (!abort.signal.aborted) { setConversation(saved); setMessages(rows); if (rows.length) setRole(rows.at(-1)!.seat); }
        } else if (newConversation) sessionStorage.removeItem(sessionKey);
        if (window.location.hash === "#connection" && connection.current) connection.current.open = true;
      } catch (err) { if (!abort.signal.aborted) setError(err instanceof Error ? err.message : "The desk is unavailable."); }
      finally { if (!abort.signal.aborted) setLoading(false); }
    }
    void load(); return () => abort.abort();
  }, [newConversation]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [messages.length, busy]);
  useEffect(() => {
    function reset() { if (!busy && !switching) { setConversation(null); setMessages([]); setError(""); sessionStorage.removeItem(sessionKey); } }
    window.addEventListener("agentic:new-conversation", reset);
    return () => window.removeEventListener("agentic:new-conversation", reset);
  }, [busy, switching]);

  async function chooseConversation(id: string) {
    const request = ++switchingId.current;
    if (!id) { setConversation(null); setMessages([]); sessionStorage.removeItem(sessionKey); return; }
    setSwitching(true); setError("");
    try { const rows = await deskApi<DeskMessage[]>(`messages?id=${id}`); if (request !== switchingId.current) return; setMessages(rows); setConversation(id); sessionStorage.setItem(sessionKey, id); if (rows.length) setRole(rows.at(-1)!.seat); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not open that conversation."); }
    finally { if (request === switchingId.current) setSwitching(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!status || busy || switching || !draft.trim()) return;
    if (!status.configured) { if (connection.current) { connection.current.open = true; connection.current.scrollIntoView({ block: "center" }); } setConnectionError("Add your OpenAI key to enable chat."); return; }
    setBusy(true); setError("");
    const userMessage = draft.trim();
    try {
      const id = conversation ?? (await deskApi<{ id: string }>("conversations", { body: {}, token: status.csrf_token })).id;
      setConversation(id); sessionStorage.setItem(sessionKey, id);
      // The selected venue is explicit; the model must fetch evidence rather than trust UI text.
      const message = messages.length === 0 ? `Selected Radar market: ${initialSymbol} (Pionex). Cross-venue comparisons must preserve venue identity.\n\n${userMessage}` : userMessage;
      const answer = await deskApi<DeskAnswer>("chat", { body: { conversation_id: id, role, message }, token: status.csrf_token });
      setMessages(previous => [...previous, { role: "user", seat: role, content: message }, { role: "assistant", seat: role, content: answer.content, details: answer }]);
      setDraft("");
      try { setConversations(await deskApi<Conversation[]>("conversations")); } catch { /* A history refresh must not turn a saved answer into a failed send. */ }
    } catch (err) { setError(err instanceof Error ? err.message : "The desk request failed."); }
    finally { setBusy(false); }
  }
  async function saveConnection(event: FormEvent, clear = false) {
    event.preventDefault(); if (!status || saving) return;
    setSaving(true); setConnectionError("");
    try { await deskApi("settings", { body: { api_key: apiKey.trim(), model: model.trim(), clear_key: clear }, token: status.csrf_token }); setApiKey(""); setStatus(await deskApi<DeskStatus>("status")); }
    catch (err) { setConnectionError(err instanceof Error ? err.message : "Connection settings could not be saved."); }
    finally { setSaving(false); }
  }
  const change = snapshot ? Number(snapshot.prices.change_24h_pct) : null;
  return <div className="radar-shell workspace-page desk-page">
    <header className="workspace-page-heading"><div><div className="workspace-eyebrow">YOUR INTELLIGENCE, ORGANIZED</div><h1>The trading floor<span>.</span></h1><p>Research the market. Test your thinking. Keep the evidence.</p></div><span className="desk-research-pill">◇ RESEARCH ONLY</span></header>
    <section className="desk-metrics" aria-label="Hyperliquid market snapshot"><div><label>{snapshot?.market ?? "HYPERLIQUID MARKET"}</label><strong>{formatDeskMoney(snapshot?.prices.book_mid)} {change !== null ? <small className={change < 0 ? "is-negative" : ""}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</small> : null}</strong><span>Book midpoint · USD</span></div><div><label>HOURLY FUNDING</label><strong>{snapshot ? `${Number(snapshot.funding.hourly_pct).toFixed(5)}%` : "—"}</strong><span>Current rate / hour</span></div><div><label>OPEN INTEREST</label><strong>{formatDeskMoney(snapshot?.activity.open_interest_usd, true)}</strong><span>Notional value · USD</span></div><div><label>BID–ASK SPREAD</label><strong>{snapshot ? Number(snapshot.book.spread_bps).toFixed(3) : "—"}</strong><span>Basis points</span></div></section>
    <details className="desk-connection" id="connection" ref={connection}><summary><span className={`desk-status-dot ${status?.configured ? "configured" : ""}`} />OpenAI connection <span>{status?.configured ? `Key configured · ${status.model}` : "Configure API access"}</span></summary><form onSubmit={saveConnection}><div><label htmlFor="openai-key">OpenAI API key</label><input id="openai-key" type="password" autoComplete="off" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder={status?.configured ? "Leave blank to keep the current key" : "sk-…"} maxLength={512} /></div><div><label htmlFor="openai-model">Model ID</label><input id="openai-model" value={model} onChange={e => setModel(e.target.value)} maxLength={100} required /></div><button className="desk-primary" disabled={!status || saving || busy}>Save connection ↗</button><button className="desk-secondary" type="button" disabled={!status || saving || busy} onClick={event => void saveConnection(event, true)}>Disconnect</button></form><p>Keys entered here stay in the local desk server&apos;s memory. Messages, loaded instructions and requested evidence are sent to OpenAI; API usage is billed to your project. A configured key is verified when you send a request.</p>{connectionError ? <p className="desk-error" role="alert">{connectionError}</p> : null}</details>
    <div className="desk-workspace-grid"><section className="desk-chat-card" aria-label="OpenAI desk conversation"><div className="desk-chat-heading"><div><span className="desk-agent-icon">▤</span><div><label htmlFor="desk-role" className="sr-only">Desk role</label><select id="desk-role" value={role} onChange={e => setRole(e.target.value)} disabled={busy || switching}>{Object.entries(seats).map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select><small>Specialist roles, shared evidence</small></div></div><span>OPENAI AGENT</span></div>
      <div className="desk-history-toolbar"><label className="sr-only" htmlFor="desk-history">Saved conversations</label><select id="desk-history" value={conversation ?? ""} disabled={busy || loading || switching} onChange={e => void chooseConversation(e.target.value)}><option value="">New conversation</option>{conversations.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select><button disabled={busy || switching} onClick={() => void chooseConversation("")}>＋ New</button></div>
      <div className="desk-messages" aria-live="polite">{!messages.length && !busy ? <div className="desk-welcome"><div>✳</div><h2>A clear view starts here.</h2><p>Your desk connects Radar&apos;s research with Hyperliquid market evidence.</p><div className="desk-suggestions">{[
        ["Compare the evidence", `Read radar_evidence for ${initialSymbol}. Compare it with a fresh Hyperliquid snapshot only if the matching market exists. State gaps, venue and freshness.`],
        ["Brief me on this market", `Read the stored Radar evidence for ${initialSymbol} and explain its scores, limitations and freshness. No trading signal.`],
        ["Challenge my assumptions", "What information do you need from me to evaluate my own trade hypothesis and estimate stressed stop risk?"],
        ["Explore the workflow", "Explain the research tools and role handoffs available in this integrated desk. State which actions remain unavailable."]
      ].map(([title, prompt]) => <button key={title} onClick={() => setDraft(prompt)}>{title}<span>↗</span></button>)}</div>{loading ? <p>Connecting to the local desk…</p> : null}</div> : null}
      {messages.map((row, index) => <article className={`desk-message ${row.role}`} key={row.id ?? index}><div className="desk-message-meta"><span>{row.role === "user" ? "Y" : "a"}</span>{row.role === "user" ? "You" : seats[row.seat] ?? row.seat}{row.created_at ? <time>{new Date(row.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time> : null}</div><MessageText text={row.content} />{row.details?.traces?.length ? <details className="desk-evidence"><summary>Inspect evidence · {row.details.traces.length} tool calls</summary><pre>{JSON.stringify(row.details.traces, null, 2)}</pre></details> : null}{row.details?.usage ? <p className="desk-token-usage">{row.details.model} · {row.details.usage.input_tokens.toLocaleString()} input / {row.details.usage.output_tokens.toLocaleString()} output tokens</p> : null}</article>)}
      {busy ? <p className="desk-thinking" role="status">The desk is working. Evidence reads and specialist passes can take a moment.</p> : null}<div ref={bottom} /></div>
      {error ? <p className="desk-error desk-chat-error" role="alert">{error}</p> : null}
      <form className="desk-composer" onSubmit={submit}><label htmlFor="desk-message" className="sr-only">Message your desk</label><textarea id="desk-message" value={draft} onChange={e => setDraft(e.target.value)} disabled={busy || switching} maxLength={8000} rows={3} placeholder={`Ask ${seats[role]} a question…`} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><div><span>• {seats[role]} <b>/</b> {status?.model ?? "OpenAI"}</span><button className="desk-primary" disabled={!status || busy || loading || switching || !draft.trim()}>{busy ? "Working…" : "Send ↗"}</button></div></form><p className="desk-composer-note">Enter to send · Shift + Enter for a new line · AI output needs your review</p>
    </section><DeskMarketLens symbol={initialSymbol} onSnapshot={setSnapshot} /></div>
  </div>;
}
