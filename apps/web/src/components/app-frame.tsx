import type { ReactNode } from "react";
type AppFrameProps = {
  current: "dashboard" | "markets" | "scanners" | "recovery-fade" | "research" | "reports" | "risk" | "simulator" | "strategy-forge" | "tradingview" | "desk";
  title: string;
  subtitle: string;
  actions?: ReactNode;
  children: ReactNode;
};
export function AppFrame({ current, title, subtitle, actions, children }: AppFrameProps) {
  return <div className="radar-shell workspace-page" data-workspace={current}>
    <header className="workspace-page-heading"><div><div className="workspace-eyebrow">YOUR INTELLIGENCE, ORGANIZED</div><h1>{title}</h1><p>{subtitle}</p></div>{actions ? <div className="workspace-page-actions">{actions}</div> : null}</header>
    <main className="space-y-6">{children}</main>
  </div>;
}
