import { useEffect, useState } from "react";
import { Card, Row, Col, Segmented } from "antd";
import { get, Scope } from "../api";
import { BRAND, CHART_COLORS, ERROR_RED } from "../theme";
import GenericTable from "../components/GenericTable";
import TraceDrawer from "../components/TraceDrawer";
import ChartCard from "../components/ChartCard";

export default function Insights({ scope, refreshKey, onScope }: { scope: Scope; refreshKey: number; onScope: (p: Partial<Scope>) => void }) {
  const [by, setBy] = useState("cost");
  const [top, setTop] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [errSvc, setErrSvc] = useState<any[]>([]);
  const [errTop, setErrTop] = useState<any[]>([]);
  const [traceId, setTraceId] = useState<string | null>(null);

  useEffect(() => { get("/top/traces", { ...scope, by } as any).then(setTop); }, [JSON.stringify(scope), by, refreshKey]);
  useEffect(() => {
    get("/models", scope as any).then(setModels);
    get("/errors/by-service", scope as any).then(setErrSvc);
    get("/errors/top", scope as any).then(setErrTop);
  }, [JSON.stringify(scope), refreshKey]);

  const m = models.slice(0, 10);
  const modelOpt = {
    color: CHART_COLORS, tooltip: { trigger: "axis" }, legend: { data: ["Cost (USD)", "Tokens"] },
    grid: { left: 8, right: 50, top: 40, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: m.map((r) => r.model), axisLabel: { rotate: 25, width: 90, overflow: "truncate" } },
    yAxis: [{ type: "value", name: "USD" }, { type: "value", name: "tokens" }],
    series: [
      { name: "Cost (USD)", type: "bar", itemStyle: { color: BRAND.gold }, data: m.map((r) => r.cost_usd || 0) },
      { name: "Tokens", type: "line", yAxisIndex: 1, itemStyle: { color: BRAND.ink }, data: m.map((r) => (r.input_tokens || 0) + (r.output_tokens || 0)) },
    ],
  };
  const es = errSvc.slice(0, 12);
  const errOpt = {
    color: [ERROR_RED], tooltip: { trigger: "axis" },
    grid: { left: 8, right: 20, top: 10, bottom: 8, containLabel: true },
    xAxis: { type: "value", name: "errors" },
    yAxis: { type: "category", inverse: true, data: es.map((r) => r.service_name || "—"), axisLabel: { width: 130, overflow: "truncate" } },
    series: [{ type: "bar", data: es.map((r) => r.errors || 0) }],
  };

  const modelDetail = (p: any) => {
    const r = m[p.dataIndex]; if (!r) return null;
    return { title: "Model", items: [
      { label: "Model", value: String(r.model ?? "—"), copyable: true },
      { label: "Calls", value: String(r.calls ?? "—") },
      { label: "Traces", value: String(r.traces ?? "—") },
      { label: "Input tokens", value: String(r.input_tokens ?? "—") },
      { label: "Output tokens", value: String(r.output_tokens ?? "—") },
      { label: "Cost", value: `$${Number(r.cost_usd || 0).toFixed(6)}` }] };
  };
  const errDetail = (p: any) => {
    const r = es[p.dataIndex]; if (!r) return null;
    return { title: "Service errors", items: [
      { label: "Service", value: String(r.service_name ?? "—"), copyable: true },
      { label: "Errors", value: String(r.errors ?? "—") },
      { label: "Spans", value: String(r.spans ?? "—") },
      { label: "Error rate", value: `${((r.error_rate || 0) * 100).toFixed(2)}%` }],
      action: { label: `Filter service: ${r.service_name}`, run: () => onScope({ service: r.service_name }) } };
  };

  return (
    <>
      <Card size="small" style={{ marginBottom: 12 }} title="Top traces"
        extra={<Segmented size="small" value={by} onChange={(v) => setBy(v as string)}
          options={[{ label: "Most expensive", value: "cost" }, { label: "Slowest", value: "latency" }, { label: "Most tokens", value: "tokens" }]} />}>
        <GenericTable rows={top} onRowClick={(r) => setTraceId(r.trace_id)} exportName={`top_${by}`} />
      </Card>

      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} lg={12}><ChartCard title="Model breakdown (cost & tokens)" option={modelOpt} height={300} onPick={modelDetail} /></Col>
        <Col xs={24} lg={12}><ChartCard title="Errors by service" option={errOpt} height={300} onPick={errDetail} /></Col>
      </Row>

      <Card size="small" title="Top error messages (from logs)">
        <GenericTable rows={errTop} exportName="top_errors" />
      </Card>

      <TraceDrawer traceId={traceId} open={!!traceId} onClose={() => setTraceId(null)} />
    </>
  );
}
