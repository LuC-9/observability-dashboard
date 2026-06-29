import { useEffect, useState } from "react";
import { JsonView, defaultStyles } from "react-json-view-lite";
import DataTable from "./DataTable";
import PlotlyChart from "./PlotlyChart";
import Spinner from "./Spinner";
import { api } from "../api";
import type { WaterfallResponse } from "../types";

const WF_SPAN_COLS = [
  "span_id", "parent_span_id", "span_name", "span_kind", "start_time",
  "duration_ms", "status_code", "agent_name",
  "gen_ai_input_tokens", "gen_ai_output_tokens", "llm_cost_total_usd",
];

const SCALAR_COLS = [
  "span_id", "parent_span_id", "span_name", "span_kind",
  "start_time", "end_time", "duration_ms",
  "status_code", "status_message",
  "service_name", "agent_name",
  "gen_ai_input_tokens", "gen_ai_output_tokens",
  "llm_cost_input_usd", "llm_cost_output_usd", "llm_cost_total_usd",
];

function tryParseJson(val: any): any {
  if (!val) return null;
  if (typeof val === "object") return val;
  try { return JSON.parse(String(val)); } catch { return null; }
}

function buildSpanDetail(row: Record<string, any>): Record<string, any> {
  const detail: Record<string, any> = {};
  for (const c of SCALAR_COLS) {
    const v = row[c];
    if (v !== null && v !== undefined && v !== "") detail[c] = v;
  }
  const raw = row.attributes_json;
  if (raw && raw !== "None" && raw !== "nan") {
    let attrs: Record<string, any>;
    try { attrs = JSON.parse(String(raw)); } catch { attrs = { _raw: String(raw) }; }
    // Parse nested JSON strings (llm_request, llm_response, tool args/responses)
    const nestedKeys = [
      "gcp.vertex.agent.llm_request",
      "gcp.vertex.agent.llm_response",
      "gcp.vertex.agent.tool_call_args",
      "gcp.vertex.agent.tool_response",
    ];
    for (const k of nestedKeys) {
      if (typeof attrs[k] === "string") {
        const parsed = tryParseJson(attrs[k]);
        if (parsed !== null) attrs[k] = parsed;
      }
    }
    detail.attributes = attrs;
  }
  return detail;
}

// ── LLM detail panel ─────────────────────────────────────────────────────────

function MetaChip({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#4b5563", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13, color: "#111827" }}>{String(value)}</div>
    </div>
  );
}

function ConversationBubble({ role, text }: { role: string; text: string }) {
  const isUser  = role === "user";
  const isModel = role === "model";
  return (
    <div style={{
      marginBottom: 8,
      padding: "10px 14px",
      borderRadius: 8,
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

function LlmPanel({ span, detail }: { span: Record<string, any>; detail: Record<string, any> }) {
  const attrs = (detail.attributes ?? {}) as Record<string, any>;
  const req   = tryParseJson(attrs["gcp.vertex.agent.llm_request"])  as any;
  const resp  = tryParseJson(attrs["gcp.vertex.agent.llm_response"]) as any;

  if (!req && !resp) return null;

  const model        = req?.model ?? attrs["gen_ai.request.model"] ?? "";
  const finishReason = resp?.finish_reason ?? "";
  const inputTok     = resp?.usage_metadata?.prompt_token_count     ?? span.gen_ai_input_tokens;
  const outputTok    = resp?.usage_metadata?.candidates_token_count ?? span.gen_ai_output_tokens;
  const latency      = span.duration_ms;

  // Conversation: show all turns except skip the system_instruction (very long)
  const contents: Array<{ role: string; parts: Array<{ text?: string; function_call?: any; function_response?: any }> }> =
    req?.contents ?? [];

  // Response text (concatenate text parts, note function calls)
  const responseParts: string[] = [];
  for (const part of resp?.content?.parts ?? []) {
    if (part.text)          responseParts.push(part.text);
    if (part.function_call) responseParts.push(`[tool call: ${part.function_call.name}(${JSON.stringify(part.function_call.args)})]`);
  }
  const responseText = responseParts.join("") || "(no text response)";

  return (
    <div style={{ marginTop: 16 }}>
      <div className="section-h">LLM Call Details</div>

      {/* Metadata strip */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 20, padding: "12px 16px", background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb", marginBottom: 16 }}>
        {model        && <MetaChip label="model"         value={model} />}
        {inputTok  != null && <MetaChip label="input tokens"  value={inputTok} />}
        {outputTok != null && <MetaChip label="output tokens" value={outputTok} />}
        {finishReason  && <MetaChip label="finish reason" value={finishReason} />}
        {latency   != null && <MetaChip label="latency ms"    value={Number(latency).toFixed(1)} />}
      </div>

      {/* Conversation */}
      {contents.length > 0 && (
        <>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#4b5563", marginBottom: 8 }}>
            Conversation ({contents.length} turn{contents.length !== 1 ? "s" : ""})
          </div>
          <div style={{ maxHeight: 360, overflowY: "auto", marginBottom: 12 }}>
            {contents.map((turn, i) => {
              const texts = (turn.parts ?? []).map((p) => {
                if (p.text)             return p.text;
                if (p.function_call)    return `[tool call: ${p.function_call.name}]`;
                if (p.function_response) return `[tool response: ${JSON.stringify(p.function_response.response)}]`;
                return "";
              }).filter(Boolean).join("\n");
              return texts ? <ConversationBubble key={i} role={turn.role} text={texts} /> : null;
            })}
          </div>
        </>
      )}

      {/* Model response */}
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", color: "#4b5563", marginBottom: 8 }}>Model Response</div>
      <ConversationBubble role="model" text={responseText} />
    </div>
  );
}

// ── Helper functions for Tree Waterfall ────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(2)}s`;
  }
  return `${ms.toFixed(1)}ms`;
}

function buildSpanTree(spans: any[]) {
  const spanIds = new Set(spans.map((s) => s.span_id));
  const byId: Record<string, any> = {};
  const children: Record<string, any[]> = {};

  spans.forEach((s) => {
    byId[s.span_id] = s;
    children[s.span_id] = [];
  });

  const roots: any[] = [];
  spans.forEach((s) => {
    const pid = s.parent_span_id;
    if (pid && spanIds.has(pid)) {
      children[pid].push(s);
    } else {
      roots.push(s);
    }
  });

  // Sort children by rel_start_ms
  Object.keys(children).forEach((pid) => {
    children[pid].sort((a, b) => (a.rel_start_ms ?? 0) - (b.rel_start_ms ?? 0));
  });

  // Sort roots by rel_start_ms
  roots.sort((a, b) => (a.rel_start_ms ?? 0) - (b.rel_start_ms ?? 0));

  const ordered: any[] = [];
  const depths: number[] = [];

  function dfs(span: any, depth: number) {
    ordered.push(span);
    depths.push(depth);
    const kids = children[span.span_id] || [];
    kids.forEach((kid) => dfs(kid, depth + 1));
  }

  roots.forEach((root) => dfs(root, 0));

  return { ordered, depths };
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  traceId: string;
  onClose: () => void;
}

export default function WaterfallModal({ traceId, onClose }: Props) {
  const [waterfall, setWaterfall] = useState<WaterfallResponse | null>(null);
  const [loading, setLoading]     = useState(true);
  const [err, setErr]             = useState("");
  const [selectedIdx, setSelectedIdx]     = useState<number | null>(null);
  const [spanDetail, setSpanDetail]       = useState<Record<string, any> | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.waterfall(traceId);
        if (!cancelled) {
          setWaterfall(result);
          // Auto-select the first span if available
          if (result?.spans && result.spans.length > 0) {
            const { ordered } = buildSpanTree(result.spans);
            if (ordered.length > 0) {
              setSelectedIdx(0);
              setSpanDetail(buildSpanDetail(ordered[0]));
            }
          }
        }
      } catch (e: any) {
        if (!cancelled) setErr(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [traceId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const { ordered: orderedSpans, depths } = waterfall
    ? buildSpanTree(waterfall.spans)
    : { ordered: [], depths: [] };

  const maxDuration = waterfall && orderedSpans.length > 0
    ? Math.max(...orderedSpans.map((s) => (s.rel_end_ms ?? 0)), 1)
    : 1;

  const selectedSpan = selectedIdx != null ? (orderedSpans[selectedIdx] ?? null) : null;
  const spanIds = new Set(waterfall?.spans.map(s => s.span_id) ?? []);

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "flex-start", justifyContent: "center",
        zIndex: 1000, overflowY: "auto", padding: "32px 16px",
        backdropFilter: "blur(2px)",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16,
        width: "min(1300px, 96vw)", padding: 24, position: "relative",
        boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)"
      }}>
        {/* Modal Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", color: "#1f2937" }}>
            Waterfall — <span style={{ color: "#4f46e5", fontFamily: "monospace", fontSize: 13 }}>{traceId}</span>
          </span>
          <button
            onClick={onClose}
            style={{
              background: "#f3f4f6", border: "none", color: "#4b5563", cursor: "pointer",
              fontSize: 16, width: 28, height: 28, borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "background-color 0.15s ease",
            }}
            className="hover:bg-gray-200"
          >
            ✕
          </button>
        </div>

        {loading && (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: 80, gap: 14 }}>
            <Spinner size={28} />
            <span style={{ color: "#4b5563", fontSize: 14, fontWeight: 500, letterSpacing: 0.5 }}>Loading waterfall…</span>
          </div>
        )}
        {err && <div className="status-error" style={{ marginBottom: 16 }}>{err}</div>}

        {waterfall && orderedSpans.length > 0 && (
          <>
            {/* Waterfall Gantt Table */}
            <div style={{
              background: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: 12,
              overflow: "hidden",
              marginBottom: 20,
              boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)"
            }}>
              {/* Table Column Headers */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "35% 55% 10%",
                padding: "12px 20px",
                borderBottom: "1px solid #e5e7eb",
                background: "#f9fafb",
                fontSize: 11,
                fontWeight: 700,
                color: "#4b5563",
                letterSpacing: "0.05em",
                textTransform: "uppercase"
              }}>
                <div>Span Name</div>
                <div>Timeline</div>
                <div style={{ textAlign: "right" }}>Duration</div>
              </div>

              {/* Table Rows Container */}
              <div style={{ maxHeight: 450, overflowY: "auto", position: "relative" }}>
                {/* Visual grid lines for timeline */}
                <div style={{
                  position: "absolute",
                  inset: 0,
                  display: "grid",
                  gridTemplateColumns: "35% 55% 10%",
                  pointerEvents: "none"
                }}>
                  <div></div>
                  <div style={{
                    position: "relative",
                    height: "100%",
                    display: "flex",
                    justifyContent: "space-between"
                  }}>
                    <div style={{ borderLeft: "1px dashed #f3f4f6", height: "100%" }}></div>
                    <div style={{ borderLeft: "1px dashed #f3f4f6", height: "100%" }}></div>
                    <div style={{ borderLeft: "1px dashed #f3f4f6", height: "100%" }}></div>
                    <div style={{ borderLeft: "1px dashed #f3f4f6", height: "100%" }}></div>
                    <div style={{ borderLeft: "1px dashed #f3f4f6", height: "100%" }}></div>
                  </div>
                  <div></div>
                </div>

                {/* Spans List */}
                {orderedSpans.map((span, index) => {
                  const depth = depths[index];
                  const relStart = span.rel_start_ms ?? 0;
                  const dur = span.duration_ms ?? 0.5;
                  const leftPct = (relStart / maxDuration) * 100;
                  const widthPct = Math.max(0.5, (dur / maxDuration) * 100);

                  const isSelected = selectedIdx === index;
                  const isError = span.status_code === "ERROR";

                  // Match Span Types (Root, Tool, LLM, Default)
                  const op = span.operation_name || "";
                  const name = span.span_name || "";
                  const isRoot = !span.parent_span_id || !spanIds.has(span.parent_span_id);
                  const isLlm = op === "llm" || name.startsWith("gen_ai") || name.includes("llm");
                  const isTool = op === "tool" || name.startsWith("tool");

                  let barBackground = "linear-gradient(90deg, #14b8a6, #0d9488)"; // Default Teal/Green
                  let barLabel = `${dur.toFixed(1)}ms`;
                  let barIcon = "📄";
                  let spanTypeLabel = "span";

                  if (isRoot) {
                    barBackground = "linear-gradient(90deg, #3b82f6, #1d4ed8)"; // Premium Blue
                    barLabel = `root — ${formatDuration(dur)}`;
                    barIcon = "🌐";
                    spanTypeLabel = "root";
                  } else if (isLlm) {
                    barBackground = "linear-gradient(90deg, #a78bfa, #7c3aed)"; // Rich Purple
                    barLabel = `LLM ${formatDuration(dur)}`;
                    barIcon = "✨";
                    spanTypeLabel = "LLM";
                  } else if (isTool) {
                    barBackground = "linear-gradient(90deg, #f59e0b, #d97706)"; // Orange/Gold
                    barLabel = formatDuration(dur);
                    barIcon = "🔧";
                    spanTypeLabel = "tool";
                  }

                  return (
                    <div
                      key={span.span_id}
                      onClick={() => {
                        setSelectedIdx(index);
                        setSpanDetail(buildSpanDetail(span));
                      }}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "35% 55% 10%",
                        padding: "10px 20px",
                        borderBottom: "1px solid #f3f4f6",
                        alignItems: "center",
                        cursor: "pointer",
                        background: isSelected ? "#eff6ff" : "transparent",
                        transition: "background-color 0.1s ease",
                        position: "relative",
                        zIndex: 1
                      }}
                      className="hover:bg-gray-50"
                    >
                      {/* SPAN NAME COLUMN */}
                      <div style={{
                        display: "flex",
                        alignItems: "center",
                        paddingLeft: depth * 16,
                        fontFamily: "monospace",
                        fontSize: 12,
                        color: isSelected ? "#1e40af" : "#374151",
                        fontWeight: isSelected || isRoot ? 600 : 400,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis"
                      }}>
                        {depth > 0 && (
                          <span style={{ color: "#9ca3af", marginRight: 6, userSelect: "none", fontFamily: "sans-serif" }}>
                            └
                          </span>
                        )}
                        <span style={{ marginRight: 6, fontSize: 13 }} title={spanTypeLabel}>{barIcon}</span>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }} title={name}>
                          {name}
                        </span>
                        {isError && (
                          <span
                            style={{
                              marginLeft: 8,
                              padding: "1px 5px",
                              background: "#fee2e2",
                              color: "#ef4444",
                              borderRadius: 4,
                              fontSize: 9,
                              fontWeight: 700,
                              textTransform: "uppercase"
                            }}
                            title={span.status_message || "Error"}
                          >
                            ERROR
                          </span>
                        )}
                      </div>

                      {/* TIMELINE COLUMN */}
                      <div style={{ position: "relative", width: "100%", height: 24, display: "flex", alignItems: "center" }}>
                        <div
                          style={{
                            position: "absolute",
                            left: `${leftPct}%`,
                            width: `${widthPct}%`,
                            background: isError ? "linear-gradient(90deg, #f87171, #ef4444)" : barBackground,
                            height: 18,
                            borderRadius: 4,
                            boxShadow: "0 1px 2px rgba(0,0,0,0.08)",
                            border: isError ? "1.5px solid #dc2626" : "none",
                            display: "flex",
                            alignItems: "center",
                            padding: "0 6px",
                            boxSizing: "border-box",
                            transition: "all 0.2s ease",
                            overflow: "hidden",
                            minWidth: 6
                          }}
                        >
                          {/* Label inside bar: only show if width is wide enough */}
                          {widthPct > 12 ? (
                            <span style={{
                              color: "#ffffff",
                              fontSize: 10,
                              fontWeight: 600,
                              fontFamily: "sans-serif",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis"
                            }}>
                              {barLabel}
                            </span>
                          ) : null}
                        </div>

                        {/* Label outside bar (to the right): only show if width is small */}
                        {widthPct <= 12 && (
                          <span style={{
                            position: "absolute",
                            left: `calc(${leftPct + widthPct}% + 8px)`,
                            color: isError ? "#ef4444" : "#6b7280",
                            fontSize: 10,
                            fontWeight: 600,
                            fontFamily: "sans-serif",
                            whiteSpace: "nowrap"
                          }}>
                            {barLabel}
                          </span>
                        )}
                      </div>

                      {/* DURATION COLUMN */}
                      <div style={{
                        textAlign: "right",
                        fontFamily: "monospace",
                        fontSize: 12,
                        color: "#4b5563"
                      }}>
                        {formatDuration(dur)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Details Panel for Selected Span */}
            {spanDetail && selectedSpan && (
              <div style={{
                marginTop: 20,
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                borderRadius: 12,
                padding: 20,
                boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "#1f2937", textTransform: "uppercase", letterSpacing: 0.5 }}>
                    Span Details
                  </span>
                  <span style={{
                    fontFamily: "monospace",
                    fontSize: 11,
                    color: "#4f46e5",
                    background: "#e0e7ff",
                    padding: "2px 6px",
                    borderRadius: 4
                  }}>
                    {selectedSpan.span_name}
                  </span>
                </div>

                {/* LLM conversation panel — shown only for spans with llm_request/llm_response */}
                <LlmPanel span={selectedSpan} detail={spanDetail} />

                <div className="section-h" style={{ marginTop: 20, marginBottom: 8 }}>Raw Span Attributes</div>
                <div className="json-viewer" style={{ border: "1px solid #e5e7eb", borderRadius: 8, overflow: "hidden" }}>
                  <JsonView data={spanDetail} shouldExpandNode={(level) => level < 2} style={{...defaultStyles, container: 'bg-gray-50 p-3 rounded'}} />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
