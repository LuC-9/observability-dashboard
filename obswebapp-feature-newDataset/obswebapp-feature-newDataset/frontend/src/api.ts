import type {
  ErrorsResponse,
  FilterOptions,
  LlmResponse,
  LogsResponse,
  MetricsResponse,
  OverviewResponse,
  SessionDetailResponse,
  SessionsResponse,
  SharedFilters,
  ToolsResponse,
  TracesResponse,
  WaterfallResponse,
} from "./types";

let activeProject = localStorage.getItem("otel_project") || "";

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { 
      "content-type": "application/json",
      ...(activeProject ? { "x-gcp-project": activeProject } : {})
    },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url, {
    headers: {
      ...(activeProject ? { "x-gcp-project": activeProject } : {})
    }
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

export const api = {
  setProject: (p: string) => {
    activeProject = p;
    localStorage.setItem("otel_project", p);
  },
  getProject: () => activeProject,

  filters:     (project?: string) => {
    const p = project || activeProject;
    return getJSON<FilterOptions>(`/api/filters${p ? `?project=${encodeURIComponent(p)}` : ""}`);
  },
  quickRanges:() => getJSON<string[]>("/api/quick-ranges"),

  overview: (f: SharedFilters) =>
    postJSON<OverviewResponse>("/api/overview", f),

  logs: (f: SharedFilters & { severity: string; environment: string; limit: number }) =>
    postJSON<LogsResponse>("/api/logs", f),

  traces: (f: SharedFilters & { agent: string; status: string; limit: number }) =>
    postJSON<TracesResponse>("/api/traces", f),

  waterfall: (traceId: string) =>
    getJSON<WaterfallResponse>(`/api/trace/${encodeURIComponent(traceId)}/waterfall`),

  metrics: (f: SharedFilters & { agent: string; metric_name: string }) =>
    postJSON<MetricsResponse>("/api/metrics", f),

  sessions: (f: SharedFilters & { agent: string; status: string }) =>
    postJSON<SessionsResponse>("/api/sessions", f),

  sessionDetail: (sessionId: string) =>
    getJSON<SessionDetailResponse>(`/api/session/${encodeURIComponent(sessionId)}`),

  llm: (f: SharedFilters & { model_name: string; provider: string; status: string }) =>
    postJSON<LlmResponse>("/api/llm", f),

  tools: (f: SharedFilters & { tool_name: string; tool_type: string; status: string }) =>
    postJSON<ToolsResponse>("/api/tools", f),

  errors: (f: SharedFilters & { component: string; error_type: string; severity: string }) =>
    postJSON<ErrorsResponse>("/api/errors", f),
};
