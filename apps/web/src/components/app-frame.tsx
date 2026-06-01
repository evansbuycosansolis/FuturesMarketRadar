import Link from "next/link";
import type { ReactNode } from "react";

type AppFrameProps = {
  current: "dashboard" | "reports" | "risk" | "tradingview";
  title: string;
  subtitle: string;
  actions?: ReactNode;
  children: ReactNode;
};

export function AppFrame({ current, title, subtitle, actions, children }: AppFrameProps) {
  return (
    <div className="radar-shell py-6 sm:py-8 lg:py-10">
      <header className="radar-card mb-6 overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[var(--radar-sun)] via-[var(--radar-sea)] to-[var(--radar-rose)]" />
        <div className="flex flex-col gap-8 p-6 sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="radar-chip">Personal Trading Manager</span>
                <nav className="flex items-center gap-2 text-sm font-medium text-[var(--radar-muted)]">
                  <Link className={current === "dashboard" ? "nav-link nav-link-active" : "nav-link"} href="/dashboard">
                    Dashboard
                  </Link>
                  <Link className={current === "reports" ? "nav-link nav-link-active" : "nav-link"} href="/reports">
                    Reports
                  </Link>
                  <Link className={current === "risk" ? "nav-link nav-link-active" : "nav-link"} href="/risk">
                    Risk
                  </Link>
                  <Link className={current === "tradingview" ? "nav-link nav-link-active" : "nav-link"} href="/tradingview">
                    TradingView
                  </Link>
                </nav>
              </div>
              <div className="space-y-3">
                <h1 className="max-w-4xl text-3xl font-semibold tracking-tight text-[var(--radar-ink)] sm:text-4xl lg:text-5xl">
                  {title}
                </h1>
                <p className="max-w-3xl text-base leading-7 text-[var(--radar-muted)] sm:text-lg">{subtitle}</p>
              </div>
            </div>
            {actions ? <div className="flex shrink-0 flex-wrap gap-3">{actions}</div> : null}
          </div>
        </div>
      </header>
      <main className="space-y-6">{children}</main>
    </div>
  );
}
