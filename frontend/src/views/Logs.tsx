import { useEffect, useMemo, useState } from "react";
import { Space, Select, Input, Switch, Row, Col, Alert, Typography } from "antd";
import { get, Scope } from "../api";
import GenericTable from "../components/GenericTable";
import ChartCard from "../components/ChartCard";
import TraceDrawer from "../components/TraceDrawer";
import { App } from "antd";

const SEV = ["INFO", "WARN", "ERROR", "FATAL", "DEBUG", "NOTICE", "UNSPECIFIED"].map((s) => ({ value: s, label: s }));
const SEV_COLOR: Record<string, string> = { ERROR: "#C0392B", FATAL: "#7B241C", WARN: "#B6862C", INFO: "#3D3D3D", UNSPECIFIED: "#9aa0a6" };

export default function Logs({ scope, refreshKey }: { scope: Scope; refreshKey: number }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [sev, setSev] = useState<string | undefined>();
  const [q, setQ] = useState("");
  const [withTrace, setWithTrace] = useState(false);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const { message } = App.useApp();

  useEffect(() => setPage(1), [JSON.stringify(scope), sev]);
  useEffect(() => {
    setLoading(true);
    get("/logs", { ...scope, severity: sev, page, page_size: pageSize } as any)
      .then((res) => { setRows(res.rows || []); setTotal(res.total || 0); })
      .finally(() => setLoading(false));
  }, [JSON.stringify(scope), sev, page, pageSize, refreshKey]);

  const filtered = useMemo(() => {
    let r = rows;
    if (q) r = r.filter((x) => JSON.stringify(x).toLowerCase().includes(q.toLowerCase()));
    if (withTrace) r = r.filter((x) => x.trace_id);
    return r;
  }, [rows, q, withTrace]);

  // severity breakdown (client-side)
  const counts: Record<string, number> = {};
  rows.forEach((r) => { const s = r.severity || "UNSPECIFIED"; counts[s] = (counts[s] || 0) + 1; });
  const sevOpt = {
    tooltip: { trigger: "item" },
    series: [{
      type: "pie", radius: ["45%", "70%"],
      data: Object.entries(counts).map(([k, v]) => ({ name: k, value: v, itemStyle: { color: SEV_COLOR[k] || "#888" } })),
    }],
  };
  const tracePct = rows.length ? Math.round((rows.filter((r) => r.trace_id).length / rows.length) * 100) : 0;

  return (
    <>
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} md={10}><ChartCard title="Severity breakdown" option={sevOpt} height={220}
          onPick={(p: any) => ({ title: "Severity", items: [
            { label: "Severity", value: String(p.name) }, { label: "Logs", value: String(p.value) }],
            action: { label: `Filter severity: ${p.name}`, run: () => setSev(p.name) } })} /></Col>
        <Col xs={24} md={14}>
          <Alert type="info" showIcon style={{ marginBottom: 12 }}
            message="About trace_id / span_id in logs"
            description={`Only request-scoped logs carry a trace (Cloud Run request logs + ADK structured gen_ai logs). Agent Engine stdout/stderr and uvicorn lines have no trace — those columns are empty for them. In this view ${tracePct}% of logs have a trace_id.`} />
          <Typography.Text type="secondary">Tip: toggle "Has trace only" to see correlatable logs.</Typography.Text>
        </Col>
      </Row>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select allowClear placeholder="Severity" style={{ width: 160 }} options={SEV} value={sev} onChange={setSev} />
        <Input.Search allowClear placeholder="Search message / trace_id / span_id" style={{ width: 340 }}
          onChange={(e) => setQ(e.target.value)} />
        <Space size={4}><span>Has trace only</span><Switch size="small" checked={withTrace} onChange={setWithTrace} /></Space>
      </Space>
      <GenericTable rows={filtered} loading={loading} exportName="logs"
        total={total} page={page} pageSize={pageSize}
        onPageChange={(p, ps) => { setPage(p); setPageSize(ps); }}
        onRowClick={(r) => (r.trace_id ? setTraceId(r.trace_id) : message.info("This log line has no trace_id"))} />
      <TraceDrawer traceId={traceId} open={!!traceId} onClose={() => setTraceId(null)} />
    </>
  );
}
