import { AppFrame } from "@/components/app-frame";

const strategyCards = [
  {
    name: "Rob Hoffman IRB",
    type: "Expert Advisor",
    status: "Draft",
    description: "Trend overlay plus IRB confirmation, risk module, and study-only/live switch.",
  },
  {
    name: "Sleeping Giant Scout",
    type: "Indicator",
    status: "Research",
    description: "Marks abnormal range and volume expansion against a median candle baseline.",
  },
  {
    name: "Risk Gate Core",
    type: "MQH Library",
    status: "Shared",
    description: "Reusable max loss, position size, spread, session, and emergency-stop checks.",
  },
];

const pipelineSteps = [
  "Design strategy rules in this app",
  "Generate .mq5 and .mqh files from templates",
  "Open in MetaEditor for compile checks",
  "Backtest and optimize inside MT5",
  "Upload test results back into the forge",
];

const templateFiles = [
  "Experts/Evans_IRB_EA.mq5",
  "Indicators/Evans_Overlay_IRB.mq5",
  "Include/TrendOverlay.mqh",
  "Include/IRBDetector.mqh",
  "Include/RiskManager.mqh",
  "Include/TradeManager.mqh",
];

const inputRows = [
  ["Strategy", "Rob Hoffman IRB"],
  ["Trend filter", "EMA overlay"],
  ["Fast / Slow / Primary / Long", "8 / 21 / 50 / 200"],
  ["Risk reward", "1:2"],
  ["Trade mode", "Study only"],
  ["Execution layer", "MQL5 inside MT5"],
];

function MiniPanel({ title, eyebrow, children }: { title: string; eyebrow: string; children: React.ReactNode }) {
  return (
    <section className="radar-card p-5 sm:p-6">
      <div className="radar-chip">{eyebrow}</div>
      <h2 className="mt-3 text-2xl font-semibold text-[var(--radar-ink)]">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function StrategyForgePage() {
  return (
    <AppFrame
      current="strategy-forge"
      title="Trading Strategy Forge."
      subtitle="A private control room for designing, documenting, versioning, and exporting MQL5 strategy code while MT5 remains the compile, backtest, and execution layer."
      actions={
        <div className="rounded-[18px] border border-amber-300/25 bg-amber-400/10 px-4 py-3 text-sm font-semibold text-amber-100">
          Private workspace concept
        </div>
      }
    >
      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <MiniPanel eyebrow="Forge Overview" title="Strategy management plus MQL5 generation">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
              <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Next.js</div>
              <div className="mt-2 text-lg font-semibold text-[var(--radar-ink)]">Control panel</div>
              <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">Library, templates, parameters, docs, export buttons, and backtest records.</p>
            </div>
            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
              <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">API + DB</div>
              <div className="mt-2 text-lg font-semibold text-[var(--radar-ink)]">Strategy memory</div>
              <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">Stores versions, presets, changelogs, generated files, licenses, and test uploads.</p>
            </div>
            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
              <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">MQL5 + MT5</div>
              <div className="mt-2 text-lg font-semibold text-[var(--radar-ink)]">Execution layer</div>
              <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">Expert Advisors, indicators, scripts, and libraries still run inside MetaTrader 5.</p>
            </div>
          </div>
        </MiniPanel>

        <MiniPanel eyebrow="Export Pipeline" title="How a strategy becomes code">
          <ol className="space-y-3">
            {pipelineSteps.map((step, index) => (
              <li className="flex gap-3 rounded-[16px] border border-[color:var(--radar-line)] bg-black/15 p-3" key={step}>
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[var(--radar-sea)] text-sm font-semibold text-black">{index + 1}</span>
                <span className="self-center text-sm font-semibold text-[var(--radar-ink)]">{step}</span>
              </li>
            ))}
          </ol>
        </MiniPanel>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <MiniPanel eyebrow="Strategy Library" title="Draft codebase modules">
          <div className="space-y-3">
            {strategyCards.map((strategy) => (
              <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.46)] p-4 transition hover:border-[color:var(--radar-line-strong)]" key={strategy.name}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-[var(--radar-ink)]">{strategy.name}</h3>
                    <p className="mt-1 text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">{strategy.type}</p>
                  </div>
                  <span className="rounded-full border border-[color:var(--radar-line)] px-3 py-1 text-xs font-semibold text-[var(--radar-muted)]">{strategy.status}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--radar-muted)]">{strategy.description}</p>
              </div>
            ))}
          </div>
        </MiniPanel>

        <MiniPanel eyebrow="Parameter Builder" title="Example generated strategy inputs">
          <div className="grid gap-3 sm:grid-cols-2">
            {inputRows.map(([label, value]) => (
              <div className="rounded-[16px] border border-[color:var(--radar-line)] bg-black/15 p-4" key={label}>
                <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">{label}</div>
                <div className="mt-2 text-base font-semibold text-[var(--radar-ink)]">{value}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-[18px] border border-[color:var(--radar-line)] bg-black/20 p-4">
            <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Generated package</div>
            <pre className="mt-3 overflow-auto whitespace-pre-wrap text-sm leading-7 text-[var(--radar-ink)]">{`Evans_RobHoffman_IRB_EA.mq5
Evans_RobHoffman_IRB_Indicator.mq5
settings.json
documentation.md`}</pre>
          </div>
        </MiniPanel>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <MiniPanel eyebrow="MQL5 Codebase" title="Template file map">
          <div className="grid gap-2">
            {templateFiles.map((file) => (
              <div className="rounded-[14px] border border-[color:var(--radar-line)] bg-black/15 px-4 py-3 font-mono text-sm text-[var(--radar-ink)]" key={file}>
                {file}
              </div>
            ))}
          </div>
        </MiniPanel>

        <MiniPanel eyebrow="Backtest Vault" title="Result uploads and review">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
              <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Latest test</div>
              <div className="mt-2 text-xl font-semibold text-[var(--radar-ink)]">Waiting for MT5 export</div>
              <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">Upload HTML, XML, CSV, or screenshots from the MT5 Strategy Tester.</p>
            </div>
            <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4">
              <div className="text-xs uppercase tracking-[0.14em] text-[var(--radar-muted)]">Quality gate</div>
              <div className="mt-2 text-xl font-semibold text-amber-300">Manual review required</div>
              <p className="mt-2 text-sm leading-6 text-[var(--radar-muted)]">No generated strategy should auto-trade until compile, backtest, forward test, and risk checks pass.</p>
            </div>
          </div>
        </MiniPanel>
      </section>
    </AppFrame>
  );
}
