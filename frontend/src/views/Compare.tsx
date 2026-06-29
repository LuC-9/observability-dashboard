import { useEffect, useState } from "react";
import { Row, Col, Card, Select, Statistic, Space, Typography } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import { get, Scope } from "../api";
import { BRAND, ERROR_RED } from "../theme";

const RANGES = [
  { value: "5m", label: "Last 5 min" }, { value: "30m", label: "Last 30 min" },
  { value: "1h", label: "Last 1 hour" }, { value: "6h", label: "Last 6 hours" },
  { value: "12h", label: "Last 12 hours" }, { value: "1d", label: "Last 1 day" },
];

const usd = (n: any) => `$${Number(n || 0).toFixed(4)}`;

function Delta({ a, b, invert }: { a: number; b: number; invert?: boolean }) {
  if (!b) return <Typography.Text type="secondary">—</Typography.Text>;
  const pct = ((a - b) / b) * 100;
  const up = pct >= 0;
  const bad = invert ? up : !up; // for cost/errors, up is bad
  return (
    <Typography.Text style={{ color: bad ? ERROR_RED : "#3f8600" }}>
      {up ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(pct).toFixed(1)}%
    </Typography.Text>
  );
}

export default function Compare({ scope }: { scope: Scope }) {
  const dims = { project: scope.project, platform: scope.platform, service: scope.service };
  const [ra, setRa] = useState("1h");
  const [rb, setRb] = useState("1d");
  const [a, setA] = useState<any>({});
  const [b, setB] = useState<any>({});

  useEffect(() => {
    get("/overview", { ...dims, time_range: ra } as any).then((o) => setA(o.kpis || {}));
  }, [JSON.stringify(dims), ra]);
  useEffect(() => {
    get("/overview", { ...dims, time_range: rb } as any).then((o) => setB(o.kpis || {}));
  }, [JSON.stringify(dims), rb]);

  const metrics = [
    { t: "Cost (USD)", ka: a.cost_usd, kb: b.cost_usd, fmt: usd, invert: true },
    { t: "Traces", ka: a.traces, kb: b.traces, fmt: (n: any) => (n ?? 0).toLocaleString() },
    { t: "Tokens", ka: (a.input_tokens || 0) + (a.output_tokens || 0), kb: (b.input_tokens || 0) + (b.output_tokens || 0), fmt: (n: any) => n.toLocaleString() },
    { t: "Error rate", ka: a.error_rate, kb: b.error_rate, fmt: (n: any) => `${((n || 0) * 100).toFixed(2)}%`, invert: true },
    { t: "P50 ms", ka: a.p50_ms, kb: b.p50_ms, fmt: (n: any) => `${n ?? 0}`, invert: true },
    { t: "P95 ms", ka: a.p95_ms, kb: b.p95_ms, fmt: (n: any) => `${n ?? 0}`, invert: true },
  ];

  const barOpt = {
    color: [BRAND.gold, BRAND.ink], tooltip: { trigger: "axis" }, legend: { data: ["A", "B"] },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: { type: "category", data: metrics.map((m) => m.t), axisLabel: { rotate: 20 } },
    yAxis: { type: "value" },
    series: [
      { name: "A", type: "bar", data: metrics.map((m) => Number(m.ka || 0)) },
      { name: "B", type: "bar", data: metrics.map((m) => Number(m.kb || 0)) },
    ],
  };

  return (
    <>
      <Space style={{ marginBottom: 12 }} wrap>
        <span>Window A</span>
        <Select style={{ width: 160 }} value={ra} options={RANGES} onChange={setRa} />
        <span>vs Window B</span>
        <Select style={{ width: 160 }} value={rb} options={RANGES} onChange={setRb} />
        <Typography.Text type="secondary">(uses the page's project/platform/service filters)</Typography.Text>
      </Space>
      <Row gutter={[12, 12]}>
        {metrics.map((m) => (
          <Col xs={12} md={8} lg={4} key={m.t}>
            <Card size="small" style={{ borderTop: `3px solid ${BRAND.gold}` }}>
              <Statistic title={m.t} value={m.fmt(m.ka) as any} valueStyle={{ color: BRAND.ink, fontSize: 20 }} />
              <Space size="small">
                <Typography.Text type="secondary">B: {m.fmt(m.kb)}</Typography.Text>
                <Delta a={Number(m.ka || 0)} b={Number(m.kb || 0)} invert={m.invert} />
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
      <Card size="small" title="A vs B" style={{ marginTop: 12 }}>
        <ReactECharts option={barOpt} style={{ height: 320 }} />
      </Card>
    </>
  );
}
