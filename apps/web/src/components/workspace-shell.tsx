"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

const groups = [
  { label: "WORKSPACE", items: [["/dashboard", "Overview", "▦"], ["/desk", "Trading desk", "▤"]] },
  { label: "MARKET TOOLS", items: [["/markets", "Markets", "◴"], ["/scanners", "Scanners", "⌕"], ["/recovery-fade", "Recovery / Fade", "↗"], ["/research", "Research", "◎"], ["/reports", "Reports", "▧"]] },
  { label: "PRACTICE & CONTROL", items: [["/simulator", "Simulator & calculators", "⌘"], ["/strategy-forge", "Strategy forge", "◇"], ["/risk", "Risk & connections", "⬡"], ["/tradingview", "TradingView", "⌁"]] },
];
export function WorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    function closeOnEscape(event: KeyboardEvent) { if (event.key === "Escape") setOpen(false); }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);
  const active = groups.flatMap(group => group.items).find(([href]) => pathname === href);
  return <div className="workspace-layout">
    <a className="workspace-skip" href="#workspace-content">Skip to workspace</a>
    <button className="workspace-mobile-toggle" aria-label={open ? "Close tools" : "Open tools"} aria-expanded={open} aria-controls="workspace-sidebar" onClick={() => setOpen(!open)}>{open ? "×" : "☰"}</button>
    {open ? <button className="workspace-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} /> : null}
    <aside id="workspace-sidebar" className={`workspace-sidebar ${open ? "is-open" : ""}`}>
      <Link href="/desk" className="workspace-brand" onClick={() => setOpen(false)}><span className="workspace-logo">a<span>↗</span></span><span>agentic<small>FUTURES WORKSPACE</small></span></Link>
      <div className="workspace-local"><i /> LOCAL WORKSPACE <span>01</span></div>
      <Link href="/desk?new=1" className="workspace-new" onClick={event => { setOpen(false); if (pathname === "/desk") { event.preventDefault(); window.dispatchEvent(new Event("agentic:new-conversation")); } }}><span>＋</span> New conversation <span>↗</span></Link>
      <nav aria-label="Workspace tools">{groups.map(group => <div className="workspace-nav-group" key={group.label}><div className="workspace-nav-label">{group.label}</div>{group.items.map(([href, label, icon]) => <Link key={href} href={href} className={`workspace-nav-link ${pathname === href ? "is-active" : ""}`} aria-current={pathname === href ? "page" : undefined} onClick={() => setOpen(false)}><span aria-hidden="true">{icon}</span>{label}{pathname === href ? <i /> : null}</Link>)}</div>)}</nav>
      <div className="workspace-sidebar-bottom"><div className="workspace-mode"><span>◇</span><div>OpenAI research desk<small>Agent tools cannot place orders.</small></div><i /></div><Link href="/desk#connection" className="workspace-settings" onClick={() => setOpen(false)}>⚙ <span>Desk connection</span><span>↗</span></Link><div className="workspace-credit">FuturesMarketRadar + Agentic<br />Desk source: Galleon Labs · MIT</div></div>
    </aside>
    <div className="workspace-main"><header className="workspace-topbar"><div><span>Workspace</span><b>/</b><strong>{active?.[1] ?? "Trading tools"}</strong></div><div className="workspace-topbar-right"><i /> Personal trading copilot <span>LOCAL</span></div></header><div id="workspace-content" tabIndex={-1}>{children}</div><footer className="workspace-footer"><span>AGENTIC × FUTURES MARKET RADAR</span><span>Evidence first. Your decisions.</span></footer></div>
  </div>;
}
