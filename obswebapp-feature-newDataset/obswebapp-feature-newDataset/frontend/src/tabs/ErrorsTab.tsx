import { useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import PlotlyChart from "../components/PlotlyChart";
import WaterfallModal from "../components/WaterfallModal";
import Spinner from "../components/Spinner";
import { SkeletonCharts, SkeletonTable } from "../components/Skeleton";
import { api } from "../api";
import type { ErrorsResponse, FilterOptions, SharedFilters } from "../types";

const TABLE_COLS = [
  "error_id", "component", "error_type", "error_message", "severity",
  "session_id", "trace_id", "timestamp",
];

function ErrorDetailModal({ row, onClose, onViewTrace }: { row: Record<string, any>; onClose: () => void; onViewTrace: (id: string) => void }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000, padding: "24px 16px",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 12,
        width: "min(760px, 95vw)", padding: 24,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", color: "#6b7280" }}>
            Error Detail
          </span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0 }}>✕</button>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 16 }}>
          {["component", "error_type", "severity", "session_id", "timestamp"].map((k) =>
            row[k] != null && (
              <div key={k}>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 3 }}>{k}</div>
                <div style={{ fontSize: 13, color: "#111827", fontFamily: k.endsWith("_id") ? "monospace" : undefined }}>
                  {String(row[k])}
                </div>
              </div>
            )
          )}
          {row.trace_id && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 3 }}>trace_id</div>
              <button
                onClick={() => { onClose(); onViewTrace(row.trace_id); }}
                style={{ background: "none", border: "1px solid #e5e7eb", borderRadius: 4, color: "#3b82f6", cursor: "pointer", fontSize: 12, fontFamily: "monospace", padding: "2px 8px" }}
              >
                {String(row.trace_id).slice(0, 16)}… ↗
              </button>
            </div>
          )}
        </div>

        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 8 }}>
          Error Message
        </div>
        <div style={{
          background: "#fee2e2", border: "1px solid #fecaca", borderRadius: 6,
          padding: "12px 14px", fontFamily: "ui-monospace, monospace", fontSize: 13,
          color: "#991b1b", whiteSpace: "pre-wrap", wordBreak: "break-word",
          maxHeight: 300, overflowY: "auto",
        }}>
          {String(row.error_message ?? "")}
        </div>
      </div>
    </div>
  );
}

export default function ErrorsTab({ filters, options }: { filters: SharedFilters; options: FilterOptions }) {
  const [component, setComponent] = useState("All");
  const [errorType, setErrorType] = useState("All");
  const [severity, setSeverity]   = useState("All");

  const [data, setData]       = useState<ErrorsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]         = useState("");
  const [selectedRow, setSelectedRow]     = useState<Record<string, any> | null>(null);
  const [waterfallTraceId, setWaterfallTraceId] = useState<string | null>(null);

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.errors({ ...filters, component, error_type: errorType, severity }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters, component, errorType, severity]);

  const components = ["All", ...(options.components ?? [])];

  return (
    <div>
      <div className="tab-filters">
        <div style={{ flex: 1, minWidth: 180 }}>
          <label className="field-label">Component</label>
          <select className="field-select" value={component} onChange={(e) => setComponent(e.target.value)}>
            {components.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <label className="field-label">Error Type</label>
          <select className="field-select" value={errorType} onChange={(e) => setErrorType(e.target.value)}>
            {['All', ...(options.error_types ?? [])].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Severity</label>
          <select className="field-select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {["All", "CRITICAL", "ERROR", "WARNING"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {loading && <Spinner size={16} />}
      </div>

      {err && <div className="status-error" style={{ marginBottom: 12 }}>{err}</div>}

      {data === null && loading
        ? <SkeletonCharts />
        : data && (
            <div className="responsive-grid" style={{ marginBottom: 16 }}>
              <PlotlyChart fig={data.charts.errors_over_time} />
              <PlotlyChart fig={data.charts.severity_pie} />
              <PlotlyChart fig={data.charts.by_component} />
              <PlotlyChart fig={data.charts.by_type} />
            </div>
          )
      }

      <div className="section-h">Error Records — click a row to view details</div>
      {data === null && loading
        ? <SkeletonTable />
        : <DataTable
            columns={TABLE_COLS}
            rows={data?.rows ?? []}
            onRowClick={(row) => setSelectedRow(row)}
            emptyText="No errors found"
            pageSize={25}
            truncateColumns={["error_id", "session_id", "trace_id", "error_message"]}
          />
      }

      {selectedRow && <ErrorDetailModal row={selectedRow} onClose={() => setSelectedRow(null)} onViewTrace={(id) => setWaterfallTraceId(id)} />}
      {waterfallTraceId && <WaterfallModal traceId={waterfallTraceId} onClose={() => setWaterfallTraceId(null)} />}
    </div>
  );
}
