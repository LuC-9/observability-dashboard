import { useEffect, useState } from "react";
import PlotlyChart from "../components/PlotlyChart";
import { api } from "../api";
import type { FilterOptions, MetricsResponse, SharedFilters } from "../types";

export default function MetricsTab({ filters, options }: { filters: SharedFilters; options: FilterOptions }) {
  const [metricName, setMetricName] = useState("All");
  const [agent, setAgent]           = useState("All");
  const [data, setData]             = useState<MetricsResponse | null>(null);
  const [loading, setLoading]       = useState(false);
  const [err, setErr]               = useState("");

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.metrics({ ...filters, agent, metric_name: metricName }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters, agent, metricName]);

  const metricNames = ["All", ...options.metric_names];
  const agents      = ["All", ...options.agents];

  return (
    <div>
      <div className="tab-filters">
        <div style={{ flex: 1, minWidth: 180 }}>
          <label className="field-label">Metric Name</label>
          <select className="field-select" value={metricName} onChange={(e) => setMetricName(e.target.value)}>
            {metricNames.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <label className="field-label">Agent</label>
          <select className="field-select" value={agent} onChange={(e) => setAgent(e.target.value)}>
            {agents.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        {loading && <div style={{ color: "#6b7280", fontSize: 12, alignSelf: "center" }}>Loading…</div>}
      </div>

      {err && <div className="status-error" style={{ marginBottom: 12 }}>{err}</div>}

      {data && data.metric_charts.length === 0 && (
        <div className="status-warn" style={{ marginBottom: 12 }}>
          No metrics data found for this time range or filter combination.
        </div>
      )}

      {data && data.metric_charts.length > 0 && (
        <>
          <div className="section-h">Metrics Over Time</div>
          <div className="responsive-grid" style={{ marginBottom: 16 }}>
            {data.metric_charts.map((fig, i) => (
              <div key={i} className="chart-panel">
                <PlotlyChart fig={fig} />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

