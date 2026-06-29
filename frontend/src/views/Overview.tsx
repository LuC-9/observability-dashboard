import { useEffect, useState } from "react";
import { Row, Col, Card, Statistic, Spin, Segmented, Typography } from "antd";
import dayjs from "dayjs";
import { get, Scope } from "../api";
import { BRAND, CHART_COLORS, ERROR_RED } from "../theme";
import ChartCard from "../components/ChartCard";

const usd = (n: any) => (n == null ? "$0" : `$${Number(n).toFixed(4)}`);
const num = (n: any) => (n ?? 0).toLocaleString();

export default function Overview({ scope, refreshKey, onScope }: { scope: Scope; refreshKey: number; onScope: (p: Partial<Scope>) => void }) {
  const [kpi, setKpi] = useState<any>({});
  const [ops, setOps] = useState<any>({});
  const [series, setSeries] = useState<any[]>([]);
  const [lat, setLat] = useState<any[]>([]);
  const [byService, setByService] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState("cost");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      get("/overview", scope as any),
      get("/overview/timeseries", scope as any),
      get("/latency/timeseries", scope as any),
      get("/cost", { ...scope, group_by: "service_name" } as any),
      get("/metrics/summary", scope as any).catch(() => ({})),
    ]).then(([o, ts, lt, cs, ms]) => {
      setKpi(o.kpis || {}); setSeries(ts || []); setLat(lt || []); setByService(cs || []); setOps(ms || {});
    }).finally(() => setLoading(false));
  }, [JSON.stringify(scope), refreshKey]);

  const x = series.map((r) => dayjs(r.bucket).format("MM-DD HH:mm"));
  const lx = lat.map((r) => dayjs(r.bucket).format("MM-DD HH:mm"));
  const totalTokens = (kpi.input_tokens ?? 0) + (kpi.output_tokens ?? 0);
  const avgCost = kpi.traces ? (kpi.cost_usd ?? 0) / kpi.traces : 0;

  const cards: { t: string; v: any; color?: string }[] = [
    { t: "Total cost", v: usd(kpi.cost_usd) }, { t: "Avg cost / trace", v: usd(avgCost) },
    { t: "Traces", v: num(kpi.traces) }, { t: "Spans", v: num(kpi.spans) },
    { t: "Total tokens", v: num(totalTokens) }, { t: "Input tokens", v: num(kpi.input_tokens) },
    { t: "Output tokens", v: num(kpi.output_tokens) }, { t: "Error rate", v: `${((kpi.error_rate ?? 0) * 100).toFixed(2)}%`, color: ERROR_RED },
    { t: "Latency P50", v: `${kpi.p50_ms ?? 0} ms` }, { t: "Latency P95", v: `${kpi.p95_ms ?? 0} ms` },
    { t: "Services", v: num(kpi.services) }, { t: "Projects", v: num(kpi.projects) },
  ];

  // operational (metrics) — distinct from trace/cost KPIs above
  const opsCards: { t: string; v: any; color?: string }[] = [
    { t: "Requests", v: num(ops.total_requests) },
    { t: "Req error rate", v: `${((ops.error_rate ?? 0) * 100).toFixed(2)}%`, color: ERROR_RED },
    { t: "Mean latency", v: `${ops.mean_latency_ms ?? 0} ms` },
    { t: "Peak instances", v: num(ops.peak_instances) },
    { t: "Peak CPU", v: `${ops.peak_cpu_pct ?? 0}%` },
    { t: "Peak memory", v: `${ops.peak_mem_pct ?? 0}%` },
  ];

  const tile = (c: { t: string; v: any; color?: string }) => (
    <Card key={c.t} size="small" style={{ borderTop: `3px solid ${c.color || BRAND.gold}`, height: "100%" }}>
      <Statistic title={c.t} value={c.v as any} valueStyle={{ color: c.color || BRAND.ink, fontSize: 22 }} />
    </Card>
  );
  // fixed 6-column grid -> 12 KPIs render as 6 cols × 2 rows, no stretching/gaps
  const grid6 = { display: "grid", gridTemplateColumns: "repeat(6, minmax(0, 1fr))", gap: 12 } as const;

  const MAIN: Record<string, any> = {
    cost: {
      tooltip: { trigger: "axis" }, legend: {},
      grid: { left: 55, right: 50, top: 40, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: x },
      yAxis: [{ type: "value", name: "USD" }, { type: "value", name: "count" }],
      series: [
        { name: "Cost (USD)", type: "line", smooth: true, itemStyle: { color: BRAND.gold }, lineStyle: { color: BRAND.gold }, data: series.map((r) => r.cost_usd || 0) },
        { name: "Traces", type: "bar", yAxisIndex: 1, itemStyle: { color: BRAND.ink }, data: series.map((r) => r.traces || 0) },
        { name: "Errors", type: "line", yAxisIndex: 1, itemStyle: { color: ERROR_RED }, lineStyle: { color: ERROR_RED, width: 2 }, data: series.map((r) => r.errors || 0) },
      ],
    },
    latency: {
      tooltip: { trigger: "axis" }, legend: {},
      grid: { left: 55, right: 20, top: 40, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: lx }, yAxis: { type: "value", name: "ms" },
      series: [
        { name: "P50", type: "line", smooth: true, itemStyle: { color: BRAND.gold }, lineStyle: { color: BRAND.gold }, data: lat.map((r) => r.p50_ms || 0) },
        { name: "P95", type: "line", smooth: true, itemStyle: { color: BRAND.ink }, lineStyle: { color: BRAND.ink }, data: lat.map((r) => r.p95_ms || 0) },
      ],
    },
    tokens: {
      tooltip: { trigger: "axis" }, legend: {}, color: CHART_COLORS,
      grid: { left: 60, right: 20, top: 40, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: x }, yAxis: { type: "value" },
      series: [
        { name: "Input", type: "line", areaStyle: {}, stack: "t", data: series.map((r) => r.input_tokens || 0) },
        { name: "Output", type: "line", areaStyle: {}, stack: "t", data: series.map((r) => r.output_tokens || 0) },
      ],
    },
    requests: {
      tooltip: { trigger: "axis" },
      grid: { left: 45, right: 20, top: 30, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: x }, yAxis: { type: "value", name: "traces" },
      series: [{ name: "Traces", type: "bar", itemStyle: { color: BRAND.gold }, data: series.map((r) => r.traces || 0) }],
    },
  };

  const svc = byService.slice(0, 10);
  const svcOpt = {
    color: [BRAND.gold], tooltip: { trigger: "axis", valueFormatter: (v: any) => `$${Number(v).toFixed(5)}` },
    grid: { left: 8, right: 20, top: 10, bottom: 8, containLabel: true },
    xAxis: { type: "value", name: "USD" },
    yAxis: { type: "category", inverse: true, data: svc.map((r) => r.key || "—"), axisLabel: { width: 140, overflow: "truncate" } },
    series: [{ type: "bar", data: svc.map((r) => r.cost_usd || 0) }],
  };

  return (
    <Spin spinning={loading}>
      {/* GenAI / cost KPIs — 6 columns × 2 rows */}
      <div style={grid6}>{cards.map(tile)}</div>

      {/* operational metrics — 6 columns × 1 row */}
      <Typography.Text type="secondary" style={{ display: "block", margin: "14px 0 6px" }}>
        Infrastructure / operational metrics
      </Typography.Text>
      <div style={grid6}>{opsCards.map(tile)}</div>

      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col xs={24} lg={14}>
          <ChartCard title="Trends" option={MAIN[view]} height={320}
            extra={<Segmented size="small" value={view} onChange={(v) => setView(v as string)}
              options={[{ label: "Cost & Errors", value: "cost" }, { label: "Latency P50/P95", value: "latency" },
                        { label: "Tokens", value: "tokens" }, { label: "Requests", value: "requests" }]} />} />
        </Col>
        <Col xs={24} lg={10}>
          <ChartCard title="LLM cost by service (top 10)" option={svcOpt} height={320}
            onPick={(p: any) => { const r = svc[p.dataIndex]; return r ? {
              title: "Service", items: [
                { label: "Service", value: String(r.key ?? "—"), copyable: true },
                { label: "Cost", value: `$${Number(r.cost_usd || 0).toFixed(6)}` },
                { label: "Input tokens", value: String(r.input_tokens ?? "—") },
                { label: "Output tokens", value: String(r.output_tokens ?? "—") },
                { label: "Traces", value: String(r.traces ?? "—") }],
              action: { label: `Filter service: ${r.key}`, run: () => onScope({ service: String(r.key) }) } } : null; }} />
        </Col>
      </Row>
    </Spin>
  );
}
