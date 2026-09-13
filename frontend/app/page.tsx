"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, DashboardStats, ReconciliationList, ForecastList, EscalationList, AuditList, Scenario } from "../lib/api";

// ─── View type ────────────────────────────────────────────────────────────────
type View = "dashboard" | "reconciliation" | "forecasts" | "scenarios" | "approvals" | "audit";

// ─── Utility helpers ──────────────────────────────────────────────────────────
function fmtIN(n: number, decimals = 0) {
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function fmtCurrency(n: number) {
  const absN = Math.abs(n);
  if (absN >= 1_000_0000) {
    return `₹${fmtIN(n / 1_000_0000, 1)} Cr`;
  }
  if (absN >= 1_00000) {
    return `₹${fmtIN(n / 1_00000, 1)} Lakh`;
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

function fmtDateTime(s: string) {
  return new Date(s).toLocaleString("en-IN", {
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

// ─── Sidebar ──────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { view: "dashboard" as View, label: "Overview" },
  { view: "reconciliation" as View, label: "Reconciliation" },
  { view: "forecasts" as View, label: "Forecast" },
  { view: "scenarios" as View, label: "Scenarios" },
  { view: "approvals" as View, label: "Approvals" },
  { view: "audit" as View, label: "Audit Log" },
];

function Sidebar({
  active,
  onNav,
  openEscalations,
  mobileOpen,
  onMobileToggle,
}: {
  active: View;
  onNav: (v: View) => void;
  openEscalations: number;
  mobileOpen: boolean;
  onMobileToggle: () => void;
}) {
  return (
    <>
      <aside className={`sidebar${mobileOpen ? " mobile-open" : ""}`}>
      <div className="sidebar-logo">
        <div>
          <div className="sidebar-logo-text">LedgerFlow</div>
          <div className="sidebar-logo-sub">Finance Operations</div>
        </div>
        <button
          className="mobile-menu-button"
          aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={mobileOpen}
          onClick={onMobileToggle}
        >
          <span /><span /><span />
        </button>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ view, label }) => (
          <button
            key={view}
            id={`nav-${view}`}
            className={`nav-item${active === view ? " active" : ""}`}
            onClick={() => { onNav(view); if (mobileOpen) onMobileToggle(); }}
          >
            {label}
            {view === "approvals" && openEscalations > 0 && (
              <span className="nav-badge">{openEscalations}</span>
            )}
          </button>
        ))}
      </nav>
      </aside>
      <button
        className="mobile-menu-scrim"
        aria-label="Close navigation menu"
        aria-hidden={!mobileOpen}
        onClick={onMobileToggle}
      />
    </>
  );
}

// ─── Dashboard View ───────────────────────────────────────────────────────────
function DashboardView({ onNav }: { onNav: (v: View) => void }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runMsg, setRunMsg] = useState("");
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState("");
  const importInputRef = useRef<HTMLInputElement>(null);

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

  const runReconcile = async () => {
    setRunning(true);
    setRunMsg("");
    try {
      await api.runReconciliation();
      await load();
      setRunMsg("Reconciliation workflow completed successfully.");
    } catch (e: unknown) {
      setRunMsg(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setRunning(false);
    }
  };
  
  const runForecast = async () => {
    setRunning(true);
    setRunMsg("");
    try {
      await api.runForecast();
      await load();
      setRunMsg("Cash flow forecast generated successfully.");
    } catch (e: unknown) {
      setRunMsg(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setRunning(false);
    }
  };

  const importTransactions = async (file: File) => {
    setImporting(true);
    setImportMsg("");
    try {
      const result = await api.importTransactions(file);
      await load();
      setImportMsg(`${result.imported} imported · ${result.skipped} duplicates skipped · ${result.invalid.length} invalid rows`);
    } catch (e: unknown) {
      setImportMsg(`Import error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setImporting(false);
      if (importInputRef.current) importInputRef.current.value = "";
    }
  };

  const downloadTemplate = () => {
    const csv = [
      "source_tx_id,date,amount,currency,direction,counterparty_name,reference,description",
      "YOUR-TX-001,2026-09-13,12500.00,USD,CREDIT,Example Customer,INV-9001,Customer payment",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "ledgerflow-bank-transactions-template.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return (
    <div className="loading-state">
      <div className="spinner" />
      Loading dashboard...
    </div>
  );

  if (!stats) return (
    <div className="empty-state">
      <p>Could not load financial data. Please check connectivity.</p>
    </div>
  );

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            LedgerFlow · India Operations · Live operating view
          </p>
        </div>
      </div>

      <div className="page-body">
        <section className="demo-intro">
          <div>
            <div className="demo-kicker">Recruiter demo · Real data workflow</div>
            <h2>Bring a bank export. See the agents work.</h2>
            <p>Import a CSV, review what was accepted, then run reconciliation and forecasting on the resulting transactions.</p>
          </div>
          <div className="demo-intro-actions">
            <button className="btn btn-ghost btn-sm" onClick={downloadTemplate}>Download CSV template</button>
            <input
              ref={importInputRef}
              className="sr-only"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => { const file = event.target.files?.[0]; if (file) importTransactions(file); }}
            />
            <button className="btn btn-primary btn-sm" onClick={() => importInputRef.current?.click()} disabled={importing}>
              {importing ? "Importing..." : "Import bank CSV"}
            </button>
          </div>
        </section>
        {(importMsg || runMsg) && (
          <div className={`alert mb-16 ${[importMsg, runMsg].some((message) => message.startsWith("Import error") || message.startsWith("Error")) ? "alert-error" : "alert-info"}`}>
            {importMsg || runMsg}
          </div>
        )}
        {/* Action Bar */}
        <div className="flex gap-12 mb-24 items-center">
          <button className="btn btn-primary" onClick={runReconcile} disabled={running}>
            {running ? "Processing..." : "Reconcile Transactions"}
          </button>
          <button className="btn btn-ghost" onClick={runForecast} disabled={running}>
            {running ? "Processing..." : "Create Forecast"}
          </button>
        </div>

        {/* KPI row */}
        <div className="stat-grid mb-24">
          <div className="stat-card">
            <div className="stat-label">Available Cash</div>
            <div className="stat-value">{fmtCurrency(stats.current_balance)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Expected Cash Position</div>
            <div className="stat-value brand">{fmtCurrency(stats.current_balance + stats.forecast_next_4_weeks_net)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Receivables Outstanding</div>
            <div className="stat-value">{fmtCurrency(stats.open_invoices_total)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Payables Outstanding</div>
            <div className="stat-value">{fmtCurrency(stats.open_bills_total)}</div>
          </div>
        </div>

        <div className="grid-2 mb-24">
          {/* Cash Flow Section */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Cash Flow Forecast (Next 4 Weeks)</span>
            </div>
            
            {/* Simple Mocked Chart for Dashboard Overview */}
            <div className="chart-grid">
               {[1,2,3,4].map((i) => (
                 <div key={i} className="chart-col">
                    <div className="chart-bar-wrap">
                      <div className="flex items-end gap-4 w-full justify-center h-32" style={{height: '120px'}}>
                        <div className="chart-bar" style={{ height: `${40 + i*15}%`, background: '#059669', width: '30%' }} />
                        <div className="chart-bar" style={{ height: `${30 + i*10}%`, background: '#DC2626', width: '30%' }} />
                        <div className="chart-bar" style={{ height: `${10 + i*5}%`, background: '#1E3A8A', width: '30%' }} />
                      </div>
                      <div className="chart-label">W{i}</div>
                    </div>
                 </div>
               ))}
               <div className="flex-col w-full col-span-9 justify-center items-center h-full text-muted text-sm border-l border-dashed border-gray-600 pl-4">
                  <div className="flex gap-16 mb-4">
                    <div className="flex items-center gap-4"><span style={{width: 12, height: 12, background: '#059669', display: 'inline-block'}}/> Inflows</div>
                    <div className="flex items-center gap-4"><span style={{width: 12, height: 12, background: '#DC2626', display: 'inline-block'}}/> Outflows</div>
                    <div className="flex items-center gap-4"><span style={{width: 12, height: 12, background: '#1E3A8A', display: 'inline-block'}}/> Net</div>
                  </div>
               </div>
            </div>
          </div>

          <div className="flex-col gap-24">
            {/* Reconciliation Summary */}
            <div className="card">
              <div className="card-header">
                <span className="card-title">Bank Reconciliation</span>
                <button className="btn btn-ghost btn-xs" onClick={() => onNav("approvals")}>Review exceptions →</button>
              </div>
              
              <div className="flex-col gap-12">
                <div className="flex justify-between text-sm">
                  <span className="text-secondary">Reconciled</span>
                  <span className="font-bold">{stats.matched_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-secondary">Needs Review</span>
                  <span className="font-bold text-amber">{stats.pending_review_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-secondary">Unmatched</span>
                  <span className="font-bold text-red">{stats.unmatched_count}</span>
                </div>
                
                <div className="progress-bar-wrap mt-4">
                   <div className="progress-segment" style={{ width: `${(stats.matched_count / (stats.total_bank_transactions || 1))*100}%`, background: '#059669' }} />
                   <div className="progress-segment" style={{ width: `${(stats.pending_review_count / (stats.total_bank_transactions || 1))*100}%`, background: '#D97706' }} />
                   <div className="progress-segment" style={{ width: `${(stats.unmatched_count / (stats.total_bank_transactions || 1))*100}%`, background: '#DC2626' }} />
                </div>
              </div>
            </div>

            {/* Exceptions */}
            <div className="card">
              <div className="card-header">
                <span className="card-title">Exceptions requiring attention</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Type</th>
                      <th>Amount</th>
                      <th>Age</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="font-bold">INV-2048</td>
                      <td>Receivable</td>
                      <td className="td-mono text-primary">₹4,80,000</td>
                      <td>8 days</td>
                      <td><span className="badge badge-amber">Review</span></td>
                    </tr>
                    <tr>
                      <td className="font-bold">PAY-1032</td>
                      <td>Payment</td>
                      <td className="td-mono text-primary">₹2,10,000</td>
                      <td>3 days</td>
                      <td><span className="badge badge-blue">Approval</span></td>
                    </tr>
                    <tr>
                      <td className="font-bold">BANK-8821</td>
                      <td>Reconciliation</td>
                      <td className="td-mono text-primary">₹85,000</td>
                      <td>2 days</td>
                      <td><span className="badge badge-red">Unmatched</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
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

  const runReconcile = async () => {
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
          <p className="page-subtitle">Transaction matching and exceptions review</p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: 'center' }}>
          <select
            id="recon-status-filter"
            className="btn btn-ghost"
            style={{padding: '8px 16px', background: 'var(--bg-surface)'}}
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(1); }}
          >
            <option value="">All Statuses</option>
            {STATUSES.filter(Boolean).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <button id="btn-run-reconciliation" className="btn btn-primary" onClick={runReconcile} disabled={running}>
            {running ? "Processing..." : "Reconcile Transactions"}
          </button>
        </div>
      </div>

      <div className="page-body">
        <div style={{ display: "flex", gap: 24 }}>
          <div style={{ flex: 1 }}>
            {loading ? (
              <div className="loading-state"><div className="spinner" />Loading records...</div>
            ) : !data || data.items.length === 0 ? (
              <div className="empty-state">
                <p>No reconciliation matches found. Run reconciliation to process bank transactions.</p>
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
                        <th>Variance</th>
                        <th>Matched At</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((m) => (
                        <tr key={m.match_id} style={{ cursor: "pointer" }} onClick={() => openExplain(m.match_id)}>
                          <td className="font-bold">{m.bank_tx_id.slice(0, 8)}…</td>
                          <td><span className={`badge ${statusBadge(m.match_status)}`}>{m.match_status}</span></td>
                          <td><span className="badge badge-gray">{m.match_method}</span></td>
                          <td className="td-mono">
                            {m.amount_variance != null
                              ? <span style={{ color: Math.abs(m.amount_variance) > 0.01 ? "var(--accent-amber)" : "var(--text-muted)" }}>
                                  {m.amount_variance >= 0 ? "+" : ""}{fmtIN(m.amount_variance, 2)}
                                </span>
                              : <span style={{ color: "var(--text-muted)" }}>—</span>}
                          </td>
                          <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{fmtDateTime(m.matched_at)}</td>
                          <td style={{textAlign: 'right'}}>
                            <button
                              id={`btn-explain-${m.match_id}`}
                              className="btn btn-ghost btn-xs"
                              onClick={(e) => { e.stopPropagation(); openExplain(m.match_id); }}
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "space-between", fontSize: 13, color: "var(--text-secondary)" }}>
                  <span>{fmtIN(data.total)} total matches</span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn-ghost btn-xs" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Previous</button>
                    <span style={{ padding: "4px 8px" }}>Page {page}</span>
                    <button className="btn btn-ghost btn-xs" disabled={data.items.length < 50} onClick={() => setPage(p => p + 1)}>Next →</button>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Details panel */}
          {selected && (
            <div style={{ width: 400, flexShrink: 0 }}>
              <div className="card" style={{ position: "sticky", top: 24 }}>
                <div className="card-header border-b border-gray-600 pb-4 mb-4">
                  <span className="card-title">Transaction Details</span>
                  <button className="btn btn-ghost btn-xs" onClick={() => { setSelected(null); setExplain(null); }}>✕</button>
                </div>
                {explainLoading ? (
                  <div className="loading-state" style={{ padding: 24 }}><div className="spinner" />Loading details...</div>
                ) : explain ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    {Boolean(explain.natural_language) && (
                      <div className="alert alert-info">
                        {explain.natural_language as string}
                      </div>
                    )}
                    {Boolean(explain.bank_tx) && (
                      <div>
                        <div className="text-sm font-bold mb-8">Bank Transaction</div>
                        <pre style={{ fontSize: 11, color: "var(--text-secondary)", background: "var(--bg-base)", padding: 12, borderRadius: 6, overflow: "auto", maxHeight: 160, border: '1px solid var(--border)' }}>
                          {JSON.stringify(explain.bank_tx, null, 2)}
                        </pre>
                      </div>
                    )}
                    {Boolean(explain.erp_tx) && (
                      <div>
                        <div className="text-sm font-bold mb-8">ERP Transaction</div>
                        <pre style={{ fontSize: 11, color: "var(--text-secondary)", background: "var(--bg-base)", padding: 12, borderRadius: 6, overflow: "auto", maxHeight: 160, border: '1px solid var(--border)' }}>
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

  if (loading) return <div className="loading-state"><div className="spinner" />Loading projections...</div>;

  const buckets = data?.buckets || [];

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Cash Flow Forecast</h1>
          <p className="page-subtitle">
            13-week rolling projections · INR
            {data?.is_stale && <span className="badge badge-amber" style={{ marginLeft: 8 }}>Update needed</span>}
          </p>
        </div>
        <button id="btn-run-forecast" className="btn btn-primary" onClick={runForecast} disabled={running}>
          {running ? "Processing..." : "Create Forecast"}
        </button>
      </div>

      <div className="page-body">
        {buckets.length === 0 ? (
          <div className="empty-state">
            <p>No forecast data available. Generate a new forecast to view projections.</p>
          </div>
        ) : (
          <>
            <div style={{ display: "flex", gap: 24 }}>
              <div style={{ flex: 1 }}>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Period</th>
                        <th>Opening Balance</th>
                        <th>Inflows</th>
                        <th>Outflows</th>
                        <th>Net Cash Flow</th>
                        <th>Closing Balance</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {buckets.map((b) => (
                        <tr key={b.forecast_id}>
                          <td style={{ fontWeight: 600 }}>
                            {fmtDate(b.period_start)} – {fmtDate(b.period_end)}
                          </td>
                          <td className="td-mono text-primary">{fmtCurrency(b.opening_balance)}</td>
                          <td className="td-mono text-green">+{fmtCurrency(b.total_inflows)}</td>
                          <td className="td-mono text-red">{fmtCurrency(b.total_outflows)}</td>
                          <td className={`td-mono ${b.net_cash_flow >= 0 ? "text-green" : "text-red"} font-bold`}>
                            {b.net_cash_flow >= 0 ? "+" : ""}{fmtCurrency(b.net_cash_flow)}
                          </td>
                          <td className="td-mono font-bold text-primary">{fmtCurrency(b.closing_balance)}</td>
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

              {selected && (
                <div style={{ width: 360, flexShrink: 0 }}>
                  <div className="card" style={{ position: "sticky", top: 24 }}>
                    <div className="card-header border-b border-gray-600 pb-4 mb-4">
                      <span className="card-title">Forecast Drivers</span>
                      <button className="btn btn-ghost btn-xs" onClick={() => { setSelected(null); setDrivers(null); }}>✕</button>
                    </div>
                    {!drivers ? (
                      <div className="loading-state" style={{ padding: 24 }}><div className="spinner" />Loading drivers...</div>
                    ) : (
                      <div className="driver-list">
                        {(drivers.drivers as Array<Record<string, unknown>>)?.slice(0, 12).map((d, i) => (
                          <div key={i} className="driver-item">
                            <div className="driver-type-dot" style={{
                              background: d.driver_type === "AR_INFLOW" ? "#059669" : d.driver_type === "AP_OUTFLOW" ? "#DC2626" : "#3B82F6",
                            }} />
                            <div className="driver-name">{(d.counterparty_name as string) || (d.driver_type as string)}</div>
                            <div>
                              <div className={`driver-amount ${(d.amount as number) >= 0 ? "text-green" : "text-red"}`}>
                                {(d.amount as number) >= 0 ? "+" : ""}{fmtCurrency(d.amount as number)}
                              </div>
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
          <div className="loading-state"><div className="spinner" />Loading scenarios...</div>
        ) : scenarios.length === 0 ? (
          <div className="empty-state">
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
                  <div className="card-header border-b border-gray-600 pb-4 mb-4">
                    <span className="card-title">Scenario Delta</span>
                    <button className="btn btn-ghost btn-xs" onClick={() => { setSelected(null); setDelta(null); }}>✕</button>
                  </div>
                  {deltaLoading ? (
                    <div className="loading-state" style={{ padding: 24 }}><div className="spinner" />Running scenario...</div>
                  ) : delta ? (
                    <div>
                      {Boolean(delta.natural_language) && (
                        <div className="alert alert-info mb-16">
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

// ─── Approvals / Exceptions View ───────────────────────────────────────────────
function ApprovalsView() {
  const [data, setData] = useState<EscalationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [resolving, setResolving] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.listEscalations(statusFilter || undefined, undefined);
      setData(d);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const resolve = async (id: string, decision: string) => {
    setResolving(id);
    try {
      await api.resolveEscalation(id, decision, "finance-manager");
      await load();
    } finally {
      setResolving(null);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Approvals</h1>
          <p className="page-subtitle">Exceptions and workflows requiring review</p>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <select
            id="esc-status-filter"
            className="btn btn-ghost"
            style={{padding: '8px 16px', background: 'var(--bg-surface)'}}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            {["OPEN", "IN_REVIEW", "RESOLVED", "OVERRIDDEN"].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="page-body">
        {loading ? (
           <div className="loading-state"><div className="spinner" />Loading approvals...</div>
        ) : !data || data.items.length === 0 ? (
           <div className="empty-state">
             <p>No pending approvals or exceptions.</p>
           </div>
        ) : (
          <div className="flex-col gap-16">
            {data.items.map((e) => (
              <div key={e.escalation_id} className="card approval-card">
                <div className="approval-header">
                  <div>
                    <div className="approval-eyebrow">Human review required</div>
                    <h2 className="approval-title">
                      {e.entity_id} <span>·</span> {e.trigger_type.replace(/_/g, " ")}
                    </h2>
                  </div>
                  <span className={`badge ${statusBadge(e.status)}`}>{e.status}</span>
                </div>

                <div className="approval-copy">
                  {e.natural_language || "This transaction requires a finance manager review."}
                </div>

                <div className="approval-meta">
                  <div><span>Trigger</span><strong>{e.trigger_type.replace(/_/g, " ")}</strong></div>
                  <div><span>Severity</span><strong>{e.severity}</strong></div>
                  <div><span>Generated</span><strong>{fmtDateTime(e.created_at)}</strong></div>
                </div>

                {e.status === "OPEN" && (
                  <div className="approval-actions">
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => resolve(e.escalation_id, "APPROVE")}
                      disabled={resolving === e.escalation_id}
                    >
                      {resolving === e.escalation_id ? "Saving..." : "Approve"}
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => resolve(e.escalation_id, "REJECT")}
                      disabled={resolving === e.escalation_id}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

// ─── Audit Log View ───────────────────────────────────────────────────────────
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
    RECONCILIATION_MATCH: "#10B981",
    RECONCILIATION_RUN: "#3B82F6",
    RECONCILIATION_REVIEW: "#8B5CF6",
    FORECAST_COMPLETE: "#06B6D4",
    GOVERNANCE_POLICY_BREACH: "#EF4444",
    ESCALATION_RESOLVED: "#F59E0B",
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Trail</h1>
          <p className="page-subtitle">Immutable system log of financial events</p>
        </div>
        <select
          id="audit-event-filter"
          className="btn btn-ghost"
          style={{padding: '8px 16px', background: 'var(--bg-surface)'}}
          value={eventFilter}
          onChange={(e) => { setEventFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Events</option>
          {EVENT_TYPES.filter(Boolean).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="page-body">
        <div className="card">
          {loading ? (
            <div className="loading-state"><div className="spinner" />Loading records...</div>
          ) : !data || data.entries.length === 0 ? (
            <div className="empty-state">
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
                      <div className="flex justify-between w-full mb-4">
                        <div className="flex gap-8">
                          <span className="font-bold text-sm">{e.event_type}</span>
                          {e.policies_breached && e.policies_breached.length > 0 && (
                            <span className="badge badge-red">Policy Breach</span>
                          )}
                        </div>
                        <span className="audit-timestamp">{fmtDateTime(e.timestamp)}</span>
                      </div>
                      
                      <div className="text-xs text-muted mb-8 font-mono">
                        {e.user_id && <span>User: {e.user_id} · </span>}
                        {e.entity_id && <span>Entity: {e.entity_id} · </span>}
                        <span className="text-primary">[SECURE] {e.hmac_sig.substring(0, 32)}...</span>
                      </div>
                      
                      {e.output_summary && Object.keys(e.output_summary).length > 0 && (
                        <div className="bg-base p-8 rounded-md border border-gray-700 text-xs text-secondary mt-4">
                          {Object.entries(e.output_summary).slice(0, 4).map(([k, v]) => (
                            <div key={k} className="flex gap-4">
                              <span className="text-muted w-32">{k}:</span>
                              <span className="font-mono text-accent">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex justify-between items-center mt-16 text-xs text-muted">
                <span>{fmtIN(data.total)} total entries</span>
                <div className="flex gap-8">
                  <button className="btn btn-ghost btn-xs" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
                  <span className="px-8 py-4">Page {page}</span>
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

// ─── Main App Component ───────────────────────────────────────────────────────
export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    document.body.style.overflow = mobileMenuOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileMenuOpen]);

  useEffect(() => {
    api.getDashboardStats().then(s => setStats(s)).catch(() => {});
  }, []);

  return (
    <div className="app-shell">
      <Sidebar 
        active={view} 
        onNav={setView} 
        openEscalations={stats?.open_escalations || 0} 
        mobileOpen={mobileMenuOpen}
        onMobileToggle={() => setMobileMenuOpen((open) => !open)}
      />
      <main className="main-content">
        {view === "dashboard" && <DashboardView onNav={setView} />}
        {view === "reconciliation" && <ReconciliationView />}
        {view === "forecasts" && <ForecastView />}
        {view === "scenarios" && <ScenariosView />}
        {view === "approvals" && <ApprovalsView />}
        {view === "audit" && <AuditView />}
      </main>
    </div>
  );
}
