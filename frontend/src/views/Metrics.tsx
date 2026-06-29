import { useEffect, useMemo, useState } from "react";
import { Row, Col, Card, Statistic, Select, Cascader, Space, Alert, Spin, Segmented, Typography, Tooltip } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { get, Scope } from "../api";
import { BRAND, CHART_COLORS, ERROR_RED } from "../theme";
import ChartCard from "../components/ChartCard";
import GenericTable from "../components/GenericTable";

const num = (n: any) => (n == null ? "—" : Number(n).toLocaleString());
const CLASS_COLOR: Record<string, string> = { "2xx": BRAND.gold, "3xx": "#8a8a8a", "4xx": "#E08E0B", "5xx": ERROR_RED };
const READY_COLOR: Record<string, string> = { HEALTHY: BRAND.gold, UNHEALTHY: ERROR_RED, UNKNOWN: "#9aa0a6" };
const STATE_COLOR: Record<string, string> = { active: BRAND.gold, idle: "#9aa0a6" };

const INST = "run.googleapis.com/container/instance_count";
const READY = "run.googleapis.com/container/instance_count_with_readiness";
const CPU_UTIL = "run.googleapis.com/container/cpu/utilizations";
const MEM_UTIL = "run.googleapis.com/container/memory/utilizations";
const MAX_SERIES = 10;

type TSRow = { bucket: string; k: string; v: number };

const aggFor = (mt: string) => (/count|bytes/i.test(mt) ? "sum" : "avg");
const scaleFor = (mt: string) => (/utilizations/i.test(mt) ? 100 : 1);
const unitFor = (mt: string) =>
  /utilizations/i.test(mt) ? "%" : /bytes/i.test(mt) ? "bytes" : /latenc/i.test(mt) ? "ms" :
  /instance|count/i.test(mt) ? "count" : "value";

// build nested Cascader options from "run.googleapis.com/container/cpu/utilizations" paths
function buildTree(types: string[] = []) {
  const root: any = {};
  for (const t of types) { let n = root; for (const p of t.split("/")) { n[p] = n[p] || {}; n = n[p]; } }
  const toOpts = (obj: any): any[] =>
    Object.keys(obj).sort().map((label) => {
      const children = toOpts(obj[label]);
      return children.length ? { value: label, label, children } : { value: label, label };
    });
  return toOpts(root);
}

function pivot(rows: TSRow[], scale = 1) {
  const buckets = [...new Set(rows.map((r) => r.bucket))].sort();
  const keys = [...new Set(rows.map((r) => r.k))];
  const bi = new Map(buckets.map((b, i) => [b, i]));
  const series = keys.map((k) => ({ key: k, data: buckets.map(() => 0 as number) }));
  rows.forEach((r) => { const s = series.find((x) => x.key === r.k)!; s.data[bi.get(r.bucket)!] = (r.v || 0) * scale; });
  return { x: buckets.map((b) => dayjs(b).format("MM-DD HH:mm")), series };
}

function lineOpt(rows: TSRow[], yName: string, opts: {
  type?: "line" | "bar"; stack?: boolean; scale?: number; maxSeries?: number; colorFn?: (k: string) => string | undefined;
} = {}) {
  const { type = "line", stack = false, scale = 1, maxSeries, colorFn } = opts;
  let { x, series } = pivot(rows, scale);
  if (maxSeries && series.length > maxSeries) {
    series = [...series].sort((a, b) =>
      b.data.reduce((s, v) => s + v, 0) - a.data.reduce((s, v) => s + v, 0)).slice(0, maxSeries);
  }
  return {
    tooltip: { trigger: "axis" }, legend: { type: "scroll" }, color: CHART_COLORS,
    grid: { left: 58, right: 22, top: 42, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: x },
    yAxis: { type: "value", name: yName, nameGap: 16 },
    series: series.map((s) => {
      const c = colorFn?.(s.key);
      return {
        name: s.key, type, smooth: type === "line",
        stack: stack ? "t" : undefined, areaStyle: stack ? {} : undefined,
        itemStyle: c ? { color: c } : undefined, lineStyle: c ? { color: c } : undefined,
        data: s.data,
      };
    }),
  };
}

export default function Metrics({ scope, refreshKey, onScope, onNavigate }: {
  scope: Scope; refreshKey: number; onScope: (p: Partial<Scope>) => void; onNavigate: (tab: string) => void;
}) {
  const [cat, setCat] = useState("all");
  const [mtype, setMtype] = useState<string | undefined>();      // full metric_type (Cascader leaf)
  const [svcSel, setSvcSel] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<any>({});
  const [sum, setSum] = useState<any>({});
  const [ts, setTs] = useState<Record<string, TSRow[]>>({});
  const [table, setTable] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // metrics-local service filter overrides the global one when set
  const svc = svcSel.length ? svcSel.join(",") : scope.service;
  const base = useMemo(() => ({ ...scope, service: svc }), [JSON.stringify(scope), svc]);

  const tree = useMemo(() => buildTree(catalog.metric_types), [catalog.metric_types]);

  useEffect(() => { get("/metrics/catalog", scope as any).then(setCatalog).catch(() => {}); },
    [JSON.stringify(scope), refreshKey]);

  useEffect(() => {
    setLoading(true); setErr(null);
    const want: [string, any][] = [];
    if (mtype) {
      want.push(["metric", { metric_type: mtype, group: "service_name", agg: aggFor(mtype) }]);
    } else {
      const all = cat === "all";
      if (all || cat === "requests") want.push(["req", { category: "requests", group: "response_code_class", agg: "sum" }]);
      if (all || cat === "latency") want.push(["lat", { category: "latency", group: all ? "none" : "metric_type", agg: "avg" }]);
      if (cat === "instances") {
        want.push(["inst", { metric_type: INST, group: "state", agg: "avg" }]);
        want.push(["ready", { metric_type: READY, group: "readiness_status", agg: "avg" }]);
      }
      if (cat === "cpu") want.push(["cpu", { metric_type: CPU_UTIL, group: "service_name", agg: "avg" }]);
      if (cat === "memory") want.push(["mem", { metric_type: MEM_UTIL, group: "service_name", agg: "avg" }]);
      if (cat === "network") want.push(["net", { category: "network", group: "service_name", agg: "sum" }]);
    }

    Promise.all([
      get("/metrics/summary", base as any).then(setSum).catch(() => setSum({})),
      get("/metrics", { ...base, category: cat === "all" ? undefined : cat, metric_type: mtype, limit: 500 } as any)
        .then(setTable).catch(() => setTable([])),
      ...want.map(([k, params]) =>
        get("/metrics/timeseries", { ...base, ...params } as any)
          .then((r) => [k, r] as [string, TSRow[]]).catch(() => [k, [] as TSRow[]] as [string, TSRow[]])),
    ]).then((res) => setTs(Object.fromEntries(res.slice(2) as [string, TSRow[]][])))
      .catch((e) => setErr(e?.response?.data?.detail || "metrics unavailable"))
      .finally(() => setLoading(false));
  }, [JSON.stringify(base), cat, mtype, refreshKey]);

  const opt = (s: string[] | undefined) => (s || []).map((v) => ({ value: v, label: v }));
  const jumpTraces = (label: string) => ({ label, run: () => onNavigate("traces") });
  const jumpLogs = (label: string) => ({ label, run: () => onNavigate("logs") });

  const cards = [
    { t: "Total requests", v: num(sum.total_requests) },
    { t: "Error rate", v: `${((sum.error_rate ?? 0) * 100).toFixed(2)}%`, color: ERROR_RED },
    { t: "Mean latency", v: `${sum.mean_latency_ms ?? 0} ms` },
    { t: "Peak instances", v: num(sum.peak_instances) },
    { t: "Peak CPU", v: `${sum.peak_cpu_pct ?? 0}%` },
    { t: "Peak memory", v: `${sum.peak_mem_pct ?? 0}%` },
    { t: "Services", v: num(sum.services) },
  ];

  if (err) return <Alert type="error" showIcon message="gold.metrics not available" description={err} />;

  return (
    <Spin spinning={loading}>
      {/* KPI tiles — flex so no trailing gap */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
        {cards.map((c) => (
          <Card key={c.t} size="small" style={{ flex: "1 1 150px", borderTop: `3px solid ${c.color || BRAND.gold}` }}>
            <Statistic title={c.t} value={c.v as any} valueStyle={{ color: c.color || BRAND.ink, fontSize: 22 }} />
          </Card>
        ))}
      </div>

      {/* filters */}
      <Space wrap style={{ marginBottom: 12 }}>
        <Segmented value={cat} disabled={!!mtype} onChange={(v) => setCat(v as string)}
          options={[
            { label: "Overview", value: "all" }, { label: "Requests", value: "requests" },
            { label: "Latency", value: "latency" }, { label: "Instances", value: "instances" },
            { label: "CPU", value: "cpu" }, { label: "Memory", value: "memory" },
            { label: "Network", value: "network" },
          ]} />
        <Cascader options={tree} value={mtype ? mtype.split("/") : undefined} allowClear showSearch
          changeOnSelect={false} placeholder="Metric name (nested)" style={{ width: 340 }}
          onChange={(v: any) => setMtype(v?.length ? v.join("/") : undefined)} />
        <Select mode="multiple" allowClear placeholder="Services (default: all, top 10 shown)" maxTagCount="responsive"
          style={{ minWidth: 280 }} value={svcSel} onChange={setSvcSel} options={opt(catalog.services)} />
        <Tooltip title="Pick a specific metric to chart it by service. Clears the category view.">
          <InfoCircleOutlined style={{ color: "#9aa0a6" }} />
        </Tooltip>
      </Space>

      <Row gutter={[12, 12]}>
        {mtype ? (
          <Col xs={24}>
            <ChartCard title={`${mtype.split("/").slice(-2).join(" / ")} — by service`} height={340}
              option={lineOpt(ts.metric || [], unitFor(mtype),
                { type: aggFor(mtype) === "sum" ? "bar" : "line", scale: scaleFor(mtype), maxSeries: MAX_SERIES })}
              onPick={(p: any) => ({ title: "Service", items: [
                { label: "Service", value: String(p.seriesName), copyable: true }],
                action: { label: `Filter service: ${p.seriesName}`, run: () => onScope({ service: String(p.seriesName) }) } })} />
          </Col>
        ) : <>
          {(cat === "all" || cat === "requests") && (
            <Col xs={24} lg={cat === "all" ? 12 : 24}>
              <ChartCard title="Request throughput by response class" height={300}
                option={lineOpt(ts.req || [], "requests", { type: "bar", stack: true, colorFn: (k) => CLASS_COLOR[k] })}
                onPick={(p: any) => ({ title: "Response class", items: [
                  { label: "Class", value: String(p.seriesName) }, { label: "Requests", value: String(p.value) }],
                  action: String(p.seriesName).match(/4xx|5xx/) ? jumpLogs("View error logs for this window") : undefined })} />
            </Col>
          )}
          {(cat === "all" || cat === "latency") && (
            <Col xs={24} lg={cat === "all" ? 12 : 24}>
              <ChartCard title={cat === "all" ? "Mean request latency" : "Mean latency by metric"} height={300}
                option={lineOpt(ts.lat || [], "ms", { maxSeries: MAX_SERIES })}
                onPick={() => ({ title: "Latency", items: [{ label: "Note", value: "Distribution mean. True P50/P95 is in the Traces tab." }],
                  action: jumpTraces("Open Traces for P50/P95") })} />
            </Col>
          )}
          {cat === "instances" && <>
            <Col xs={24} lg={12}>
              <ChartCard title="Instances (active vs idle)" height={300}
                option={lineOpt(ts.inst || [], "instances", { type: "line", stack: true, colorFn: (k) => STATE_COLOR[k] })} />
            </Col>
            <Col xs={24} lg={12}>
              <ChartCard title="Instance readiness" height={300}
                option={lineOpt(ts.ready || [], "instances", { type: "line", stack: true, colorFn: (k) => READY_COLOR[k] })}
                onPick={(p: any) => ({ title: "Readiness", items: [{ label: "Status", value: String(p.seriesName) }],
                  action: String(p.seriesName) === "UNHEALTHY" ? jumpLogs("View logs for this window") : undefined })} />
            </Col>
          </>}
          {cat === "cpu" && (
            <Col xs={24}><ChartCard title="CPU utilization (%) by service" height={320}
              option={lineOpt(ts.cpu || [], "%", { scale: 100, maxSeries: MAX_SERIES })} /></Col>
          )}
          {cat === "memory" && (
            <Col xs={24}><ChartCard title="Memory utilization (%) by service" height={320}
              option={lineOpt(ts.mem || [], "%", { scale: 100, maxSeries: MAX_SERIES })} /></Col>
          )}
          {cat === "network" && (
            <Col xs={24}><ChartCard title="Network bytes by service" height={320}
              option={lineOpt(ts.net || [], "bytes", { type: "bar", stack: true, maxSeries: MAX_SERIES })} /></Col>
          )}
        </>}
      </Row>

      <Typography.Title level={5} style={{ marginTop: 16 }}>Raw metric points</Typography.Title>
      <GenericTable rows={table} loading={loading} exportName="metrics"
        onRowClick={(r) => { if (r.service_name) onScope({ service: String(r.service_name) }); }} />
    </Spin>
  );
}
