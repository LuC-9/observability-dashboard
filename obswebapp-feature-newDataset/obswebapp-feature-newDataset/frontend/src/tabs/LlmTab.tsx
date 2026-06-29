import { useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import PlotlyChart from "../components/PlotlyChart";
import WaterfallModal from "../components/WaterfallModal";
import Spinner from "../components/Spinner";
import { SkeletonCharts, SkeletonTable } from "../components/Skeleton";
import { api } from "../api";
import type { FilterOptions, LlmResponse, SharedFilters } from "../types";

const TABLE_COLS = [
  "llm_call_id", "model_name", "provider", "tokens_input", "tokens_output",
  "latency_ms", "cost", "status", "trace_id", "timestamp",
];

function parseJson(raw: any): any {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  try { return JSON.parse(String(raw)); } catch { return null; }
}

const labelStyle: React.CSSProperties = {
  fontSize: 10, fontWeight: 600, letterSpacing: 1,
  textTransform: "uppercase", color: "#9ca3af", marginBottom: 8,
};

const preStyle: React.CSSProperties = {
  background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 6,
  padding: "12px 14px", fontFamily: "ui-monospace, monospace", fontSize: 12,
  color: "#374151", whiteSpace: "pre-wrap", wordBreak: "break-word",
  maxHeight: 260, overflowY: "auto", margin: "8px 0 0",
};

function ConversationBubble({ role, text }: { role: string; text: string }) {
  const isUser  = role === "user";
  const isModel = role === "model";
  return (
    <div style={{
      marginBottom: 8, padding: "10px 14px", borderRadius: 8,
      background: isUser ? "#dbeafe" : isModel ? "#f3e8ff" : "#f9fafb",
      border: `1px solid ${isUser ? "#93c5fd" : isModel ? "#e9d5ff" : "#e5e7eb"}`,
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase", color: isUser ? "#3b82f6" : isModel ? "#8b5cf6" : "#6b7280", marginBottom: 6 }}>
        {role}
      </div>
      <div style={{ fontSize: 13, color: "#374151", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {text}
      </div>
    </div>
  );
}

function LlmDetailModal({
  row, onClose, onViewTrace,
}: { row: Record<string, any>; onClose: () => void; onViewTrace: (id: string) => void }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const attrs = parseJson(row.attributes_json) ?? {};
  const req  = attrs["gcp.vertex.agent.llm_request"]  ? parseJson(attrs["gcp.vertex.agent.llm_request"])  : null;
  const resp = attrs["gcp.vertex.agent.llm_response"] ? parseJson(attrs["gcp.vertex.agent.llm_response"]) : null;

  const sysInstruction: string | null = req?.config?.system_instruction ?? null;
  const contents: Array<{ role: string; parts: Array<{ text?: string; function_call?: any; function_response?: any }> }> =
    req?.contents ?? [];

  const responseParts: string[] = [];
  for (const part of resp?.content?.parts ?? []) {
    if (part.text)          responseParts.push(part.text);
    if (part.function_call) responseParts.push(`[tool call: ${part.function_call.name}(${JSON.stringify(part.function_call.args)})]`);
  }
  const responseText = responseParts.join("") || null;

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
        width: "min(900px, 95vw)", padding: 24,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", color: "#6b7280" }}>
            LLM Interaction — {row.model_name}
          </span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0 }}>✕</button>
        </div>

        {/* Metadata strip */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 16 }}>
          {["model_name", "provider", "tokens_input", "tokens_output", "total_tokens", "latency_ms", "cost", "status", "timestamp"].map((k) =>
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

        {/* System instruction */}
        {sysInstruction && (
          <details style={{ marginBottom: 16 }}>
            <summary style={{ ...labelStyle, cursor: "pointer", userSelect: "none" }}>System Instruction</summary>
            <pre style={preStyle}>{sysInstruction}</pre>
          </details>
        )}

        {/* Conversation turns */}
        {contents.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={labelStyle}>Conversation ({contents.length} turn{contents.length !== 1 ? "s" : ""})</div>
            <div style={{ maxHeight: 400, overflowY: "auto" }}>
              {contents.map((turn, i) => {
                const text = (turn.parts ?? []).map((p) => {
                  if (p.text)              return p.text;
                  if (p.function_call)     return `[tool call: ${p.function_call.name}]`;
                  if (p.function_response) return `[tool response: ${JSON.stringify(p.function_response.response)}]`;
                  return "";
                }).filter(Boolean).join("\n");
                return text ? <ConversationBubble key={i} role={turn.role} text={text} /> : null;
              })}
            </div>
          </div>
        )}

        {/* Model response */}
        {responseText != null && (
          <div>
            <div style={labelStyle}>Model Response</div>
            <ConversationBubble role="model" text={responseText} />
          </div>
        )}

        {/* LangGraph fallback: gen_ai.prompt / gen_ai.completion */}
        {!req && !resp && (attrs["gen_ai.prompt"] || attrs["gen_ai.completion"]) && (
          <div>
            {attrs["gen_ai.prompt"] && (
              <div style={{ marginBottom: 16 }}>
                <div style={labelStyle}>Prompt</div>
                <ConversationBubble role="user" text={String(attrs["gen_ai.prompt"])} />
              </div>
            )}
            {attrs["gen_ai.completion"] && (
              <div>
                <div style={labelStyle}>Completion</div>
                <ConversationBubble role="model" text={String(attrs["gen_ai.completion"])} />
              </div>
            )}
          </div>
        )}

        {!req && !resp && !attrs["gen_ai.prompt"] && !attrs["gen_ai.completion"] && (
          <div style={{ fontSize: 12, color: "#9ca3af", fontStyle: "italic" }}>
            No prompt/response data available for this span.
          </div>
        )}
      </div>
    </div>
  );
}

export default function LlmTab({ filters, options }: { filters: SharedFilters; options: FilterOptions }) {
  const [modelName, setModelName] = useState("All");
  const [provider, setProvider]   = useState("All");
  const [status, setStatus]       = useState("All");

  const [data, setData]       = useState<LlmResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]         = useState("");
  const [selectedRow, setSelectedRow]           = useState<Record<string, any> | null>(null);
  const [waterfallTraceId, setWaterfallTraceId] = useState<string | null>(null);

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.llm({ ...filters, model_name: modelName, provider, status }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters, modelName, provider, status]);

  const models    = ["All", ...(options.models ?? [])];
  const providers = ["All", ...(options.providers ?? [])];

  return (
    <div>
      <div className="tab-filters">
        <div style={{ flex: 1, minWidth: 180 }}>
          <label className="field-label">Model</label>
          <select className="field-select" value={modelName} onChange={(e) => setModelName(e.target.value)}>
            {models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Provider</label>
          <select className="field-select" value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providers.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label className="field-label">Status</label>
          <select className="field-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {["All", "success", "error"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {loading && <Spinner size={16} />}
      </div>

      {err && <div className="status-error" style={{ marginBottom: 12 }}>{err}</div>}

      {data === null && loading
        ? <SkeletonCharts />
        : data && (
            <div className="responsive-grid" style={{ marginBottom: 16 }}>
              <PlotlyChart fig={data.charts.cost_by_model} />
              <PlotlyChart fig={data.charts.latency_hist} />
              <PlotlyChart fig={data.charts.tokens_over_time} />
              <PlotlyChart fig={data.charts.provider_pie} />
            </div>
          )
      }

      <div className="section-h">LLM Interactions — click a row to view prompt & response</div>
      {data === null && loading
        ? <SkeletonTable />
        : <DataTable
            columns={TABLE_COLS}
            rows={data?.rows ?? []}
            onRowClick={(row) => setSelectedRow(row)}
            emptyText="No interactions found"
            pageSize={25}
            truncateColumns={["llm_call_id", "trace_id"]}
          />
      }

      {selectedRow && (
        <LlmDetailModal
          row={selectedRow}
          onClose={() => setSelectedRow(null)}
          onViewTrace={(id) => { setSelectedRow(null); setWaterfallTraceId(id); }}
        />
      )}
      {waterfallTraceId && <WaterfallModal traceId={waterfallTraceId} onClose={() => setWaterfallTraceId(null)} />}
    </div>
  );
}
