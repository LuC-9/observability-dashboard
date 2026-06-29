// Types mirror backend/models.py

export interface FilterOptions {
  services: string[];
  environments: string[];
  severities: string[];
  agents: string[];
  metric_names: string[];
  models: string[];
  providers: string[];
  tool_names: string[];
  tool_types: string[];
  tool_statuses: string[];
  components: string[];
  errors: string[];
  error_types: string[];
  projects?: string[];
}

export interface SharedFilters {
  quick: string;
  start: string;
  end: string;
  service: string;
  project: string;
}

export interface OverviewStats {
  total_spans: number;
  error_spans: number;
  avg_duration_ms: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_logs: number;
}

// Plotly figure shape: {data: [...], layout: {...}}
export interface PlotlyFig {
  data: any[];
  layout: any;
}

export interface OverviewResponse {
  stats: OverviewStats;
  charts: {
    cost: PlotlyFig;
    latency: PlotlyFig;
    tokens: PlotlyFig;
    errors: PlotlyFig;
  };
}

export interface LogsResponse {
  rows: Record<string, any>[];
  severity_chart: PlotlyFig;
}

export interface TracesResponse {
  trace_list: Record<string, any>[];
  spans: Record<string, any>[];
  charts: {
    latency_hist: PlotlyFig;
    cost: PlotlyFig;
    tokens: PlotlyFig;
    by_agent: PlotlyFig;
  };
}

export interface WaterfallResponse {
  chart: PlotlyFig;
  spans: Record<string, any>[];
}

export interface MetricsResponse {
  rows: Record<string, any>[];
  metric_charts: PlotlyFig[];
  bar_chart: PlotlyFig;
}

export interface SessionsResponse {
  sessions: Record<string, any>[];
  charts: {
    status_pie: PlotlyFig;
    sessions_over_time: PlotlyFig;
    cost_by_agent: PlotlyFig;
    turns_hist: PlotlyFig;
  };
}

export interface SessionDetailResponse {
  session: Record<string, any>;
  agent_traces: Record<string, any>[];
  llm_interactions: Record<string, any>[];
  tool_executions: Record<string, any>[];
}

export interface LlmResponse {
  rows: Record<string, any>[];
  charts: {
    cost_by_model: PlotlyFig;
    latency_hist: PlotlyFig;
    tokens_over_time: PlotlyFig;
    provider_pie: PlotlyFig;
  };
}

export interface ToolsResponse {
  rows: Record<string, any>[];
  charts: {
    calls_by_tool: PlotlyFig;
    latency_by_tool: PlotlyFig;
    status_pie: PlotlyFig;
    executions_over_time: PlotlyFig;
  };
}

export interface ErrorsResponse {
  rows: Record<string, any>[];
  charts: {
    errors_over_time: PlotlyFig;
    by_component: PlotlyFig;
    by_type: PlotlyFig;
    severity_pie: PlotlyFig;
  };
}

export type StatusKind = "ok" | "warn" | "error" | null;
export interface StatusMsg {
  kind: StatusKind;
  text: string;
  key: number;
}
