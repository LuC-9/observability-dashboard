import type { OverviewStats } from "../types";

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi-card">
      <div className="kpi-lbl">{label}</div>
      <div className="kpi-val">{value}</div>
    </div>
  );
}

const fmt = (n: number) => n.toLocaleString();

export default function KpiRow({ stats }: { stats: OverviewStats }) {
  const errPct = stats.total_spans
    ? Math.round((stats.error_spans / stats.total_spans) * 1000) / 10
    : 0;
  return (
    <div className="kpi-row">
      <Card label="Total Spans"    value={fmt(stats.total_spans)} />
      <Card label="Total Logs"     value={fmt(stats.total_logs)} />
      <Card label="Error Spans"    value={`${fmt(stats.error_spans)} (${errPct}%)`} />
      <Card label="Avg Latency"    value={`${stats.avg_duration_ms.toFixed(1)} ms`} />
      <Card label="Total LLM Cost" value={`$${stats.total_cost_usd.toFixed(4)}`} />
      <Card label="Input Tokens"   value={fmt(stats.total_input_tokens)} />
      <Card label="Output Tokens"  value={fmt(stats.total_output_tokens)} />
    </div>
  );
}
