import { AppFrame } from "@/components/app-frame";
import { ReportHistoryCard } from "@/components/report-history-card";
import { ReportsOverview } from "@/components/reports-overview";
import { RunScanButton } from "@/components/run-scan-button";
import { getReportHistory } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const reports = await getReportHistory();

  return (
    <AppFrame
      current="reports"
      title="Read the radar like a tape, not a black box."
      subtitle="This archive turns every stored scan into a visual report sheet so you can spot leadership, regime shifts, and watchlist carryover without digging through dense text."
      actions={<RunScanButton />}
    >
      {reports.length === 0 ? (
        <section className="radar-card p-8 text-sm leading-7 text-[var(--radar-muted)]">
          No reports are stored yet. Generate the first scan from the dashboard or with the FastAPI `POST /api/scanner/run-now` endpoint.
        </section>
      ) : (
        <div className="space-y-6">
          <ReportsOverview reports={reports} />
          <section className="space-y-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="radar-chip">Report Archive</div>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Stored scans, reorganized for fast reading</h2>
              </div>
              <p className="max-w-2xl text-sm leading-7 text-[var(--radar-muted)]">
                Each card below breaks a single report into highlights, signal winners, AI commentary, and the watchlist that still needed confirmation.
              </p>
            </div>

            <div className="space-y-6">
              {reports.map((report) => (
                <ReportHistoryCard key={report.id} report={report} />
              ))}
            </div>
          </section>
        </div>
      )}
    </AppFrame>
  );
}
