import { useEffect, useState } from "react";
import { JsonView, defaultStyles } from "react-json-view-lite";
import DataTable from "../components/DataTable";
import PlotlyChart from "../components/PlotlyChart";
import WaterfallModal from "../components/WaterfallModal";
import Spinner from "../components/Spinner";
import { SkeletonCharts, SkeletonTable } from "../components/Skeleton";
import { api } from "../api";
import type { FilterOptions, SharedFilters, ToolsResponse } from "../types";

const TABLE_COLS = [
  "execution_id", "tool_name", "tool_type", "latency_ms", "status", "error_message", "timestamp",
];

const toolPreStyle: React.CSSProperties = {
  background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 6,
  padding: "12px 14px", fontFamily: "ui-monospace, monospace", fontSize: 12,
  color: "#374151", whiteSpace: "pre-wrap", wordBreak: "break-word",
  maxHeight: 300, overflowY: "auto", margin: 0,
};

function ToolDetailModal({ row, onClose, onViewTrace }: { row: Record<string, any>; onClose: () => void; onViewTrace: (id: string) => void }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function parsePayload(raw: any): any {
    if (!raw) return {};
    if (typeof raw === "object") return raw;
    try { return JSON.parse(String(raw)); } catch { return String(raw); }
  }

  const displayName = row.tool_display_name ?? row.tool_name;
  // LangGraph: tool.input / tool.output extracted server-side or from attributes
  const attrs = parsePayload(row.input_payload);
  const toolInput  = row.tool_input  ?? (typeof attrs === "object" ? attrs["tool.input"]  : null);
  const toolOutput = row.output_payload ?? (typeof attrs === "object" ? attrs["tool.output"] : null);
  const hasToolPayloads = toolInput != null || toolOutput != null;

  const labelStyle: React.CSSProperties = {
    fontSize: 10, fontWeight: 600, letterSpacing: 1,
    textTransform: "uppercase", color: "#9ca3af", marginBottom: 8,
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)",
        display: "flex", alignItems: "flex-start", justifyContent: "center",
        zIndex: 1000, overflowY: "auto", padding: "32px 16px",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 12,
        width: "min(800px, 95vw)", padding: 24,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", color: "#6b7280" }}>
            Tool Execution — {displayName}
          </span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0 }}>✕</button>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 16 }}>
          {["tool_name", "tool_type", "status", "latency_ms", "error_message", "timestamp"].map((k) =>
            row[k] != null && (
              <div key={k}>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 3 }}>{k}</div>
                <div style={{ fontSize: 13, color: "#111827" }}>{String(row[k])}</div>
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

        {/* LangGraph: clean tool.input / tool.output */}
        {hasToolPayloads && (
          <>
            {toolInput != null && (
              <div style={{ marginBottom: 12 }}>
                <div style={labelStyle}>Input</div>
                <pre style={toolPreStyle}>{String(toolInput)}</pre>
              </div>
            )}
            {toolOutput != null && (
              <div style={{ marginBottom: 12 }}>
                <div style={labelStyle}>Output</div>
                <pre style={toolPreStyle}>{String(toolOutput)}</pre>
              </div>
            )}
          </>
        )}

        {/* ADK / fallback: show full attributes JSON */}
        {!hasToolPayloads && (
          <div style={{ marginBottom: 12 }}>
            <div style={labelStyle}>Attributes</div>
            <div className="json-viewer">
              <JsonView data={parsePayload(row.input_payload)} shouldExpandNode={(l) => l < 3} style={defaultStyles} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ToolsTab({ filters, options }: { filters: SharedFilters; options: FilterOptions }) {
  const [toolName, setToolName] = useState("All");
  const [toolType, setToolType] = useState("All");
  const [status, setStatus]     = useState("All");

  const [data, setData]       = useState<ToolsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]         = useState("");
  const [selectedRow, setSelectedRow]     = useState<Record<string, any> | null>(null);
  const [waterfallTraceId, setWaterfallTraceId] = useState<string | null>(null);

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.tools({ ...filters, tool_name: toolName, tool_type: toolType, status }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters, toolName, toolType, status]);

  const toolNames = ["All", ...(options.tool_names ?? [])];
  const toolTypes = ["All", ...(options.tool_types ?? [])];
  const toolStatuses = ["All", ...(options.tool_statuses ?? [])];

  return (
    <div>
      <div className="tab-filters">
        <div style={{ flex: 1, minWidth: 180 }}>
          <label className="field-label">Tool</label>
          <select className="field-select" value={toolName} onChange={(e) => setToolName(e.target.value)}>
            {toolNames.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Tool Type</label>
          <select className="field-select" value={toolType} onChange={(e) => setToolType(e.target.value)}>
            {toolTypes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Status</label>
          <select className="field-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {toolStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {loading && <Spinner size={16} />}
      </div>

      {err && <div className="status-error" style={{ marginBottom: 12 }}>{err}</div>}

      {data === null && loading
        ? <SkeletonCharts />
        : data && (
            <div className="responsive-grid" style={{ marginBottom: 16 }}>
              <PlotlyChart fig={data.charts.calls_by_tool} />
              <PlotlyChart fig={data.charts.latency_by_tool} />
              <PlotlyChart fig={data.charts.status_pie} />
              <PlotlyChart fig={data.charts.executions_over_time} />
            </div>
          )
      }

      <div className="section-h">Tool Executions — click a row to view payloads</div>
      {data === null && loading
        ? <SkeletonTable />
        : <DataTable
            columns={TABLE_COLS}
            rows={data?.rows ?? []}
            onRowClick={(row) => setSelectedRow(row)}
            emptyText="No executions found"
            pageSize={25}
            truncateColumns={["execution_id", "error_message"]}
          />
      }

      {selectedRow && <ToolDetailModal row={selectedRow} onClose={() => setSelectedRow(null)} onViewTrace={(id) => setWaterfallTraceId(id)} />}
      {waterfallTraceId && <WaterfallModal traceId={waterfallTraceId} onClose={() => setWaterfallTraceId(null)} />}
    </div>
  );
}
