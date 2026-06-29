"""Pydantic request/response schemas for the dashboard API."""
from typing import Any
from pydantic import BaseModel, Field


class FilterOptions(BaseModel):
    services: list[str]
    environments: list[str]
    severities: list[str]
    agents: list[str]
    metric_names: list[str]
    models: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    tool_types: list[str] = Field(default_factory=list)
    tool_statuses: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    error_types: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)


class DateRangeRequest(BaseModel):
    quick: str = "Last 24 Hours"
    start: str = ""
    end: str = ""
    service: str = "All"


class OverviewRequest(DateRangeRequest):
    pass


class LogsRequest(DateRangeRequest):
    severity: str = "All"
    environment: str = "All"
    limit: int = 500


class TracesRequest(DateRangeRequest):
    agent: str = "All"
    status: str = "All"
    limit: int = 100


class MetricsRequest(DateRangeRequest):
    agent: str = "All"
    metric_name: str = "All"


class SessionsRequest(DateRangeRequest):
    agent: str = "All"
    status: str = "All"


class LlmRequest(DateRangeRequest):
    model_name: str = "All"
    provider: str = "All"
    status: str = "All"


class ToolsRequest(DateRangeRequest):
    tool_name: str = "All"
    tool_type: str = "All"
    status: str = "All"


class ErrorsRequest(DateRangeRequest):
    component: str = "All"
    error_type: str = "All"
    severity: str = "All"


class OverviewStats(BaseModel):
    total_spans: int
    error_spans: int
    avg_duration_ms: float
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_logs: int


class OverviewResponse(BaseModel):
    stats: OverviewStats
    charts: dict[str, Any]


class LogsResponse(BaseModel):
    rows: list[dict[str, Any]]
    severity_chart: dict[str, Any]


class TracesResponse(BaseModel):
    trace_list: list[dict[str, Any]]
    spans: list[dict[str, Any]]
    charts: dict[str, Any]


class WaterfallResponse(BaseModel):
    chart: dict[str, Any]
    spans: list[dict[str, Any]]


class MetricsResponse(BaseModel):
    rows: list[dict[str, Any]]
    metric_charts: list[dict[str, Any]]
    bar_chart: dict[str, Any]


class SessionsResponse(BaseModel):
    sessions: list[dict[str, Any]]
    charts: dict[str, Any]   # status_pie, sessions_over_time, cost_by_agent, turns_hist


class SessionDetailResponse(BaseModel):
    session: dict[str, Any]
    agent_traces: list[dict[str, Any]]
    llm_interactions: list[dict[str, Any]]
    tool_executions: list[dict[str, Any]]


class LlmResponse(BaseModel):
    rows: list[dict[str, Any]]
    charts: dict[str, Any]   # cost_by_model, latency_hist, tokens_over_time, provider_pie


class ToolsResponse(BaseModel):
    rows: list[dict[str, Any]]
    charts: dict[str, Any]   # calls_by_tool, latency_by_tool, status_pie, executions_over_time


class ErrorsResponse(BaseModel):
    rows: list[dict[str, Any]]
    charts: dict[str, Any]   # errors_over_time, by_component, by_type, severity_pie
