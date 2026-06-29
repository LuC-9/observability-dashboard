import { useEffect, useMemo, useState, lazy, Suspense } from "react";
import FilterBar from "./components/FilterBar";
import StatusBanner from "./components/StatusBanner";
import Tabs from "./components/Tabs";
import Spinner from "./components/Spinner";
import { api } from "./api";

const OverviewTab = lazy(() => import("./tabs/OverviewTab"));
const LogsTab = lazy(() => import("./tabs/LogsTab"));
const TracesTab = lazy(() => import("./tabs/TracesTab"));
const MetricsTab = lazy(() => import("./tabs/MetricsTab"));
const SessionsTab = lazy(() => import("./tabs/SessionsTab"));
const LlmTab = lazy(() => import("./tabs/LlmTab"));
const ToolsTab = lazy(() => import("./tabs/ToolsTab"));
const ErrorsTab = lazy(() => import("./tabs/ErrorsTab"));
import type { FilterOptions, SharedFilters, StatusMsg } from "./types";

const TAB_NAMES = ["Overview", "Logs", "Traces", "Metrics", "Sessions", "LLM", "Tools", "Errors"];

function defaultDates(): { start: string; end: string } {
  const now = new Date();
  const day  = (d: Date) => d.toISOString().slice(0, 10);
  const past = new Date(now.getTime() - 24 * 3600 * 1000);
  return { start: day(past), end: day(now) };
}

function statusFromOptions(opts: FilterOptions, key: number): StatusMsg {
  if (opts.errors && opts.errors.length) {
    return {
      kind: "error",
      key,
      text: `⚠ BigQuery errors on: ${opts.errors.join(", ")}. Check IAM permissions (BigQuery Data Viewer + Job User required).`,
    };
  }
  if (!opts.services.length && !opts.agents.length && !opts.metric_names.length) {
    return { kind: "warn", key, text: "⚠ Filters loaded but no data found — tables may be empty." };
  }
  const loaded = opts.services.length + opts.agents.length + opts.metric_names.length;
  return { kind: "ok", key, text: `✓ Filters refreshed — ${loaded} distinct values loaded.` };
}

export default function App() {
  const dates = useMemo(defaultDates, []);
  const [filters, setFilters] = useState<SharedFilters>({
    quick: "Last 24 Hours", start: dates.start, end: dates.end, service: "All",
    project: api.getProject(),
  });
  const [options, setOptions] = useState<FilterOptions>({
    services: [], environments: [], severities: [], agents: [], metric_names: [],
    models: [], providers: [], tool_names: [], tool_types: [], tool_statuses: [], components: [],
    errors: [], error_types: [], projects: [],
  });
  const [quickRanges, setQuickRanges] = useState<string[]>([
    "Last 1 Hour", "Last 6 Hours", "Last 24 Hours", "Last 7 Days", "Last 30 Days", "Custom",
  ]);
  const [status, setStatus] = useState<StatusMsg>({ kind: null, text: "", key: 0 });
  const [refreshing, setRefreshing] = useState(false);
  const [active, setActive] = useState("Overview");

  async function loadFilters(initial: boolean, projectOverride?: string) {
    setRefreshing(true);
    try {
      const activeProj = projectOverride !== undefined ? projectOverride : filters.project;
      const opts = await api.filters(activeProj);
      setOptions(opts);

      let nextProject = activeProj;
      if (!activeProj && opts.projects && opts.projects.length > 0) {
        nextProject = opts.projects[0];
        api.setProject(nextProject);
        setFilters((prev) => ({ ...prev, project: nextProject }));
      }

      setStatus(statusFromOptions(opts, Date.now()));
    } catch (e: any) {
      setStatus({ kind: "error", text: `Failed to load filters: ${e.message}`, key: Date.now() });
    } finally {
      setRefreshing(false);
    }
    if (initial) {
      try { setQuickRanges(await api.quickRanges()); } catch {}
    }
  }

  useEffect(() => { loadFilters(true); }, []);

  function handleProjectChange(newProject: string) {
    api.setProject(newProject);
    setFilters((prev) => ({ ...prev, project: newProject, service: "All" }));
    loadFilters(false, newProject);
  }

  return (
    <>
      <header className="app-header justify-between">
        <div className="header-left">
          <h1 className="text-xl font-bold text-gray-900">OTel Dashboard</h1>
          {options.projects && options.projects.length > 0 && (
            <div className="app-header-project">
              <span className="header-label">Project</span>
              <select
                className="header-project-select"
                value={filters.project}
                onChange={(e) => handleProjectChange(e.target.value)}
              >
                {options.projects.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </header>

      {/* ── Page body ── */}
      <div className="app-container">
        <FilterBar
          value={filters}
          onChange={setFilters}
          quickRanges={quickRanges}
          services={options.services}
          onRefresh={() => loadFilters(false)}
          refreshing={refreshing}
        />
        <StatusBanner msg={status} />

        <Tabs tabs={TAB_NAMES} active={active} onChange={setActive} />

        <Suspense fallback={
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 200 }}>
            <Spinner size={32} />
          </div>
        }>
          {active === "Overview" && <OverviewTab filters={filters} />}
          {active === "Logs" && <LogsTab filters={filters} options={options} />}
          {active === "Traces" && <TracesTab filters={filters} options={options} />}
          {active === "Metrics" && <MetricsTab filters={filters} options={options} />}
          {active === "Sessions" && <SessionsTab filters={filters} options={options} />}
          {active === "LLM" && <LlmTab filters={filters} options={options} />}
          {active === "Tools" && <ToolsTab filters={filters} options={options} />}
          {active === "Errors" && <ErrorsTab filters={filters} options={options} />}
        </Suspense>
      </div>
    </>
  );
}
