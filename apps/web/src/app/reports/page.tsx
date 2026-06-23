import { AppFrame } from "@/components/app-frame";
import { ReportHistoryCard } from "@/components/report-history-card";
import { RunScanButton } from "@/components/run-scan-button";
import { getLatestReport } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const report = await getLatestReport();

  return (
    <AppFrame
      current="reports"
      title="Latest radar report."
      subtitle="Shows only the most current completed scan so the decision-support read stays clean and focused."
      actions={<RunScanButton />}
    >
      {!report ? (
        <section className="radar-card p-8 text-sm leading-7 text-[var(--radar-muted)]">
          No reports are stored yet. Generate the first scan from the dashboard or with the FastAPI `POST /api/scanner/run-now` endpoint.
        </section>
      ) : (
        <ReportHistoryCard report={report} />
      )}
    </AppFrame>
  );
}
