import { useEffect, useState } from "react";
import { Row, Col, Empty } from "antd";
import { get, Scope } from "../api";
import { BRAND, CHART_COLORS } from "../theme";
import GenericTable from "../components/GenericTable";
import ChartCard from "../components/ChartCard";

export default function Tools({ scope, refreshKey }: { scope: Scope; refreshKey: number }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setLoading(true);
    get("/tools", scope as any).then(setRows).finally(() => setLoading(false));
  }, [JSON.stringify(scope), refreshKey]);

  const top = rows.slice(0, 12);
  const cat = top.map((r) => r.tool || "—");
  const callsOpt = {
    color: CHART_COLORS, tooltip: { trigger: "axis" },
    legend: { data: ["Calls", "Avg ms", "Errors"] },
    grid: { left: 8, right: 50, top: 40, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: cat, axisLabel: { rotate: 30, overflow: "truncate", width: 90 } },
    yAxis: [{ type: "value", name: "calls" }, { type: "value", name: "ms" }],
    series: [
      { name: "Calls", type: "bar", data: top.map((r) => r.calls || 0) },
      { name: "Avg ms", type: "line", yAxisIndex: 1, data: top.map((r) => r.avg_ms || 0) },
      { name: "Errors", type: "bar", data: top.map((r) => r.errors || 0), itemStyle: { color: "#C0392B" } },
    ],
  };
  const shareOpt = {
    color: CHART_COLORS, tooltip: { trigger: "item" },
    series: [{ type: "pie", radius: ["40%", "70%"], data: top.map((r) => ({ name: r.tool || "—", value: r.calls || 0 })) }],
  };

  if (!loading && !rows.length)
    return <Empty description="No tool calls in this window (tool spans detected via gen_ai.tool.name / execute_tool / span name)" />;

  return (
    <>
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} lg={15}><ChartCard title="Tool usage · latency · errors" option={callsOpt} height={320}
          onPick={(p: any) => { const r = top[p.dataIndex]; return r ? {
            title: "Tool", items: [
              { label: "Tool", value: String(r.tool ?? "—"), copyable: true },
              { label: "Service", value: String(r.service_name ?? "—") },
              { label: "Calls", value: String(r.calls ?? "—") },
              { label: "Avg latency", value: `${r.avg_ms ?? 0} ms` },
              { label: "Errors", value: String(r.errors ?? "—") }] } : null; }} /></Col>
        <Col xs={24} lg={9}><ChartCard title="Call share" option={shareOpt} height={320}
          onPick={(p: any) => ({ title: "Tool", items: [
            { label: "Tool", value: String(p.name), copyable: true },
            { label: "Calls", value: String(p.value) }] })} /></Col>
      </Row>
      <GenericTable rows={rows} loading={loading} exportName="tools" />
    </>
  );
}
