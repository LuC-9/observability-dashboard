import { useEffect, useState } from "react";
import { Drawer, Spin, Typography, Row, Col } from "antd";
import { get, Scope } from "../api";
import { BRAND } from "../theme";
import GenericTable from "../components/GenericTable";
import TraceDrawer from "../components/TraceDrawer";
import ChartCard from "../components/ChartCard";

const sid = (c: any) => String(c ?? "—");

export default function Sessions({ scope, refreshKey }: { scope: Scope; refreshKey: number }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [cid, setCid] = useState<string | null>(null);
  const [sessRows, setSessRows] = useState<any[]>([]);
  const [sessLoading, setSessLoading] = useState(false);
  const [traceId, setTraceId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    get("/sessions", scope as any).then(setRows).finally(() => setLoading(false));
  }, [JSON.stringify(scope), refreshKey]);

  const openSession = (r: any) => {
    setCid(r.conversation_id); setSessLoading(true);
    get(`/sessions/${encodeURIComponent(r.conversation_id)}`).then(setSessRows).finally(() => setSessLoading(false));
  };

  // keep FULL ids in the data; truncate only the displayed axis label (overflow), so tooltip/click get the full value
  const catAxis = (data: string[]) => ({ type: "category", data, inverse: true, axisLabel: { width: 110, overflow: "truncate" } });

  const topCost = [...rows].sort((a, b) => (b.cost_usd || 0) - (a.cost_usd || 0)).slice(0, 10);
  const costOpt = {
    color: [BRAND.gold], tooltip: { trigger: "axis", valueFormatter: (v: any) => `$${Number(v).toFixed(5)}` },
    grid: { left: 8, right: 20, top: 10, bottom: 8, containLabel: true },
    xAxis: { type: "value", name: "USD" },
    yAxis: catAxis(topCost.map((r) => sid(r.conversation_id))),
    series: [{ type: "bar", data: topCost.map((r) => r.cost_usd || 0) }],
  };
  const topTok = [...rows].sort((a, b) => (b.tokens || 0) - (a.tokens || 0)).slice(0, 10);
  const tokOpt = {
    color: [BRAND.goldSoft], tooltip: { trigger: "axis" },
    grid: { left: 8, right: 20, top: 10, bottom: 8, containLabel: true },
    xAxis: { type: "value", name: "tokens" },
    yAxis: catAxis(topTok.map((r) => sid(r.conversation_id))),
    series: [{ type: "bar", data: topTok.map((r) => r.tokens || 0) }],
  };
  const turns = rows.map((r) => r.turns || 0);
  const maxT = Math.max(1, ...turns);
  const tbuckets = Array.from({ length: Math.min(maxT, 8) }, (_, i) => i + 1);
  const turnOpt = {
    color: [BRAND.ink], tooltip: { trigger: "axis" },
    grid: { left: 8, right: 20, top: 34, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: tbuckets.map((t) => `${t}`), name: "turns", nameGap: 26 },
    yAxis: { type: "value", name: "sessions", nameGap: 12 },
    series: [{ type: "bar", data: tbuckets.map((t) => turns.filter((x) => x === t).length) }],
  };

  const sessionDetail = (src: any[]) => (p: any): any => {
    const r = src[p.dataIndex]; if (!r) return null;
    return {
      title: "Session", items: [
        { label: "Conversation id", value: sid(r.conversation_id), copyable: true },
        { label: "Service", value: sid(r.service_name) },
        { label: "Cost", value: `$${Number(r.cost_usd || 0).toFixed(6)}` },
        { label: "Tokens", value: String(r.tokens ?? "—") },
        { label: "Turns", value: String(r.turns ?? "—") },
      ],
      action: { label: "Open session", run: () => openSession(r) },
    };
  };

  return (
    <>
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} lg={9}><ChartCard title="Top sessions by cost" option={costOpt} height={260} onPick={sessionDetail(topCost)} /></Col>
        <Col xs={24} lg={6}><ChartCard title="Turns per session" option={turnOpt} height={260} /></Col>
        <Col xs={24} lg={9}><ChartCard title="Top sessions by tokens" option={tokOpt} height={260} onPick={sessionDetail(topTok)} /></Col>
      </Row>

      <GenericTable rows={rows} loading={loading} onRowClick={openSession} exportName="sessions" />

      <Drawer width={820} open={!!cid} onClose={() => setCid(null)} title={`Session · ${cid || ""}`}>
        <Spin spinning={sessLoading}>
          <Typography.Paragraph type="secondary">{sessRows.length} turns (traces). Click a row to open its span tree.</Typography.Paragraph>
          <GenericTable rows={sessRows} onRowClick={(r) => setTraceId(r.trace_id)} exportName="session_traces" />
        </Spin>
      </Drawer>

      <TraceDrawer traceId={traceId} open={!!traceId} onClose={() => setTraceId(null)} />
    </>
  );
}
