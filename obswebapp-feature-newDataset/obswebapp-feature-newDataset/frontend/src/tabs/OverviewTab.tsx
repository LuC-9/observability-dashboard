import { useEffect, useState } from "react";
import KpiRow from "../components/KpiCard";
import PlotlyChart from "../components/PlotlyChart";
import { api } from "../api";
import type { OverviewResponse, SharedFilters } from "../types";

function ChartPanel({ title, badge, children }: { title: string; badge?: string; children: React.ReactNode }) {
  return (
    <div className="chart-panel">
      <div className="chart-panel-header">
        <span className="chart-panel-title">{title}</span>
        {badge && <span className="chart-panel-badge">{badge}</span>}
      </div>
      {children}
    </div>
  );
}

export default function OverviewTab({ filters }: { filters: SharedFilters }) {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    setLoading(true); setErr("");
    try {
      setData(await api.overview(filters));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filters]);

  const rangeLabel = filters.quick !== "Custom" ? filters.quick : `${filters.start} → ${filters.end}`;

  return (
    <div>
      {loading && <div style={{ color: "#6b7280", marginBottom: 12 }}>Loading…</div>}
      {err && <div className="status-error" style={{ marginTop: 12 }}>{err}</div>}

      {data && (
        <>
          <div style={{ marginTop: 16 }}>
            <KpiRow stats={data.stats} />
          </div>

          <div className="responsive-grid" style={{ marginTop: 4 }}>
            <ChartPanel title="LLM Cost Over Time" badge={rangeLabel}>
              <PlotlyChart fig={data.charts.cost} />
            </ChartPanel>
            <ChartPanel title="Avg Latency Over Time" badge={rangeLabel}>
              <PlotlyChart fig={data.charts.latency} />
            </ChartPanel>
            <ChartPanel title="Token Usage Over Time" badge={rangeLabel}>
              <PlotlyChart fig={data.charts.tokens} />
            </ChartPanel>
            <ChartPanel title="Error Rate Over Time" badge={rangeLabel}>
              <PlotlyChart fig={data.charts.errors} />
            </ChartPanel>
          </div>
        </>
      )}
    </div>
  );
}
