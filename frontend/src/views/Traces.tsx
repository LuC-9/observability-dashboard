import { useEffect, useState } from "react";
import { Row, Col } from "antd";
import dayjs from "dayjs";
import { get, Scope } from "../api";
import { BRAND } from "../theme";
import GenericTable from "../components/GenericTable";
import TraceDrawer from "../components/TraceDrawer";
import ChartCard from "../components/ChartCard";

export default function Traces({ scope, refreshKey }: { scope: Scope; refreshKey: number }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  useEffect(() => setPage(1), [JSON.stringify(scope)]);
  useEffect(() => {
    setLoading(true);
    get("/traces", { ...scope, page, page_size: pageSize } as any)
      .then((res) => { setRows(res.rows || []); setTotal(res.total || 0); })
      .finally(() => setLoading(false));
  }, [JSON.stringify(scope), page, pageSize, refreshKey]);

  const durs = rows.map((r) => r.duration_ms || 0).filter((d) => d > 0);
  const max = Math.max(1, ...durs);
  const nb = 10, w = max / nb;
  const hist = Array.from({ length: nb }, (_, i) => ({
    label: `${Math.round(i * w)}–${Math.round((i + 1) * w)}`,
    count: durs.filter((d) => d >= i * w && d < (i + 1) * w).length,
  }));
  const histOpt = {
    color: [BRAND.gold], tooltip: { trigger: "axis" },
    grid: { left: 8, right: 16, top: 34, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: hist.map((h) => h.label), name: "ms", nameGap: 28,
             axisLabel: { rotate: 35, fontSize: 10, hideOverlap: true } },
    yAxis: { type: "value", name: "traces", nameGap: 12 },
    series: [{ type: "bar", data: hist.map((h) => h.count) }],
  };
  const byBucket: Record<string, number> = {};
  rows.forEach((r) => { const k = dayjs(r.start_time).format("MM-DD HH:mm"); byBucket[k] = (byBucket[k] || 0) + 1; });
  const bk = Object.keys(byBucket).sort();
  const volOpt = {
    color: [BRAND.ink], tooltip: { trigger: "axis" },
    grid: { left: 8, right: 16, top: 34, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: bk, axisLabel: { rotate: 35, fontSize: 10, hideOverlap: true } },
    yAxis: { type: "value", name: "traces", nameGap: 12 },
    series: [{ type: "bar", data: bk.map((k) => byBucket[k]) }],
  };
  const scatter = rows.filter((r) => r.cost_usd).map((r) => [r.duration_ms || 0, r.cost_usd || 0, r.trace_id, r.service_name]);
  const scatterOpt = {
    color: [BRAND.gold], tooltip: { trigger: "item", formatter: (p: any) => `${Math.round(p.value[0])}ms · $${Number(p.value[1]).toFixed(5)}` },
    grid: { left: 8, right: 16, top: 34, bottom: 8, containLabel: true },
    xAxis: { type: "value", name: "latency ms", nameGap: 26 },
    yAxis: { type: "value", name: "cost USD", nameGap: 40 },
    series: [{ type: "scatter", symbolSize: 8, data: scatter }],
  };

  return (
    <>
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} lg={8}><ChartCard title="Latency distribution" option={histOpt} height={240}
          onPick={(p: any) => ({ title: "Latency bucket", items: [
            { label: "Range (ms)", value: hist[p.dataIndex]?.label || "—" },
            { label: "Traces", value: String(hist[p.dataIndex]?.count ?? 0) }] })} /></Col>
        <Col xs={24} lg={8}><ChartCard title="Traces over time" option={volOpt} height={240}
          onPick={(p: any) => ({ title: "Time bucket", items: [
            { label: "Bucket", value: p.name }, { label: "Traces", value: String(p.value) }] })} /></Col>
        <Col xs={24} lg={8}><ChartCard title="Cost vs latency" option={scatterOpt} height={240}
          onPick={(p: any) => ({ title: "Trace", items: [
            { label: "Trace id", value: String(p.value[2]), copyable: true },
            { label: "Service", value: String(p.value[3] || "—") },
            { label: "Latency", value: `${Math.round(p.value[0])} ms` },
            { label: "Cost", value: `$${Number(p.value[1]).toFixed(6)}` }],
            action: { label: "Open trace", run: () => setTraceId(p.value[2]) } })} /></Col>
      </Row>
      <GenericTable rows={rows} loading={loading} onRowClick={(r) => setTraceId(r.trace_id)} exportName="traces"
        total={total} page={page} pageSize={pageSize}
        onPageChange={(p, ps) => { setPage(p); setPageSize(ps); }} />
      <TraceDrawer traceId={traceId} open={!!traceId} onClose={() => setTraceId(null)} />
    </>
  );
}
