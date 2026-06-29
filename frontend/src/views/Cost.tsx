import { useEffect, useState } from "react";
import { Segmented, Row, Col } from "antd";
import { get, Scope } from "../api";
import { BRAND, CHART_COLORS } from "../theme";
import GenericTable from "../components/GenericTable";
import ChartCard from "../components/ChartCard";

const GROUPS = [
  { value: "service_name", label: "By service" },
  { value: "model", label: "By model" },
  { value: "project_id", label: "By project" },
  { value: "source_platform", label: "By platform" },
];

export default function Cost({ scope, refreshKey, onScope }: { scope: Scope; refreshKey: number; onScope: (p: Partial<Scope>) => void }) {
  const [groupBy, setGroupBy] = useState("service_name");
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    get("/cost", { ...scope, group_by: groupBy } as any).then(setRows).finally(() => setLoading(false));
  }, [JSON.stringify(scope), groupBy, refreshKey]);

  const top = rows.slice(0, 12);
  const barOpt = {
    color: [BRAND.gold], tooltip: { trigger: "axis", valueFormatter: (v: any) => `$${Number(v).toFixed(5)}` },
    grid: { left: 8, right: 30, top: 10, bottom: 8, containLabel: true },
    xAxis: { type: "value", name: "USD" },
    yAxis: { type: "category", inverse: true, data: top.map((r) => r.key || "—"), axisLabel: { width: 130, overflow: "truncate" } },
    series: [{ type: "bar", data: top.map((r) => r.cost_usd || 0) }],
  };
  const pieOpt = {
    color: CHART_COLORS, tooltip: { trigger: "item", valueFormatter: (v: any) => `$${Number(v).toFixed(5)}` },
    series: [{ type: "pie", radius: ["40%", "70%"], data: top.map((r) => ({ name: r.key || "—", value: r.cost_usd || 0 })) }],
  };

  const actionFor = (key: string) => {
    if (groupBy === "service_name") return { label: `Filter service: ${key}`, run: () => onScope({ service: key }) };
    if (groupBy === "project_id") return { label: `Filter project: ${key}`, run: () => onScope({ project: key, platform: undefined, service: undefined }) };
    if (groupBy === "source_platform") return { label: `Filter platform: ${key}`, run: () => onScope({ platform: key }) };
    return undefined;
  };
  const detail = (p: any) => {
    const r = top[p.dataIndex] || top.find((x) => x.key === p.name); if (!r) return null;
    return {
      title: GROUPS.find((g) => g.value === groupBy)?.label || "Detail",
      items: [
        { label: groupBy, value: String(r.key ?? "—"), copyable: true },
        { label: "Cost", value: `$${Number(r.cost_usd || 0).toFixed(6)}` },
        { label: "Input tokens", value: String(r.input_tokens ?? "—") },
        { label: "Output tokens", value: String(r.output_tokens ?? "—") },
        { label: "Traces", value: String(r.traces ?? "—") },
      ],
      action: r.key ? actionFor(String(r.key)) : undefined,
    };
  };

  return (
    <>
      <Segmented options={GROUPS} value={groupBy} onChange={(v) => setGroupBy(v as string)} style={{ marginBottom: 12 }} />
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} lg={14}><ChartCard title="LLM cost (top)" option={barOpt} height={340} onPick={detail} /></Col>
        <Col xs={24} lg={10}><ChartCard title="Cost share" option={pieOpt} height={340} onPick={detail} /></Col>
      </Row>
      <GenericTable rows={rows} loading={loading} exportName={`cost_${groupBy}`} />
    </>
  );
}
