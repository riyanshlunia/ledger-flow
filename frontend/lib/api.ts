/**
 * LedgerFlow Agent — API Client
 * Typed fetch layer for all backend endpoints.
 */

const BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/v1").replace(/\/$/, "");

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status}: ${err}`);
  }
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface DashboardStats {
  entity_id: string;
  entity_name: string;
  current_balance: number;
  currency: string;
  balance_as_of: string | null;
  total_bank_transactions: number;
  matched_count: number;
  pending_review_count: number;
  unmatched_count: number;
  match_rate_pct: number;
  open_escalations: number;
  open_invoices_total: number;
  open_bills_total: number;
  forecast_next_4_weeks_net: number;
}

export interface ReconciliationMatch {
  match_id: string;
  bank_tx_id: string;
  erp_tx_id: string | null;
  entity_id: string;
  match_status: string;
  match_method: string;
  confidence_score: number;
  amount_variance: number | null;
  natural_language: string | null;
  matched_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface ReconciliationList {
  total: number;
  page: number;
  page_size: number;
  items: ReconciliationMatch[];
}

export interface ForecastBucket {
  forecast_id: string;
  period_start: string;
  period_end: string;
  granularity: string;
  opening_balance: number;
  total_inflows: number;
  total_outflows: number;
  net_cash_flow: number;
  closing_balance: number;
  p10_closing: number;
  p90_closing: number;
  model_version: string;
  is_stale: boolean;
  natural_language: string | null;
}

export interface ForecastList {
  entity_id: string;
  currency: string;
  generated_at: string;
  is_stale: boolean;
  scenario_id: string | null;
  buckets: ForecastBucket[];
}

export interface ForecastDriver {
  driver_id: string;
  driver_type: string;
  amount: number;
  probability: number | null;
  source_type: string | null;
  counterparty_name: string | null;
  expected_date: string | null;
  notes: string | null;
}

export interface ForecastDriversResponse {
  forecast_id: string;
  drivers: ForecastDriver[];
  summary_by_type: Record<string, number>;
}

export interface Scenario {
  scenario_id: string;
  name: string;
  description: string | null;
  parameters: Record<string, unknown>;
  is_system_scenario: boolean;
  created_at: string;
}

export interface ScenarioDeltaBucket {
  period_start: string;
  base_net_flow: number;
  scenario_net_flow: number;
  delta: number;
  delta_pct: number;
  base_closing: number;
  scenario_closing: number;
  policy_breaches: string[];
}

export interface ScenarioDelta {
  scenario_id: string;
  scenario_name: string;
  buckets: ScenarioDeltaBucket[];
  total_delta: number;
  natural_language: string;
  risk_flags: string[];
}

export interface Escalation {
  escalation_id: string;
  entity_id: string;
  trigger_type: string;
  severity: string;
  status: string;
  natural_language: string | null;
  agent_proposal: Record<string, unknown> | null;
  alternatives_json: unknown[] | null;
  sla_deadline: string | null;
  created_at: string;
  policy_id: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
}

export interface EscalationList {
  total: number;
  page: number;
  page_size: number;
  items: Escalation[];
}

export interface AuditEntry {
  log_id: string;
  timestamp: string;
  event_type: string;
  agent_id: string | null;
  agent_version: string;
  user_id: string | null;
  entity_id: string | null;
  input_summary: Record<string, unknown> | null;
  output_summary: Record<string, unknown> | null;
  policies_evaluated: string[] | null;
  policies_breached: string[] | null;
  hmac_sig: string;
  notes: string | null;
}

export interface AuditList {
  total: number;
  page: number;
  page_size: number;
  entries: AuditEntry[];
}

// ── API Functions ──────────────────────────────────────────────────────────

const ENTITY = "ENTITY-US-001";

export const api = {
  importTransactions: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`${BASE}/transactions/import?entity_id=${ENTITY}`, {
      method: "POST",
      body,
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return res.json() as Promise<{ filename: string; imported: number; skipped: number; invalid: Array<{ row: number; reason: string }> }>;
  },

  // Dashboard
  getDashboardStats: () =>
    apiFetch<DashboardStats>(`/dashboard/stats?entity_id=${ENTITY}`),

  // Reconciliation
  runReconciliation: () =>
    apiFetch<{ status: string; results: Record<string, number> }>(
      `/reconciliations/run?entity_id=${ENTITY}`,
      { method: "POST" }
    ),
  listReconciliations: (status?: string, page = 1, pageSize = 50) => {
    const params = new URLSearchParams({
      entity_id: ENTITY,
      page: String(page),
      page_size: String(pageSize),
    });
    if (status) params.set("status", status);
    return apiFetch<ReconciliationList>(`/reconciliations?${params}`);
  },
  explainReconciliation: (matchId: string) =>
    apiFetch<Record<string, unknown>>(`/reconciliations/${matchId}/explain`),
  reviewReconciliation: (
    matchId: string,
    decision: string,
    reviewer: string,
    note?: string
  ) =>
    apiFetch(`/reconciliations/${matchId}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, reviewer, note }),
    }),

  // Forecasts
  runForecast: (scenarioId?: string) => {
    const params = new URLSearchParams({ entity_id: ENTITY });
    if (scenarioId) params.set("scenario_id", scenarioId);
    return apiFetch(`/forecasts/run?${params}`, { method: "POST" });
  },
  getCurrentForecast: (scenarioId?: string) => {
    const params = new URLSearchParams({ entity_id: ENTITY });
    if (scenarioId) params.set("scenario_id", scenarioId);
    return apiFetch<ForecastList>(`/forecasts/current?${params}`);
  },
  getForecastDrivers: (forecastId: string) =>
    apiFetch<ForecastDriversResponse>(`/forecasts/${forecastId}/drivers`),
  explainForecast: (forecastId: string) =>
    apiFetch<Record<string, unknown>>(`/forecasts/${forecastId}/explain`),

  // Scenarios
  listScenarios: () => apiFetch<Scenario[]>(`/scenarios`),
  createScenario: (body: {
    name: string;
    description?: string;
    parameters: Record<string, unknown>;
  }) =>
    apiFetch<Scenario>(`/scenarios`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getScenarioDelta: (scenarioId: string) =>
    apiFetch<ScenarioDelta>(
      `/scenarios/${scenarioId}/delta?entity_id=${ENTITY}`
    ),

  // Escalations
  listEscalations: (status?: string, severity?: string, page = 1) => {
    const params = new URLSearchParams({
      entity_id: ENTITY,
      page: String(page),
      page_size: "50",
    });
    if (status) params.set("status", status);
    if (severity) params.set("severity", severity);
    return apiFetch<EscalationList>(`/escalations?${params}`);
  },
  resolveEscalation: (
    escalationId: string,
    decision: string,
    resolvedBy: string,
    note?: string
  ) =>
    apiFetch(`/escalations/${escalationId}/decisions`, {
      method: "POST",
      body: JSON.stringify({
        decision,
        resolved_by: resolvedBy,
        note,
      }),
    }),

  // Audit
  getAuditLog: (eventType?: string, agentId?: string, page = 1) => {
    const params = new URLSearchParams({
      entity_id: ENTITY,
      page: String(page),
      page_size: "50",
    });
    if (eventType) params.set("event_type", eventType);
    if (agentId) params.set("agent_id", agentId);
    return apiFetch<AuditList>(`/audit?${params}`);
  },
};
