import { useCallback, useEffect, useState } from "react";
import { Layout, Tabs, App as AntApp, Alert } from "antd";
import { useAuth } from "./auth";
import { get, api, Scope } from "./api";
import Login from "./pages/Login";
import AppHeader from "./components/AppHeader";
import FilterBar from "./components/FilterBar";
import GlobalSearch, { SearchAction } from "./components/GlobalSearch";
import SettingsDrawer, { Settings } from "./components/SettingsDrawer";
import TraceDrawer from "./components/TraceDrawer";
import Overview from "./views/Overview";
import Traces from "./views/Traces";
import Logs from "./views/Logs";
import Metrics from "./views/Metrics";
import Cost from "./views/Cost";
import Sessions from "./views/Sessions";
import Tools from "./views/Tools";
import Insights from "./views/Insights";
import Health from "./views/Health";
import Compare from "./views/Compare";
import Admin from "./views/Admin";

function loadSettings(): Settings {
  return {
    budgetCost: Number(localStorage.getItem("budgetCost") || 0),
    budgetErr: Number(localStorage.getItem("budgetErr") || 0),
    autoSeconds: Number(localStorage.getItem("autoSeconds") || 60),
    defaultRange: localStorage.getItem("defaultRange") || "1d",
    pageSize: Number(localStorage.getItem("pageSize") || 50),
  };
}

function readUrl(defaultRange: string): { scope: Scope; tab: string } {
  const p = new URLSearchParams(location.search);
  return {
    scope: {
      project: p.get("project") || undefined, platform: p.get("platform") || undefined,
      service: p.get("service") || undefined, time_range: p.get("time_range") || defaultRange,
      start: p.get("start") || undefined, end: p.get("end") || undefined,
    },
    tab: p.get("tab") || "overview",
  };
}
function writeUrl(scope: Scope, tab: string) {
  const p = new URLSearchParams();
  Object.entries({ ...scope, tab }).forEach(([k, v]) => { if (v) p.set(k, String(v)); });
  history.replaceState(null, "", `?${p.toString()}`);
}

export default function Root() {
  const { token, role, allowedProjects } = useAuth();
  const { message, modal } = AntApp.useApp();

  const [settings, setSettings] = useState<Settings>(loadSettings);
  const init = readUrl(settings.defaultRange);

  const [scope, setScope] = useState<Scope>(init.scope);
  const [tab, setTab] = useState(init.tab);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState<Record<string, string | null>>({});
  const [busy, setBusy] = useState(false);
  const [auto, setAuto] = useState(false);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchTrace, setSearchTrace] = useState<string | null>(null);
  const [bannerKpi, setBannerKpi] = useState<any>({});

  useEffect(() => writeUrl(scope, tab), [scope, tab]);

  // Guard: only admins can sit on the Admin tab
  useEffect(() => {
    if (tab === "admin" && role && role !== "admin") setTab("overview");
  }, [tab, role]);

  const loadFreshness = useCallback(() => {
    if (token) get("/meta/last-refresh").then(setLastRefresh).catch(() => {});
  }, [token]);
  const refetch = useCallback(() => {
    setBusy(true); setRefreshKey((k) => k + 1); loadFreshness();
    setTimeout(() => setBusy(false), 500);
  }, [loadFreshness]);

  const doRunPipeline = async () => {
    try {
      setPipelineRunning(true);
      const { data } = await api.post("/refresh/pipeline");
      message.info("Goblins dispatched. Pipeline started…");
      const exec = data.execution;
      const poll = async () => {
        try {
          const s = await get("/refresh/status", { execution: exec });
          if (["ACTIVE", "QUEUED", "STATE_UNSPECIFIED"].includes(s.state)) setTimeout(poll, 5000);
          else {
            setPipelineRunning(false); refetch();
            s.state === "SUCCEEDED" ? message.success("Pipeline complete — fresh data served.") : message.warning(`Pipeline ${s.state}`);
          }
        } catch { setPipelineRunning(false); }
      };
      setTimeout(poll, 5000);
    } catch {
      setPipelineRunning(false);
      message.error("Could not trigger pipeline (backend needs workflows.invoker).");
    }
  };

  const runPipeline = () => modal.confirm({
    title: "Run the full pipeline now?",
    content: "This re-pulls traces + metrics and re-merges the gold tables — a few minutes of real BigQuery + Cloud Run compute. It already runs automatically every 10 minutes, so only do this if you truly need the freshest data this second. Don't run it unnecessarily. 🙏",
    okText: "Yes, summon the goblins",
    cancelText: "Never mind",
    onOk: doRunPipeline,
  });

  const saveSettings = (s: Settings) => {
    Object.entries(s).forEach(([k, v]) => localStorage.setItem(k, String(v)));
    setSettings(s);
    setRefreshKey((k) => k + 1);   // re-render so timezone/format changes apply
    message.success("Settings saved");
  };

  useEffect(loadFreshness, [loadFreshness]);
  useEffect(() => {
    if (token) get("/overview", scope as any).then((o) => setBannerKpi(o.kpis || {})).catch(() => {});
  }, [JSON.stringify(scope), refreshKey, token]);
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(refetch, Math.max(15, settings.autoSeconds) * 1000);
    return () => clearInterval(id);
  }, [auto, refetch, settings.autoSeconds]);

  const onSearch = (a: SearchAction) => {
    if (a.type === "trace") setSearchTrace(a.value);
    else if (a.type === "service") { setScope((s) => ({ ...s, service: a.value })); message.success(`Filtered service: ${a.value}`); }
    else if (a.type === "project") setScope((s) => ({ ...s, project: a.value, platform: undefined, service: undefined }));
    else if (a.type === "session") { setTab("sessions"); message.info("Open the session in the Sessions tab"); }
    else message.info(`${a.type}: ${a.value}`);
  };

  if (!token) return <Login />;

  const costBreach = settings.budgetCost > 0 && (bannerKpi.cost_usd || 0) > settings.budgetCost;
  const errBreach = settings.budgetErr > 0 && (bannerKpi.error_rate || 0) * 100 > settings.budgetErr;

  const onScope = (patch: Partial<Scope>) => setScope((s) => ({ ...s, ...patch }));
  const views: Record<string, JSX.Element> = {
    overview: <Overview scope={scope} refreshKey={refreshKey} onScope={onScope} />,
    traces: <Traces scope={scope} refreshKey={refreshKey} />,
    logs: <Logs scope={scope} refreshKey={refreshKey} />,
    metrics: <Metrics scope={scope} refreshKey={refreshKey} onScope={onScope} onNavigate={setTab} />,
    cost: <Cost scope={scope} refreshKey={refreshKey} onScope={onScope} />,
    sessions: <Sessions scope={scope} refreshKey={refreshKey} />,
    tools: <Tools scope={scope} refreshKey={refreshKey} />,
    insights: <Insights scope={scope} refreshKey={refreshKey} onScope={onScope} />,
    health: <Health refreshKey={refreshKey} />,
    compare: <Compare scope={scope} />,
    admin: <Admin />,
  };
  const items = [
    { key: "overview", label: <span data-testid="tab-overview">Overview</span> },
    { key: "traces", label: <span data-testid="tab-traces">Traces</span> },
    { key: "logs", label: <span data-testid="tab-logs">Logs</span> },
    { key: "metrics", label: <span data-testid="tab-metrics">Metrics</span> },
    { key: "cost", label: <span data-testid="tab-cost">LLM Cost</span> },
    { key: "sessions", label: <span data-testid="tab-sessions">Sessions</span> },
    { key: "tools", label: <span data-testid="tab-tools">Tool Calls</span> },
    { key: "insights", label: <span data-testid="tab-insights">Insights</span> },
    { key: "health", label: <span data-testid="tab-health">Health</span> },
    { key: "compare", label: <span data-testid="tab-compare">Compare</span> },
    ...(role === "admin" ? [{ key: "admin", label: <span data-testid="tab-admin">Admin</span> }] : []),
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <AppHeader lastRefresh={lastRefresh} onRefetch={refetch} onRunPipeline={runPipeline}
        busy={busy} autoRefresh={auto} setAutoRefresh={setAuto}
        pipelineRunning={pipelineRunning}
        onOpenSettings={() => setSettingsOpen(true)} onOpenSearch={() => setSearchOpen(true)} />
      <Layout.Content style={{ padding: 16 }}>
        {(costBreach || errBreach) && (
          <Alert type="error" showIcon banner style={{ marginBottom: 8 }}
            message={[
              costBreach ? `Cost $${(bannerKpi.cost_usd || 0).toFixed(4)} > budget $${settings.budgetCost}` : null,
              errBreach ? `Error rate ${((bannerKpi.error_rate || 0) * 100).toFixed(1)}% > ${settings.budgetErr}%` : null,
            ].filter(Boolean).join("   ·   ")} />
        )}
        {role === "user" && allowedProjects.length === 0 && (
          <Alert
            data-testid="no-project-banner"
            type="warning"
            showIcon
            banner
            style={{ marginBottom: 8 }}
            message="No projects assigned to your account. Ask an admin to grant project access."
          />
        )}
        <FilterBar scope={scope} onChange={setScope} />
        <Tabs activeKey={tab} onChange={setTab} items={items} />
        <div style={{ marginTop: 8 }}>{views[tab]}</div>
      </Layout.Content>

      <GlobalSearch open={searchOpen} setOpen={setSearchOpen} onAction={onSearch} />
      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} settings={settings} onSave={saveSettings} />
      <TraceDrawer traceId={searchTrace} open={!!searchTrace} onClose={() => setSearchTrace(null)} />
    </Layout>
  );
}
