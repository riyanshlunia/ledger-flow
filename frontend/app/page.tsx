"use client";

import { useState, useEffect, useCallback } from "react";
import { api, DashboardStats, ReconciliationList, ForecastList, EscalationList, AuditList, Scenario } from "../lib/api";

// ─── View type ────────────────────────────────────────────────────────────────
type View = "dashboard" | "reconciliation" | "forecasts" | "escalations" | "audit" | "scenarios";

// ─── Utility helpers ──────────────────────────────────────────────────────────
function fmt(n: number, decimals = 0) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function fmtCurrency(n: number, currency = "USD") {
  if (Math.abs(n) >= 1_000_000) return `$${fmt(n / 1_000_000, 1)}M`;
  if (Math.abs(n) >= 1_000) return `$${fmt(n / 1_000, 0)}K`;
  return `$${fmt(n, 0)}`;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtDateTime(s: string) {
  return new Date(s).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    MATCHED: "badge-green",
    HUMAN_CONFIRMED: "badge-green",
    PENDING_REVIEW: "badge-amber",
    UNMATCHED: "badge-red",
    HUMAN_REJECTED: "badge-red",
    OPEN: "badge-amber",
    IN_REVIEW: "badge-blue",
    RESOLVED: "badge-green",
    OVERRIDDEN: "badge-gray",
    CRITICAL: "badge-red",
    HIGH: "badge-amber",
    MEDIUM: "badge-blue",
    LOW: "badge-gray",
  };
  return map[status] || "badge-gray";
}

// ─── Confidence bar ───────────────────────────────────────────────────────────
function ConfBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="confidence-bar">
      <div className="confidence-track">
        <div className="confidence-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: 11, color, fontFamily: "var(--font-mono)", minWidth: 32 }}>
        {pct}%
      </span>
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { view: "dashboard" as View, icon: "", label: "Dashboard" },
  { view: "reconciliation" as View, icon: "", label: "Reconciliation" },
  { view: "forecasts" as View, icon: "", label: "Forecasts" },
  { view: "scenarios" as View, icon: "", label: "Scenarios" },
  { view: "escalations" as View, icon: "", label: "Escalations" },
  { view: "audit" as View, icon: "", label: "Audit Trail" },
];

function Sidebar({
  active,
  onNav,
  openEscalations,
}: {
  active: View;
  onNav: (v: View) => void;
  openEscalations: number;
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div>
          <div className="sidebar-logo-text">ledger flo</div>
          <div className="sidebar-logo-sub">AGENT v1.0.0</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        <div className="nav-section-label">Operations</div>
        {NAV_ITEMS.map(({ view, icon, label }) => (
          <button
            key={view}
            id={`nav-${view}`}
            className={`nav-item${active === view ? " active" : ""}`}
            onClick={() => onNav(view)}
          >
            <span className="nav-icon">{icon}</span>
            {label}
            {view === "escalations" && openEscalations > 0 && (
              <span className="nav-badge">{openEscalations}</span>
            )}
          </button>
        ))}
      </nav>
      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--border)" }}>
        <div style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.6 }}>
          Entity: ENTITY-US-001
          <br />
          <span style={{ color: "var(--accent-green)" }}>API Connected</span>
        </div>
      </div>
    </aside>
  );
}

// ─── Dashboard View ───────────────────────────────────────────────────────────
function DashboardView() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runMsg, setRunMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const s = await api.getDashboardStats();
      setStats(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runAll = async () => {
    setRunning(true);
    setRunMsg("");
    try {
      await api.runReconciliation();
      await api.runForecast();
      await load();
      setRunMsg("Reconciliation + Forecast agents completed successfully.");
    } catch (e: unknown) {
      setRunMsg(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setRunning(false);
    }
  };

  if (loading) return (
    <div className="loading-state">
      <div className="spinner" />
      Loading dashboard...
    </div>
  );

  if (!stats) return (
    <div className="empty-state">
      <div className="empty-icon">[!]</div>
      <p>Could not load dashboard stats. Is the API running?</p>
    </div>
  );

  const matchRingColor = stats.match_rate_pct >= 90 ? "#10b981" : stats.match_rate_pct >= 70 ? "#f59e0b" : "#ef4444";

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            {stats.entity_name} · {stats.currency} · Balance as of{" "}
            {stats.balance_as_of ? fmtDate(stats.balance_as_of) : "–"}
          </p>
        </div>
        <button id="btn-run-all" className="btn btn-primary" onClick={runAll} disabled={running}>
          {running ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Running...</> : "Run Agents"}
        </button>
      </div>

      <div className="page-body">
        {runMsg && (
          <div className={`alert mb-16 ${runMsg.startsWith("Error") ? "alert-error" : "alert-ok"}`}>
            <span>{runMsg.startsWith("Error") ? "[Error]" : "[Success]"}</span>
            <span>{runMsg}</span>
          </div>
        )}

        {/* KPI row */}
        <div className="stat-grid mb-24">
          <div className="stat-card">
            <div className="stat-label">Current Balance</div>
            <div className="stat-value">{fmtCurrency(stats.current_balance)}</div>
            <div className="stat-sub">{stats.currency}</div>
          </div>
          <div className={`stat-card ${stats.forecast_next_4_weeks_net >= 0 ? "green" : "red"}`}>
            <div className="stat-label">4-Week Forecast Net</div>
            <div className={`stat-value ${stats.forecast_next_4_weeks_net >= 0 ? "green" : "red"}`}>
              {stats.forecast_next_4_weeks_net >= 0 ? "+" : ""}{fmtCurrency(stats.forecast_next_4_weeks_net)}
            </div>
            <div className="stat-sub">Rolling 4 weeks</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Open AR</div>
            <div className="stat-value amber">{fmtCurrency(stats.open_invoices_total)}</div>
            <div className="stat-sub">Outstanding invoices</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Open AP</div>
            <div className="stat-value">{fmtCurrency(stats.open_bills_total)}</div>
            <div className="stat-sub">Outstanding bills</div>
          </div>
        </div>

        {/* Reconciliation + Escalation row */}
        <div className="grid-2 mb-24">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Reconciliation Status</span>
              <span style={{ fontSize: 12, color: matchRingColor, fontWeight: 700 }}>
                {stats.match_rate_pct}% Match Rate
              </span>
            </div>
            <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
              {/* Ring */}
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
                <circle
                  cx="50" cy="50" r="40" fill="none"
                  stroke={matchRingColor} strokeWidth="10"
                  strokeDasharray={`${stats.match_rate_pct * 2.513} 251.3`}
                  strokeLinecap="round"
                  transform="rotate(-90 50 50)"
                  style={{ transition: "stroke-dasharray 0.8s ease" }}
                />
                <text x="50" y="54" textAnchor="middle" fontSize="16" fontWeight="800" fill={matchRingColor}>
                  {stats.match_rate_pct}%
                </text>
              </svg>
              <div style={{ flex: 1 }}>
                {[
                  { label: "Auto Matched", count: stats.matched_count, color: "#10b981" },
                  { label: "Pending Review", count: stats.pending_review_count, color: "#f59e0b" },
                  { label: "Unmatched", count: stats.unmatched_count, color: "#ef4444" },
                ].map(({ label, count, color }) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                    <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: color, marginRight: 6 }} />
                      {label}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 700, color }}>{fmt(count)}</span>
                  </div>
                ))}
                <div style={{ marginTop: 8, fontSize: 11, color: "var(--text-muted)" }}>
                  {fmt(stats.total_bank_transactions)} total bank transactions
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Governance</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 12,
                  background: stats.open_escalations > 0 ? "rgba(239,68,68,0.12)" : "rgba(16,185,129,0.12)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 24,
                }}>
                  {stats.open_escalations > 0 ? "" : "[OK]"}
                </div>
                <div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: stats.open_escalations > 0 ? "var(--accent-red)" : "var(--accent-green)" }}>
                    {stats.open_escalations}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Open Escalations</div>
                </div>
              </div>
              <div className={`alert ${stats.open_escalations === 0 ? "alert-ok" : "alert-warn"}`}>
                <span>{stats.open_escalations === 0 ? "[OK]" : "[!]"}</span>
                <span style={{ fontSize: 12 }}>
                  {stats.open_escalations === 0
                    ? "All escalations resolved. System operating normally."
                    : `${stats.open_escalations} escalation(s) require human review within SLA window.`}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Quick actions */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Quick Actions</span>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {[
              { label: " Run Reconciliation", id: "btn-run-recon", action: async () => { await api.runReconciliation(); await load(); } },
              { label: " Run Forecast", id: "btn-run-forecast", action: async () => { await api.runForecast(); await load(); } },
            ].map(({ label, id, action }) => (
              <button key={id} id={id} className="btn btn-ghost" onClick={action} disabled={running}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ─── Reconciliation View ──────────────────────────────────────────────────────
function ReconciliationView() {
  const [data, setData] = useState<ReconciliationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [explain, setExplain] = useState<Record<string, unknown> | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.listReconciliations(filter || undefined, page);
      setData(d);
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => { load(); }, [load]);

  const runAgent = async () => {
    setRunning(true);
    try {
      await api.runReconciliation();
      await load();
    } finally {
      setRunning(false);
    }
  };

  const openExplain = async (matchId: string) => {
    setSelected(matchId);
    setExplain(null);
    setExplainLoading(true);
    try {
      const e = await api.explainReconciliation(matchId);
      setExplain(e);
    } finally {
      setExplainLoading(false);
    }
  };

  const STATUSES = ["", "MATCHED", "PENDING_REVIEW", "UNMATCHED", "HUMAN_CONFIRMED", "HUMAN_REJECTED"];

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Reconciliation</h1>
          <p className="page-subtitle">Autonomous bank-to-ERP matching with confidence scoring</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <select
            id="recon-status-filter"
            className="btn btn-ghost btn-sm"
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(1); }}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s} style={{ background: "var(--bg-surface)" }}>
                {s || "All Statuses"}
              </option>
            ))}
          </select>
          <button id="btn-run-reconciliation" className="btn btn-primary btn-sm" onClick={runAgent} disabled={running}>
            {running ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Running…</> : " Run Agent"}
          </button>
        </div>
      </div>

      <div className="page-body">
        <div style={{ display: "flex", gap: 20 }}>
          <div style={{ flex: 1 }}>
            {loading ? (
              <div className="loading-state"><div className="spinner" />Loading…</div>
            ) : !data || data.items.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon"></div>
                <p>No reconciliation matches found. Run the agent to process bank transactions.</p>
              </div>
            ) : (
              <>
                <div className="table-wrap mb-16">
                  <table>
                    <thead>
                      <tr>
                        <th>Bank TX</th>
                        <th>Status</th>
                        <th>Method</th>
                        <th>Confidence</th>
                        <th>Variance</th>
                        <th>Matched At</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((m) => (
                        <tr key={m.match_id} style={{ cursor: "pointer" }} onClick={() => openExplain(m.match_id)}>
                          <td className="td-mono">{m.bank_tx_id.slice(0, 8)}…</td>
                          <td><span className={`badge ${statusBadge(m.match_status)}`}>{m.match_status}</span></td>
                          <td><span className="badge badge-gray">{m.match_method}</span></td>
                          <td style={{ minWidth: 140 }}><ConfBar score={m.confidence_score} /></td>
                          <td className="td-mono">
                            {m.amount_variance != null
                              ? <span style={{ color: Math.abs(m.amount_variance) > 0.01 ? "var(--accent-amber)" : "var(--text-muted)" }}>
                                  {m.amount_variance >= 0 ? "+" : ""}{fmt(m.amount_variance, 2)}
                                </span>
                              : <span style={{ color: "var(--text-muted)" }}>—</span>}
                          </td>
                          <td style={{ fontSize: 12, color: "var(--text-muted)" }}>{fmtDateTime(m.matched_at)}</td>
                          <td>
                            <button
                              id={`btn-explain-${m.match_id}`}
                              className="btn btn-ghost btn-xs"
                              onClick={(e) => { e.stopPropagation(); openExplain(m.match_id); }}
                            >
                              Explain
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12, color: "var(--text-muted)" }}>
                  <span>{fmt(data.total)} total matches</span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn-ghost btn-xs" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
                    <span style={{ padding: "3px 8px" }}>Page {page}</span>
                    <button className="btn btn-ghost btn-xs" disabled={data.items.length < 50} onClick={() => setPage(p => p + 1)}>Next →</button>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Explain panel */}
          {selected && (
            <div style={{ width: 360, flexShrink: 0 }}>
              <div className="card" style={{ position: "sticky", top: 24 }}>
                <div className="card-header">
                  <span className="card-title">Explanation</span>
                  <button className="btn btn-ghost btn-xs" onClick={() => { setSelected(null); setExplain(null); }}>✕</button>
                </div>
                {explainLoading ? (
                  <div className="loading-state" style={{ padding: 24 }}><div className="spinner" />Loading…</div>
                ) : explain ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <span className="card-title">Confidence</span>
                      <ConfBar score={(explain.confidence_score as number) || 0} />
                    </div>
                    {Boolean(explain.natural_language) && (
                      <div className="escalation-nl" style={{ fontSize: 12 }}>
                        {explain.natural_language as string}
                      </div>
                    )}
                    {Boolean(explain.feature_scores) && (
                      <div>
                        <div className="card-title mb-8">Feature Scores</div>
                        {Object.entries(explain.feature_scores as Record<string, number>).map(([k, v]) => (
                          <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 12, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                            <span style={{ color: "var(--text-secondary)" }}>{k.replace(/_/g, " ")}</span>
                            <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-blue)" }}>{((v as number) * 100).toFixed(0)}%</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {Boolean(explain.bank_tx) && (
                      <div>
                        <div className="card-title mb-8">Bank Transaction</div>
                        <pre style={{ fontSize: 10, color: "var(--text-secondary)", background: "rgba(0,0,0,0.2)", padding: 10, borderRadius: 6, overflow: "auto", maxHeight: 120 }}>
                          {JSON.stringify(explain.bank_tx, null, 2)}
                        </pre>
                      </div>
                    )}
                    {Boolean(explain.erp_tx) && (
                      <div>
                        <div className="card-title mb-8">ERP Transaction</div>
                        <pre style={{ fontSize: 10, color: "var(--text-secondary)", background: "rgba(0,0,0,0.2)", padding: 10, borderRadius: 6, overflow: "auto", maxHeight: 120 }}>
                          {JSON.stringify(explain.erp_tx, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ─── Forecast View ────────────────────────────────────────────────────────────
function ForecastView() {
  const [data, setData] = useState<ForecastList | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [drivers, setDrivers] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.getCurrentForecast();
      setData(d);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runForecast = async () => {
    setRunning(true);
    try {
      await api.runForecast();
      await load();
    } finally {
      setRunning(false);
    }
  };

  const openDrivers = async (forecastId: string) => {
    setSelected(forecastId);
    setDrivers(null);
    const d = await api.getForecastDrivers(forecastId);
    setDrivers(d as unknown as Record<string, unknown>);
  };

  if (loading) return <div className="loading-state"><div className="spinner" />Loading…</div>;

  const buckets = data?.buckets || [];
  const maxAbs = Math.max(...buckets.map(b => Math.max(Math.abs(b.total_inflows), Math.abs(b.total_outflows))), 1);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Cash Flow Forecasts</h1>
          <p className="page-subtitle">
            13-week rolling AR/AP forecast · {data?.currency || "USD"}
            {data?.is_stale && <span className="badge badge-amber" style={{ marginLeft: 8 }}>Stale</span>}
          </p>
        </div>
        <button id="btn-run-forecast" className="btn btn-primary btn-sm" onClick={runForecast} disabled={running}>
          {running ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Running…</> : " Run Forecast"}
        </button>
      </div>

      <div className="page-body">
        {buckets.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"></div>
            <p>No forecast data. Click "Run Forecast" to generate a 13-week projection.</p>
          </div>
        ) : (
          <>
            {/* Summary row */}
            <div className="stat-grid mb-24">
              <div className="stat-card">
                <div className="stat-label">Total Inflows (13w)</div>
                <div className="stat-value green">{fmtCurrency(buckets.reduce((s, b) => s + b.total_inflows, 0))}</div>
              </div>
              <div className="stat-card red">
                <div className="stat-label">Total Outflows (13w)</div>
                <div className="stat-value red">{fmtCurrency(Math.abs(buckets.reduce((s, b) => s + b.total_outflows, 0)))}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Net (13w)</div>
                <div className={`stat-value ${buckets.reduce((s, b) => s + b.net_cash_flow, 0) >= 0 ? "green" : "red"}`}>
                  {fmtCurrency(buckets.reduce((s, b) => s + b.net_cash_flow, 0))}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Closing Balance (W13)</div>
                <div className="stat-value">{fmtCurrency(buckets[buckets.length - 1]?.closing_balance || 0)}</div>
              </div>
            </div>

            {/* Waterfall chart */}
            <div className="card mb-24">
              <div className="card-header">
                <span className="card-title">Weekly Cash Flow — Inflows vs Outflows</span>
                <div style={{ display: "flex", gap: 16, fontSize: 11 }}>
                  <span><span style={{ color: "#10b981" }}>■</span> Inflows</span>
                  <span><span style={{ color: "#ef4444" }}>■</span> Outflows</span>
                  <span><span style={{ color: "#3b82f6" }}>■</span> Net</span>
                </div>
              </div>
              <div className="waterfall-grid">
                {buckets.map((b) => {
                  const inH = Math.round((b.total_inflows / maxAbs) * 120);
                  const outH = Math.round((Math.abs(b.total_outflows) / maxAbs) * 120);
                  const netH = Math.round((Math.abs(b.net_cash_flow) / maxAbs) * 80);
                  return (
                    <div key={b.forecast_id} className="waterfall-col">
                      <div
                        className="waterfall-bar-wrap"
                        onClick={() => openDrivers(b.forecast_id)}
                        title={b.natural_language || ""}
                      >
                        <div style={{ display: "flex", gap: 2, alignItems: "flex-end", height: 140 }}>
                          <div className="waterfall-bar" style={{ height: inH, background: "#10b981", width: "40%" }} />
                          <div className="waterfall-bar" style={{ height: outH, background: "#ef4444", width: "40%" }} />
                          <div className="waterfall-bar" style={{
                            height: netH,
                            background: b.net_cash_flow >= 0 ? "#3b82f6" : "#f59e0b",
                            width: "20%",
                          }} />
                        </div>
                        <div className="waterfall-label">{fmtDate(b.period_start)}</div>
                        <div className="waterfall-value" style={{ color: b.net_cash_flow >= 0 ? "#10b981" : "#ef4444" }}>
                          {b.net_cash_flow >= 0 ? "+" : ""}{fmtCurrency(b.net_cash_flow)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Table */}
            <div style={{ display: "flex", gap: 20 }}>
              <div style={{ flex: 1 }}>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Period</th>
                        <th>Opening</th>
                        <th>Inflows</th>
                        <th>Outflows</th>
                        <th>Net</th>
                        <th>Closing</th>
                        <th>P10–P90 Range</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {buckets.map((b) => (
                        <tr key={b.forecast_id}>
                          <td style={{ fontWeight: 600 }}>
                            {fmtDate(b.period_start)} – {fmtDate(b.period_end)}
                          </td>
                          <td className="td-mono">{fmtCurrency(b.opening_balance)}</td>
                          <td className="td-mono" style={{ color: "var(--accent-green)" }}>+{fmtCurrency(b.total_inflows)}</td>
                          <td className="td-mono" style={{ color: "var(--accent-red)" }}>{fmtCurrency(b.total_outflows)}</td>
                          <td className="td-mono" style={{ color: b.net_cash_flow >= 0 ? "var(--accent-green)" : "var(--accent-red)", fontWeight: 700 }}>
                            {b.net_cash_flow >= 0 ? "+" : ""}{fmtCurrency(b.net_cash_flow)}
                          </td>
                          <td className="td-mono">{fmtCurrency(b.closing_balance)}</td>
                          <td style={{ fontSize: 11, color: "var(--text-muted)" }}>
                            {fmtCurrency(b.p10_closing)} – {fmtCurrency(b.p90_closing)}
                          </td>
                          <td>
                            <button
                              id={`btn-drivers-${b.forecast_id}`}
                              className="btn btn-ghost btn-xs"
                              onClick={() => openDrivers(b.forecast_id)}
                            >
                              Drivers
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Drivers panel */}
              {selected && (
                <div style={{ width: 320, flexShrink: 0 }}>
                  <div className="card" style={{ position: "sticky", top: 24 }}>
                    <div className="card-header">
                      <span className="card-title">Forecast Drivers</span>
                      <button className="btn btn-ghost btn-xs" onClick={() => { setSelected(null); setDrivers(null); }}>✕</button>
                    </div>
                    {!drivers ? (
                      <div className="loading-state" style={{ padding: 24 }}><div className="spinner" />Loading…</div>
                    ) : (
                      <div className="driver-list">
                        {(drivers.drivers as Array<Record<string, unknown>>)?.slice(0, 12).map((d, i) => (
                          <div key={i} className="driver-item">
                            <div className="driver-type-dot" style={{
                              background: d.driver_type === "AR_INFLOW" ? "#10b981" : d.driver_type === "AP_OUTFLOW" ? "#ef4444" : "#8b5cf6",
                            }} />
                            <div className="driver-name">{(d.counterparty_name as string) || (d.driver_type as string)}</div>
                            <div>
                              <div className={`driver-amount ${(d.amount as number) >= 0 ? "text-green" : "text-red"}`}>
                                {(d.amount as number) >= 0 ? "+" : ""}{fmtCurrency(d.amount as number)}
                              </div>
                              {d.probability != null && (
                                <div className="driver-prob">{((d.probability as number) * 100).toFixed(0)}% prob</div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ─── Escalations View ─────────────────────────────────────────────────────────
function EscalationsView() {
  const [data, setData] = useState<EscalationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [resolving, setResolving] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.listEscalations(statusFilter || undefined, severityFilter || undefined);
      setData(d);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter]);

  useEffect(() => { load(); }, [load]);

  const resolve = async (id: string, decision: string) => {
    setResolving(id);
    try {
      await api.resolveEscalation(id, decision, "admin-user");
      await load();
    } finally {
      setResolving(null);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Escalations</h1>
          <p className="page-subtitle">Governance exceptions requiring human review</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <select
            id="esc-status-filter"
            className="btn btn-ghost btn-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            {["OPEN", "IN_REVIEW", "RESOLVED", "OVERRIDDEN"].map(s => (
              <option key={s} value={s} style={{ background: "var(--bg-surface)" }}>{s}</option>
            ))}
          </select>
          <select
            id="esc-severity-filter"
            className="btn btn-ghost btn-sm"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="">All Severities</option>
            {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map(s => (
              <option key={s} value={s} style={{ background: "var(--bg-surface)" }}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="loading-state"><div className="spinner" />Loading…</div>
        ) : !data || data.items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"></div>
            <p>No escalations found. All good! </p>
          </div>
        ) : (
          <>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {data.items.map((e) => (
                <div key={e.escalation_id} className={`escalation-card severity-${e.severity}`}>
                  <div className="escalation-header">
                    <div>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                        <span className={`badge ${statusBadge(e.severity)}`}>{e.severity}</span>
                        <span className={`badge ${statusBadge(e.status)}`}>{e.status}</span>
                        <span className="badge badge-gray">{e.trigger_type.replace(/_/g, " ")}</span>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                        {fmtDateTime(e.created_at)}
                        {e.sla_deadline && (
                          <span> · SLA: {fmtDateTime(e.sla_deadline)}</span>
                        )}
                      </div>
                    </div>
                    <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                      {e.escalation_id.slice(0, 12)}…
                    </div>
                  </div>

                  {e.natural_language && (
                    <div className="escalation-nl">{e.natural_language}</div>
                  )}

                  {e.agent_proposal && (
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
                      <strong style={{ color: "var(--text-secondary)" }}>Agent Proposal:</strong>{" "}
                      {(e.agent_proposal as Record<string, string>).action}
                    </div>
                  )}

                  {e.status === "OPEN" && (
                    <div className="escalation-actions">
                      <button
                        id={`btn-resolve-${e.escalation_id}`}
                        className="btn btn-success btn-sm"
                        disabled={resolving === e.escalation_id}
                        onClick={() => resolve(e.escalation_id, "ACCEPT")}
                      >
                        [OK] Accept &amp; Resolve
                      </button>
                      <button
                        id={`btn-override-${e.escalation_id}`}
                        className="btn btn-ghost btn-sm"
                        disabled={resolving === e.escalation_id}
                        onClick={() => resolve(e.escalation_id, "OVERRIDE")}
                      >
                        Override
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16, fontSize: 12, color: "var(--text-muted)" }}>
              {fmt(data.total)} total escalations
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ─── Audit View ───────────────────────────────────────────────────────────────
function AuditView() {
  const [data, setData] = useState<AuditList | null>(null);
  const [loading, setLoading] = useState(true);
  const [eventFilter, setEventFilter] = useState("");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.getAuditLog(eventFilter || undefined, undefined, page);
      setData(d);
    } finally {
      setLoading(false);
    }
  }, [eventFilter, page]);

  useEffect(() => { load(); }, [load]);

  const EVENT_TYPES = [
    "", "RECONCILIATION_RUN", "RECONCILIATION_MATCH", "RECONCILIATION_REVIEW",
    "FORECAST_COMPLETE", "GOVERNANCE_POLICY_BREACH", "ESCALATION_RESOLVED",
  ];

  const dotColor: Record<string, string> = {
    RECONCILIATION_MATCH: "#10b981",
    RECONCILIATION_RUN: "#3b82f6",
    RECONCILIATION_REVIEW: "#8b5cf6",
    FORECAST_COMPLETE: "#06b6d4",
    GOVERNANCE_POLICY_BREACH: "#ef4444",
    ESCALATION_RESOLVED: "#f59e0b",
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Trail</h1>
          <p className="page-subtitle">Immutable HMAC-signed agent action log</p>
        </div>
        <select
          id="audit-event-filter"
          className="btn btn-ghost btn-sm"
          value={eventFilter}
          onChange={(e) => { setEventFilter(e.target.value); setPage(1); }}
        >
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t} style={{ background: "var(--bg-surface)" }}>
              {t || "All Events"}
            </option>
          ))}
        </select>
      </div>

      <div className="page-body">
        <div className="card">
          {loading ? (
            <div className="loading-state"><div className="spinner" />Loading…</div>
          ) : !data || data.entries.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon"></div>
              <p>No audit entries found.</p>
            </div>
          ) : (
            <>
              <div className="audit-timeline">
                {data.entries.map((e) => (
                  <div key={e.log_id} className="audit-entry">
                    <div
                      className="audit-dot"
                      style={{ background: dotColor[e.event_type] || "var(--text-muted)" }}
                    />
                    <div className="audit-content">
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span className="audit-event-type">{e.event_type}</span>
                        {e.policies_breached && e.policies_breached.length > 0 && (
                          <span className="badge badge-red">Policy Breach</span>
                        )}
                        <span className="audit-timestamp">{fmtDateTime(e.timestamp)}</span>
                      </div>
                      <div className="audit-detail">
                        {e.agent_id && <><strong>Agent:</strong> {e.agent_id} v{e.agent_version} &nbsp;</>}
                        {e.user_id && <><strong>User:</strong> {e.user_id} &nbsp;</>}
                        {e.entity_id && <><strong>Entity:</strong> {e.entity_id}</>}
                      </div>
                      {e.output_summary && Object.keys(e.output_summary).length > 0 && (
                        <div className="audit-detail" style={{ marginTop: 4 }}>
                          {Object.entries(e.output_summary).slice(0, 4).map(([k, v]) => (
                            <span key={k} style={{ marginRight: 12 }}>
                              <span style={{ color: "var(--text-muted)" }}>{k}:</span>{" "}
                              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-accent)" }}>
                                {String(v)}
                              </span>
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="audit-hmac">[SECURE] {e.hmac_sig}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16, fontSize: 12, color: "var(--text-muted)" }}>
                <span>{fmt(data.total)} total entries</span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-ghost btn-xs" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
                  <span style={{ padding: "3px 8px" }}>Page {page}</span>
                  <button className="btn btn-ghost btn-xs" disabled={data.entries.length < 50} onClick={() => setPage(p => p + 1)}>Next →</button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ─── Scenarios View ───────────────────────────────────────────────────────────
function ScenariosView() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [delta, setDelta] = useState<Record<string, unknown> | null>(null);
  const [deltaLoading, setDeltaLoading] = useState(false);

  useEffect(() => {
    api.listScenarios().then((s) => { setScenarios(s); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const runDelta = async (scenarioId: string) => {
    setSelected(scenarioId);
    setDelta(null);
    setDeltaLoading(true);
    try {
      const d = await api.getScenarioDelta(scenarioId);
      setDelta(d as unknown as Record<string, unknown>);
    } finally {
      setDeltaLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Scenarios</h1>
          <p className="page-subtitle">What-if analysis — stress test cash flow against policy rules</p>
        </div>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="loading-state"><div className="spinner" />Loading…</div>
        ) : scenarios.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"></div>
            <p>No scenarios found. Seed the database to add system scenarios.</p>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 20 }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {scenarios.map((s) => (
                  <div key={s.scenario_id} className="card" style={{ cursor: "pointer" }} onClick={() => runDelta(s.scenario_id)}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                          <span style={{ fontSize: 14, fontWeight: 700 }}>{s.name}</span>
                          {s.is_system_scenario && <span className="badge badge-blue">System</span>}
                        </div>
                        {s.description && (
                          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 10 }}>
                            {s.description}
                          </div>
                        )}
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {Object.entries(s.parameters).map(([k, v]) => (
                            <span key={k} className="badge badge-gray">
                              {k}: {String(v)}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button
                        id={`btn-delta-${s.scenario_id}`}
                        className="btn btn-primary btn-sm"
                        onClick={(e) => { e.stopPropagation(); runDelta(s.scenario_id); }}
                      >
                        Run Delta 
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {selected && (
              <div style={{ width: 400, flexShrink: 0 }}>
                <div className="card" style={{ position: "sticky", top: 24 }}>
                  <div className="card-header">
                    <span className="card-title">Scenario Delta</span>
                    <button className="btn btn-ghost btn-xs" onClick={() => { setSelected(null); setDelta(null); }}>✕</button>
                  </div>
                  {deltaLoading ? (
                    <div className="loading-state" style={{ padding: 24 }}><div className="spinner" />Running scenario…</div>
                  ) : delta ? (
                    <div>
                      {Boolean(delta.natural_language) && (
                        <div className="escalation-nl" style={{ fontSize: 12, marginBottom: 16 }}>
                          {delta.natural_language as string}
                        </div>
                      )}
                      <div style={{ marginBottom: 12 }}>
                        <span className="card-title">Total Delta: </span>
                        <span style={{
                          fontFamily: "var(--font-mono)", fontSize: 16, fontWeight: 700,
                          color: (delta.total_delta as number) >= 0 ? "var(--accent-green)" : "var(--accent-red)",
                        }}>
                          {(delta.total_delta as number) >= 0 ? "+" : ""}{fmtCurrency(delta.total_delta as number)}
                        </span>
                      </div>
                      {(delta.risk_flags as string[])?.length > 0 && (
                        <div className="alert alert-warn mb-12">
                          <span>[!]</span>
                          <div>
                            {(delta.risk_flags as string[]).map((f, i) => (
                              <div key={i} style={{ fontSize: 11 }}>{f}</div>
                            ))}
                          </div>
                        </div>
                      )}
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Week</th>
                              <th>Base Net</th>
                              <th>Scen Net</th>
                              <th>Delta %</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(delta.buckets as Array<Record<string, unknown>>)?.map((b, i) => (
                              <tr key={i}>
                                <td style={{ fontSize: 11 }}>{fmtDate(b.period_start as string)}</td>
                                <td className="td-mono">{fmtCurrency(b.base_net_flow as number)}</td>
                                <td className="td-mono">{fmtCurrency(b.scenario_net_flow as number)}</td>
                                <td className="td-mono" style={{ color: (b.delta as number) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}>
                                  {(b.delta_pct as number) >= 0 ? "+" : ""}{b.delta_pct as number}%
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ─── App Shell ────────────────────────────────────────────────────────────────
export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [openEscalations, setOpenEscalations] = useState(0);

  useEffect(() => {
    api.listEscalations("OPEN").then((d) => setOpenEscalations(d.total)).catch(() => {});
  }, []);

  const VIEWS: Record<View, React.ReactNode> = {
    dashboard: <DashboardView />,
    reconciliation: <ReconciliationView />,
    forecasts: <ForecastView />,
    scenarios: <ScenariosView />,
    escalations: <EscalationsView />,
    audit: <AuditView />,
  };

  return (
    <div className="app-shell">
      <Sidebar active={view} onNav={setView} openEscalations={openEscalations} />
      <main className="main-content">
        {VIEWS[view]}
      </main>
    </div>
  );
}

