import { useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import PlotlyChart from "../components/PlotlyChart";
import Spinner from "../components/Spinner";
import { SkeletonTable } from "../components/Skeleton";
import { api } from "../api";
import type { FilterOptions, LogsResponse, SharedFilters } from "../types";

const COLS = ["timestamp", "severity", "message", "service_name", "environment", "model"];

const LOG_DETAIL_COLS = ["timestamp", "severity", "service_name", "environment", "model"];

function LogModal({ log, onClose }: { log: Record<string, any>; onClose: () => void }) {
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
        width: "min(760px, 95vw)", padding: 24, position: "relative",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", color: "#6b7280" }}>
            Log Entry
          </span>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0 }}
          >
            ✕
          </button>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 16 }}>
          {LOG_DETAIL_COLS.map((c) => log[c] != null && (
            <div key={c}>
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 3 }}>{c}</div>
              <div style={{ fontSize: 13, color: "#111827" }}>{String(log[c])}</div>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 8 }}>
          Message
        </div>
        <div style={{
          background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 6,
          padding: "12px 14px", fontFamily: "ui-monospace, monospace", fontSize: 13,
          color: "#374151", whiteSpace: "pre-wrap", wordBreak: "break-word",
          maxHeight: 400, overflowY: "auto",
        }}>
          {String(log.message ?? "")}
        </div>
      </div>
    </div>
  );
}

export default function LogsTab({ filters, options }: { filters: SharedFilters; options: FilterOptions }) {
  const [severity, setSeverity]       = useState("All");
  const [environment, setEnvironment] = useState("All");
  const [limit, setLimit]             = useState(500);
  const [appliedLimit, setAppliedLimit] = useState(500);
  const [data, setData]               = useState<LogsResponse | null>(null);
  const [loading, setLoading]         = useState(false);
  const [err, setErr]                 = useState("");
  const [selectedLog, setSelectedLog] = useState<Record<string, any> | null>(null);

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.logs({ ...filters, severity, environment, limit: appliedLimit }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters, severity, environment, appliedLimit]);

  const severities   = ["All", ...options.severities];
  const environments = ["All", ...options.environments];

  return (
    <div>
      <div className="tab-filters">
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Severity</label>
          <select className="field-select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {severities.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Environment</label>
          <select className="field-select" value={environment} onChange={(e) => setEnvironment(e.target.value)}>
            {environments.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ flex: 2, minWidth: 220 }}>
          <label className="field-label">Row Limit: {limit}</label>
          <input
            type="range" min={100} max={2000} step={100}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            onPointerUp={(e) => setAppliedLimit(Number((e.target as HTMLInputElement).value))}
          />
        </div>
        {loading && <Spinner size={16} />}
      </div>

      {err && <div className="status-error" style={{ marginBottom: 12 }}>{err}</div>}

      {data && (
        <div style={{ marginBottom: 16 }}>
          <PlotlyChart fig={data.severity_chart} />
        </div>
      )}

      <div className="section-h">Log Records — click a row to view full message</div>
      {data === null && loading
        ? <SkeletonTable rows={10} />
        : <DataTable
            columns={COLS}
            rows={data?.rows ?? []}
            pageSize={20}
            truncateColumns={["message"]}
            onRowClick={(row) => setSelectedLog(row)}
            emptyText="No logs found"
          />
      }

      {selectedLog && <LogModal log={selectedLog} onClose={() => setSelectedLog(null)} />}
    </div>
  );
}
