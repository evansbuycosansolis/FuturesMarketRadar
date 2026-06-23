import {
  AutomationActionResponse,
  AutomationMode,
  AssetResearchResponse,
  AutomationSummary,
  ArmManagedExitRequest,
  ArmManagedExitResponse,
  DisarmManagedExitResponse,
  ExchangeStatusResponse,
  FuturesAnomalyResponse,
  HealthStatus,
  OrderExecutionResponse,
  CopilotOverview,
  ManualSignalRequest,
  MarketChangeTrajectoryResponse,
  MarketOverviewResponse,
  MarketIntelligenceSummary,
  MarketQualityResponse,
  MarketSessionMomentumResponse,
  PaperSummary,
  Report,
  ReportHistoryResponse,
  RiskPolicy,
  RiskSummary,
  RunExitAutomationResponse,
  SignalActionResponse,
  SleepingGiantResponse,
  TradeCheckRequest,
  TradeCheckResponse,
  TradePlanRequest,
  TradePlanResponse,
  TradingViewWebhookResponse,
  SignalHeatmap,
} from "./types";

const serverBaseUrl = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const clientBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function getApiBaseUrl(): string {
  return typeof window === "undefined" ? serverBaseUrl : clientBaseUrl;
}

async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Request failed for ${path}: ${response.status}${detail ? ` ${detail}` : ""}`);
  }

  return (await response.json()) as T;
}

async function readOptionalJson<T>(path: string): Promise<T | null> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, { cache: "no-store" });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed for ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  return readJson<HealthStatus>("/api/health");
}

export async function getExchangeStatus(): Promise<ExchangeStatusResponse> {
  return readJson<ExchangeStatusResponse>("/api/exchanges/status");
}

export async function getLatestReport(): Promise<Report | null> {
  return readOptionalJson<Report>("/api/reports/latest");
}

export async function getReportHistory(): Promise<Report[]> {
  const data = await readJson<ReportHistoryResponse>("/api/reports/history?limit=18");
  return data.items;
}

export async function getMarketOverview(): Promise<MarketOverviewResponse> {
  return readJson<MarketOverviewResponse>("/api/market/overview?limit=120");
}

export async function getMarketQuality(): Promise<MarketQualityResponse> {
  return readJson<MarketQualityResponse>("/api/market/quality");
}

export async function getMarketSessionMomentum(): Promise<MarketSessionMomentumResponse> {
  return readJson<MarketSessionMomentumResponse>("/api/market/session-momentum?limit=40&lookback_hours=24");
}

export async function getMarketChangeTrajectory(): Promise<MarketChangeTrajectoryResponse> {
  return readJson<MarketChangeTrajectoryResponse>("/api/market/change-trajectory?limit=20&lookback_hours=8");
}

export async function getSleepingGiants(
  timeframe: "1H" | "4H" = "1H",
  mode: "strict" | "recent" = "strict",
): Promise<SleepingGiantResponse> {
  return readJson<SleepingGiantResponse>(
    `/api/market/sleeping-giants?limit=12&lookback_days=21&timeframe=${timeframe}&mode=${mode}`,
  );
}

export async function getFuturesAnomalies(): Promise<FuturesAnomalyResponse> {
  return readJson<FuturesAnomalyResponse>("/api/market/futures-anomalies?limit=12&lookback_hours=24&max_symbols=80");
}

export async function researchAsset(query: string): Promise<AssetResearchResponse> {
  return readJson<AssetResearchResponse>("/api/research/asset", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function runScanNow(): Promise<{ report: Report | null; message: string }> {
  const data = await readJson<{ ok: boolean; report: Report | null; message?: string }>("/api/scanner/run-now", {
    method: "POST",
  });
  return { report: data.report, message: data.message ?? "" };
}

export async function getRiskSummary(): Promise<RiskSummary> {
  return readJson<RiskSummary>("/api/risk/summary");
}

export async function syncRiskNow(): Promise<RiskSummary> {
  const data = await readJson<{ ok: boolean; summary: RiskSummary }>("/api/risk/sync-now", {
    method: "POST",
  });
  return data.summary;
}

export async function updateRiskPolicy(policy: Omit<RiskPolicy, "id" | "name" | "created_at" | "updated_at">): Promise<RiskPolicy> {
  return readJson<RiskPolicy>("/api/risk/policies", {
    method: "PUT",
    body: JSON.stringify(policy),
  });
}

export async function checkTradeRisk(payload: TradeCheckRequest): Promise<TradeCheckResponse> {
  return readJson<TradeCheckResponse>("/api/risk/check-trade", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function planTrade(payload: TradePlanRequest): Promise<TradePlanResponse> {
  return readJson<TradePlanResponse>("/api/risk/plan-trade", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function placeTradeOrder(
  payload: TradeCheckRequest & {
    client_order_id?: string;
    take_profit_price?: number;
    arm_exit_automation?: boolean;
  },
): Promise<OrderExecutionResponse> {
  return readJson<OrderExecutionResponse>("/api/trading/order", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function cancelAllOrders(symbol: string): Promise<void> {
  await readJson<{ ok: boolean; symbol: string; message: string }>("/api/trading/cancel-all", {
    method: "POST",
    body: JSON.stringify({ symbol }),
  });
}

export async function armManagedExit(payload: ArmManagedExitRequest): Promise<ArmManagedExitResponse> {
  return readJson<ArmManagedExitResponse>("/api/trading/managed-exits/arm", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function disarmManagedExit(planId: number): Promise<DisarmManagedExitResponse> {
  return readJson<DisarmManagedExitResponse>(`/api/trading/managed-exits/${planId}/disarm`, {
    method: "POST",
  });
}

export async function runExitAutomationNow(): Promise<RunExitAutomationResponse> {
  return readJson<RunExitAutomationResponse>("/api/trading/managed-exits/run-now", {
    method: "POST",
  });
}

export async function getAutomationSummary(): Promise<AutomationSummary> {
  return readJson<AutomationSummary>("/api/automation/summary");
}

export async function getCopilotOverview(): Promise<CopilotOverview> {
  return readJson<CopilotOverview>("/api/copilot/overview");
}

export async function getSignalHeatmap(): Promise<SignalHeatmap> {
  return readJson<SignalHeatmap>("/api/copilot/signal-heatmap");
}

export async function getPaperSummary(): Promise<PaperSummary> {
  return readJson<PaperSummary>("/api/paper/summary");
}

export async function getMarketIntelligenceSummary(): Promise<MarketIntelligenceSummary> {
  return readJson<MarketIntelligenceSummary>("/api/intelligence/summary");
}

export async function updateAutomationMode(mode: AutomationMode): Promise<AutomationSummary> {
  const response = await readJson<{ id: number }>("/api/automation/control", {
    method: "PUT",
    body: JSON.stringify({ mode }),
  });
  if (!response.id) {
    throw new Error("Automation control update did not return a control record.");
  }
  return getAutomationSummary();
}

export async function engageKillSwitch(reason: string): Promise<AutomationActionResponse> {
  return readJson<AutomationActionResponse>("/api/automation/kill-switch/engage", {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function releaseKillSwitch(reason: string): Promise<AutomationActionResponse> {
  return readJson<AutomationActionResponse>("/api/automation/kill-switch/release", {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function reconcileAutomationNow(): Promise<AutomationActionResponse> {
  return readJson<AutomationActionResponse>("/api/automation/reconcile-now", {
    method: "POST",
  });
}

export async function runAutomationWatchdogNow(): Promise<AutomationActionResponse> {
  return readJson<AutomationActionResponse>("/api/automation/watchdog/run-now", {
    method: "POST",
  });
}

export async function approveAutomationSignal(signalId: number): Promise<SignalActionResponse> {
  return readJson<SignalActionResponse>(`/api/automation/signals/${signalId}/approve`, {
    method: "POST",
  });
}

export async function rejectAutomationSignal(signalId: number, reason: string): Promise<SignalActionResponse> {
  return readJson<SignalActionResponse>(`/api/automation/signals/${signalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function sendTradingViewWebhook(
  payload: Record<string, unknown>,
  secret?: string,
): Promise<TradingViewWebhookResponse> {
  return readJson<TradingViewWebhookResponse>("/api/webhooks/tradingview", {
    method: "POST",
    headers: secret ? { "X-FMR-Webhook-Secret": secret } : undefined,
    body: JSON.stringify(payload),
  });
}

export async function sendManualSignal(payload: ManualSignalRequest): Promise<TradingViewWebhookResponse> {
  return readJson<TradingViewWebhookResponse>("/api/copilot/manual-signal", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type BackendProbe =
  | { ok: true; health: HealthStatus; latestReport: Report | null; exchangeStatus: ExchangeStatusResponse; marketIntelligence: MarketIntelligenceSummary | null }
  | { ok: false; error: string; baseUrl: string };

export async function probeBackend(): Promise<BackendProbe> {
  const baseUrl = getApiBaseUrl();
  try {
    const [health, latestReport, exchangeStatus, marketIntelligence] = await Promise.all([
      getHealthStatus(),
      getLatestReport(),
      getExchangeStatus(),
      getMarketIntelligenceSummary().catch(() => null),
    ]);
    return { ok: true, health, latestReport, exchangeStatus, marketIntelligence };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown backend error";
    return { ok: false, error: message, baseUrl };
  }
}
