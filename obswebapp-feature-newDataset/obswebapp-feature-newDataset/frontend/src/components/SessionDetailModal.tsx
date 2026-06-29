import { useEffect, useState } from "react";
import DataTable from "./DataTable";
import WaterfallModal from "./WaterfallModal";
import Spinner from "./Spinner";
import { api } from "../api";
import type { SessionDetailResponse } from "../types";

const AT_COLS   = ["step_number", "step_type", "decision", "tool_name", "llm_call_id", "timestamp"];
const LLM_COLS  = ["model_name", "provider", "tokens_input", "tokens_output", "latency_ms", "cost", "status", "timestamp"];
const TOOL_COLS = ["tool_name", "tool_type", "status", "latency_ms", "trace_id", "timestamp"];

// ── Conversation components ───────────────────────────────────────────────────

function parseJson(raw: any): any {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  try { return JSON.parse(String(raw)); } catch { return null; }
}

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

function LlmConversationModal({ row, onClose }: { row: Record<string, any>; onClose: () => void }) {
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
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)",
        display: "flex", alignItems: "flex-start", justifyContent: "center",
        zIndex: 1100, overflowY: "auto", padding: "32px 16px",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 12,
        width: "min(860px, 95vw)", padding: 24,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", color: "#6b7280" }}>
            LLM Call — {row.model_name}
          </span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0 }}>✕</button>
        </div>

        {/* Metadata strip */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 16, padding: "10px 14px", background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
          {["model_name", "provider", "tokens_input", "tokens_output", "latency_ms", "cost", "status"].map((k) =>
            row[k] != null && (
              <div key={k}>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 3 }}>{k}</div>
                <div style={{ fontSize: 13, color: "#111827" }}>{String(row[k])}</div>
              </div>
            )
          )}
        </div>

        {sysInstruction && (
          <details style={{ marginBottom: 16 }}>
            <summary style={{ ...labelStyle, cursor: "pointer", userSelect: "none" }}>System Instruction</summary>
            <pre style={preStyle}>{sysInstruction}</pre>
          </details>
        )}

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

interface Props {
  sessionId: string;
  onClose: () => void;
}

export default function SessionDetailModal({ sessionId, onClose }: Props) {
  const [data, setData]         = useState<SessionDetailResponse | null>(null);
  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState("");
  const [waterfallTraceId, setWaterfallTraceId] = useState<string | null>(null);
  const [selectedLlmRow, setSelectedLlmRow]     = useState<Record<string, any> | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.sessionDetail(sessionId);
        if (!cancelled) setData(result);
      } catch (e: any) {
        if (!cancelled) setErr(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [sessionId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const session = data?.session ?? {};

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
        width: "min(1200px, 96vw)", padding: 24,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", color: "#6b7280" }}>
            Session Detail — <span style={{ fontFamily: "monospace", fontSize: 12, color: "#6b7280" }}>{sessionId}</span>
          </span>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0 }}
          >
            ✕
          </button>
        </div>

        {loading && (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: 48, gap: 14 }}>
            <Spinner size={28} />
            <span style={{ color: "#6b7280", fontSize: 13, letterSpacing: 0.5 }}>Loading session…</span>
          </div>
        )}
        {err && <div className="status-error">{err}</div>}

        {data && (
          <>
            {/* Session metadata */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 20, padding: "12px 16px", background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
              {["agent_id", "status", "total_turns", "start_time", "end_time", "total_cost"].map((k) =>
                session[k] != null && (
                  <div key={k}>
                    <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#9ca3af", marginBottom: 3 }}>{k}</div>
                    <div style={{ fontSize: 13, color: "#111827" }}>
                      {k === "total_cost" ? `$${Number(session[k]).toFixed(6)}` : String(session[k])}
                    </div>
                  </div>
                )
              )}
            </div>

            <div className="section-h">Agent Traces</div>
            <DataTable
              columns={AT_COLS}
              rows={data.agent_traces}
              emptyText="No agent traces"
              pageSize={10}
              truncateColumns={["llm_call_id"]}
            />

            <div className="section-h" style={{ marginTop: 16 }}>LLM Interactions — click a row to view prompt & response</div>
            <DataTable
              columns={LLM_COLS}
              rows={data.llm_interactions}
              emptyText="No LLM interactions"
              pageSize={10}
              onRowClick={(row) => setSelectedLlmRow(row)}
            />

            <div className="section-h" style={{ marginTop: 16 }}>Tool Executions — click a row to view OTel trace</div>
            <DataTable
              columns={TOOL_COLS}
              rows={data.tool_executions}
              emptyText="No tool executions"
              pageSize={10}
              truncateColumns={["trace_id"]}
              onRowClick={(row) => row.trace_id && setWaterfallTraceId(row.trace_id)}
            />
          </>
        )}
      </div>
      {waterfallTraceId && <WaterfallModal traceId={waterfallTraceId} onClose={() => setWaterfallTraceId(null)} />}
      {selectedLlmRow && <LlmConversationModal row={selectedLlmRow} onClose={() => setSelectedLlmRow(null)} />}
    </div>
  );
}
